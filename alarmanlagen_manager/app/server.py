"""Alarmanlagen-Manager – Oberfläche und Schnittstelle.

Flask liefert die Ingress-Seite aus und stellt die API bereit. Die
eigentliche Arbeit macht die Anlage in ihrem eigenen Takt; hier wird nur
gelesen, eingestellt und angestoßen.
"""

import logging
import os
import signal
import sys
import threading

from flask import Flask, jsonify, request, send_from_directory

import eskalation
import ha
import lovelace
import protokoll
import uebernahme
from anlage import anlage
from mqtt_publisher import publisher
from store import neue_id, store

VERSION = os.environ.get("ADDON_VERSION", "1.0.0")
WWW_DIR = os.environ.get("WWW_DIR", "/www")
PORT = int(os.environ.get("PORT", "8102"))

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(),
                  logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("alarm")

app = Flask(__name__, static_folder=None)


# ----------------------------------------------------------------- Seiten

def _frisch(antwort):
    """Immer nachfragen, ob die Datei noch stimmt.

    Ohne das behält der Browser nach einem Update des Add-ons die alte
    app.js und zeigt tagelang eine Oberfläche, die es nicht mehr gibt –
    während das Add-on längst etwas anderes tut. ``no-cache`` heißt nicht
    "nicht speichern", sondern "vor dem Benutzen nachfragen"; über ETag
    kostet das im Regelfall eine leere Antwort.
    """
    antwort.headers["Cache-Control"] = "no-cache"
    return antwort


@app.route("/")
def index():
    return _frisch(send_from_directory(WWW_DIR, "index.html"))


@app.route("/<path:pfad>")
def statisch(pfad):
    return _frisch(send_from_directory(WWW_DIR, pfad))


# ----------------------------------------------------------------- Status

@app.route("/api/status")
def status():
    return jsonify({
        "version": VERSION,
        "anlage": anlage.zustand(),
        "mqtt": publisher.status(),
        "homeassistant": {"verfuegbar": ha.verfuegbar()},
        "uebernahme": store.get("uebernahme", default={}),
    })


@app.route("/api/konfig", methods=["GET", "POST"])
def konfig():
    if request.method == "GET":
        return jsonify(store.konfig())
    daten = request.get_json(silent=True) or {}
    store.konfig_ersetzen(daten)
    _nach_aenderung()
    return jsonify({"ok": True, "konfig": store.konfig()})


def _nach_aenderung() -> None:
    """Nach jeder Änderung: Beobachtung und Entitäten nachziehen."""
    anlage.beobachtung_erneuern()
    publisher.erneut_ankuendigen()
    publisher.veroeffentlichen(anlage.zustand())


# ----------------------------------------------------------------- Melder

@app.route("/api/melder", methods=["GET", "POST"])
def melder():
    if request.method == "GET":
        return jsonify(store.melder())
    liste = request.get_json(silent=True) or []
    # Jeder Melder braucht eine ID, und sie bleibt, was sie ist: Die
    # Überbrückung und das Protokoll zeigen darauf.
    for eintrag in liste:
        eintrag.setdefault("id", neue_id())
    store.melder_setzen(liste)
    _nach_aenderung()
    return jsonify({"ok": True, "melder": store.melder()})


@app.route("/api/melder/ignorieren", methods=["POST"])
def ignorieren():
    """Einen Vorschlag dauerhaft ausblenden – oder wieder hervorholen."""
    daten = request.get_json(silent=True) or {}
    liste = store.get("ignorierte_melder", default=[]) or []
    entity_id = daten.get("entity")
    if daten.get("alle_zurueck"):
        liste = []
    elif entity_id and daten.get("an", True):
        if entity_id not in liste:
            liste.append(entity_id)
    elif entity_id:
        liste = [e for e in liste if e != entity_id]
    store.set("ignorierte_melder", liste)
    return jsonify({"ok": True, "ignoriert": liste})


@app.route("/api/melder/<melder_id>/ueberbruecken", methods=["POST"])
def ueberbruecken(melder_id):
    daten = request.get_json(silent=True) or {}
    anlage.ueberbruecken(melder_id, bool(daten.get("an", True)))
    return jsonify({"ok": True, "zustand": anlage.zustand()})


# ------------------------------------------------------------ Auswahllisten

@app.route("/api/auswahl")
def auswahl():
    praefix = store.get("betrieb", "entity_praefix", default="alarmanlage")
    return jsonify({
        "melder": ha.melderkandidaten(praefix),
        "ignoriert": store.get("ignorierte_melder", default=[]),
        "bereiche": ha.bereiche(),
        "personen": ha.entitaeten("person."),
        "schloesser": ha.entitaeten("lock."),
        "sensoren": ha.entitaeten("sensor.", "binary_sensor."),
        "lichter": ha.entitaeten("light."),
        # Fuer die Ruhequellen: was sich bewegt und dabei einen Melder
        # ueberlisten kann.
        "bewegliches": ha.entitaeten("cover.", "fan.", "climate.", "vacuum."),
        "schalter": ha.entitaeten("switch.", "siren."),
        "helfer": ha.entitaeten("input_select.", "input_boolean."),
        "meldewege": ha.meldewege(),
    })


# -------------------------------------------------------------- Bedienung

@app.route("/api/schalten", methods=["POST"])
def schalten():
    daten = request.get_json(silent=True) or {}
    befehl = daten.get("befehl")
    if befehl == "entschaerfen":
        return jsonify(anlage.entschaerfen("oberflaeche", auch_hausmodus=True))
    if befehl == "scharf":
        return jsonify(anlage.scharf_schalten(daten.get("modus", "abwesend"),
                                              quelle="oberflaeche",
                                              sofort=bool(daten.get("sofort"))))
    if befehl == "hausmodus":
        return jsonify(anlage.hausmodus_setzen(daten.get("modus", "zuhause"),
                                               quelle="oberflaeche"))
    if befehl == "quittieren":
        anlage.alarme_quittieren()
        return jsonify({"ok": True})
    if befehl == "trockenlauf":
        store.set("betrieb", "trockenlauf", bool(daten.get("an")))
        publisher.veroeffentlichen(anlage.zustand())
        protokoll.schreiben("betrieb",
                            "Trockenlauf " + ("an" if daten.get("an") else "aus"))
        return jsonify({"ok": True})
    if befehl == "automatik":
        store.set("betrieb", "automatik", bool(daten.get("an")))
        publisher.veroeffentlichen(anlage.zustand())
        protokoll.schreiben("betrieb",
                            "Automatik " + ("an" if daten.get("an") else "aus"))
        return jsonify({"ok": True})
    return jsonify({"ok": False, "grund": "unbekannter_befehl"}), 400


@app.route("/api/probe", methods=["POST"])
def probe():
    """Eine Meldestufe einmal von Hand auslösen.

    Damit sich prüfen lässt, ob der kritische Push wirklich durch den
    Fokusmodus kommt – herausfinden will man das nicht im Ernstfall.
    """
    daten = request.get_json(silent=True) or {}
    linie = daten.get("linie", "einbruch")
    stufe = daten.get("stufe", "alarm")
    getan = eskalation.ausfuehren(linie, stufe, ausloeser="Probelauf",
                                  ort="Probelauf", modus="Probelauf", rest=0)
    return jsonify({"ok": True, "getan": getan})


# -------------------------------------------------------------- Protokoll

@app.route("/api/protokoll")
def protokoll_lesen():
    anzahl = min(int(request.args.get("anzahl", 200)), 1000)
    return jsonify(protokoll.lesen(anzahl, request.args.get("art")))


# -------------------------------------------------------------- Übernahme

@app.route("/api/uebernahme/vorschlag")
def uebernahme_vorschlag():
    return jsonify(uebernahme.vorschlag())


@app.route("/api/uebernahme", methods=["POST"])
def uebernahme_einspielen():
    daten = request.get_json(silent=True) or {}
    ergebnis = uebernahme.uebernehmen(daten)
    _nach_aenderung()
    return jsonify(ergebnis)


@app.route("/api/uebernahme/abschalten", methods=["POST"])
def uebernahme_abschalten():
    daten = request.get_json(silent=True) or {}
    return jsonify(uebernahme.automationen_abschalten(daten.get("aliasse", [])))


@app.route("/api/uebernahme/zurueck", methods=["POST"])
def uebernahme_zurueck():
    return jsonify(uebernahme.automationen_zurueck())


# ------------------------------------------------------------------ Start

def _mqtt_befehl(befehl: str, nutzlast: str) -> None:
    """Ein Befehl vom Bedienfeld in Home Assistant."""
    if befehl == "panel":
        if nutzlast == "DISARM":
            # Über das Bedienfeld ist es ein Mensch, der entschärft – der
            # meint den Sollzustand mit.
            anlage.entschaerfen("panel", auch_hausmodus=True)
            return
        for schluessel, modus in (store.get("modi", default={}) or {}).items():
            ziel = {"ARM_AWAY": "armed_away", "ARM_HOME": "armed_home",
                    "ARM_NIGHT": "armed_night",
                    "ARM_VACATION": "armed_vacation"}.get(nutzlast)
            if ziel and modus.get("panel_zustand") == ziel:
                anlage.hausmodus_setzen(schluessel, quelle="panel")
                anlage.scharf_schalten(schluessel, quelle="panel")
                return
    elif befehl == "hausmodus":
        if nutzlast == "Zuhause":
            anlage.hausmodus_setzen("zuhause", quelle="panel")
            return
        for schluessel, modus in (store.get("modi", default={}) or {}).items():
            if modus.get("name") == nutzlast:
                anlage.hausmodus_setzen(schluessel, quelle="panel")
                return
    elif befehl in ("automatik", "trockenlauf"):
        store.set("betrieb", befehl, nutzlast == "ON")
        protokoll.schreiben("betrieb", f"{befehl}: {nutzlast}", quelle="panel")
        publisher.veroeffentlichen(anlage.zustand())
    elif befehl == "quittieren":
        anlage.alarme_quittieren()


def _beenden(signum, rahmen):  # noqa: ARG001
    log.info("Beende …")
    anlage.stop()
    publisher.stop()
    sys.exit(0)


def main() -> None:
    protokoll.kuerzen()

    publisher.on_befehl = _mqtt_befehl
    anlage.on_zustand = publisher.veroeffentlichen
    publisher.start()
    anlage.start()

    # Die Karte bereitstellen und anmelden – im Hintergrund, damit ein
    # langsamer Start von Home Assistant die Oberfläche nicht aufhält.
    threading.Thread(target=lovelace.einrichten, args=(VERSION,),
                     daemon=True, name="karte").start()

    signal.signal(signal.SIGTERM, _beenden)
    signal.signal(signal.SIGINT, _beenden)

    log.info("Alarmanlagen-Manager %s bereit auf Port %d", VERSION, PORT)
    app.run(host="0.0.0.0", port=PORT, threaded=True)


if __name__ == "__main__":
    main()
