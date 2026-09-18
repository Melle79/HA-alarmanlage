"""Die vorhandenen Automationen lesen, verstehen und ablösen.

Der Vorschlag wird aus den Automationen gewonnen, aber **nicht** blind
übernommen: Wer sich an bestehenden Automationen entlanghangelt, erbt
deren Zufälligkeiten und braucht für jede Abweichung einen Kunstgriff.
Das Modell steht (Linien, Modi, Melder); die Übernahme füllt es nur.

Abgeschaltet wird, nicht gelöscht. Eine Alarmanlage ist die falsche
Stelle für einen Weg, der nicht zurückführt – und der Zustand der
Automationen wird vorher weggeschrieben.
"""

import json
import logging
import os
import re
import time
from pathlib import Path

import ha
import protokoll
from store import neue_id, store

log = logging.getLogger("alarm.uebernahme")

CONFIG_DIR = Path(os.environ.get("HA_CONFIG_DIR", "/config"))
AUTOMATIONEN = CONFIG_DIR / "automations.yaml"
KONFIGURATION = CONFIG_DIR / "configuration.yaml"
SICHERUNG_DIR = Path(os.environ.get("DATA_DIR", "/data")) / "sicherungen"

# Woran eine Automation als Teil der Alarmanlage zu erkennen ist.
ALARM_MERKMALE = ("alarm_control_panel", "alarm_arm_", "alarm_disarm",
                  "alarm_trigger")
RAUCH_MERKMALE = ("rauchmelder", "rauch", "feueralarm", "smoke")


def _laden() -> list:
    if not AUTOMATIONEN.is_file():
        log.warning("%s nicht lesbar", AUTOMATIONEN)
        return []
    try:
        import yaml  # noqa: PLC0415
        daten = yaml.safe_load(AUTOMATIONEN.read_text(encoding="utf-8"))
    except Exception as err:  # noqa: BLE001
        log.warning("automations.yaml nicht lesbar: %s", err)
        return []
    return daten if isinstance(daten, list) else []


def _entitaeten(knoten, treffer: set) -> None:
    """Alle entity_id-Angaben aus einem beliebig verschachtelten Baum."""
    if isinstance(knoten, dict):
        for schluessel, wert in knoten.items():
            if schluessel == "entity_id":
                if isinstance(wert, str):
                    treffer.add(wert)
                elif isinstance(wert, list):
                    treffer.update(w for w in wert if isinstance(w, str))
            else:
                _entitaeten(wert, treffer)
    elif isinstance(knoten, list):
        for eintrag in knoten:
            _entitaeten(eintrag, treffer)


def _dienste(knoten, treffer: set) -> None:
    if isinstance(knoten, dict):
        for schluessel, wert in knoten.items():
            if schluessel in ("action", "service") and isinstance(wert, str):
                treffer.add(wert)
            else:
                _dienste(wert, treffer)
    elif isinstance(knoten, list):
        for eintrag in knoten:
            _dienste(eintrag, treffer)


def kandidaten() -> list:
    """Welche Automationen dieses Add-on ersetzen würde."""
    out = []
    # Woran eine Automation hängt, sagt mehr als ihr Name. Eine Automation
    # namens "RM Alarm oeffnet alle Rollos" ist über den Namen nicht als
    # Rauchsache zu erkennen - über ihren Auslöser schon.
    gefahrenmelder = {m["entity_id"]: m["art"] for m in ha.melderkandidaten()
                      if m["art"] in ("rauch", "wasser")}
    for eintrag in _laden():
        if not isinstance(eintrag, dict):
            continue
        roh = json.dumps(eintrag, ensure_ascii=False).lower()
        alias = eintrag.get("alias", "") or ""
        entitaeten: set = set()
        _entitaeten(eintrag, entitaeten)
        dienste: set = set()
        _dienste(eintrag, dienste)

        arten = {gefahrenmelder[e] for e in entitaeten if e in gefahrenmelder}
        art = None
        if any(m in roh for m in ALARM_MERKMALE):
            art = "einbruch"
        elif arten:
            art = "rauch" if "rauch" in arten else "wasser"
        elif any(m in alias.lower() for m in RAUCH_MERKMALE) and \
                any(e.startswith("binary_sensor.") for e in entitaeten):
            art = "rauch"
        elif "hausmodus" in roh and "input_select" in roh:
            art = "hausmodus"
        if not art:
            continue

        # Automationen, die bei Rauch etwas *fahren* statt zu melden,
        # gehören anderswo hin – etwa Rollos, die ein eigener Planer
        # aufzieht. Sie werden gezeigt, aber nicht vorgeschlagen.
        fremd = any(d.startswith(("cover.", "light.", "climate.", "scene."))
                    for d in dienste)

        out.append({
            "id": eintrag.get("id"),
            "alias": alias,
            "art": art,
            "entitaeten": sorted(entitaeten),
            "dienste": sorted(dienste),
            "fremdwirkung": fremd,
            "vorschlagen": not fremd,
            "aktiv": _automation_aktiv(alias),
        })
    return out


def _automation_aktiv(alias: str) -> bool | None:
    for eintrag in ha.zustaende():
        if eintrag.get("entity_id", "").startswith("automation.") and \
                eintrag.get("attributes", {}).get("friendly_name") == alias:
            return eintrag.get("state") == "on"
    return None


def panel_werte() -> dict:
    """Ausgeh-, Eintritts- und Auslösezeit aus dem YAML-Bedienfeld.

    Damit die Übernahme nicht mit anderen Zeiten anfängt als die Anlage
    bisher hatte – ein stillschweigend von 45 auf 30 Sekunden verkürzter
    Eintrittsweg wäre genau die Art Überraschung, die niemand sucht.
    """
    if not KONFIGURATION.is_file():
        return {}
    text = KONFIGURATION.read_text(encoding="utf-8", errors="replace")
    out = {}
    for schluessel, ziel in (("arming_time", "ausgehzeit"),
                             ("delay_time", "eintrittszeit"),
                             ("trigger_time", "ausloesezeit")):
        treffer = re.search(rf"^\s*{schluessel}:\s*(\d+)", text, re.M)
        if treffer:
            out[ziel] = int(treffer.group(1))
    return out


def vorschlag() -> dict:
    """Aus den Automationen einen vollständigen Konfigurationsvorschlag."""
    gefunden = kandidaten()
    melder, personen, schloesser, push, sprache = [], [], [], [], []
    bereiche = ha.bereiche()
    bekannt = {m["entity_id"]: m for m in ha.melderkandidaten()}

    for automation in gefunden:
        if not automation["vorschlagen"]:
            continue
        for entity_id in automation["entitaeten"]:
            if entity_id.startswith("person."):
                personen.append(entity_id)
            elif entity_id.startswith("lock."):
                schloesser.append(entity_id)
            elif entity_id.startswith("binary_sensor."):
                _melder_aufnehmen(melder, entity_id, automation["art"],
                                  bekannt, bereiche)
        for dienst in automation["dienste"]:
            if dienst.startswith("notify.mobile_app_"):
                push.append(dienst)
            elif dienst.startswith("notify.alexa_media"):
                sprache.append(dienst)

    werte = panel_werte()
    modi = store.get("modi", default={}) or {}
    for schluessel in ("abwesend", "urlaub", "nacht", "teilscharf"):
        if schluessel not in modi:
            continue
        if werte.get("ausgehzeit") is not None and schluessel != "teilscharf":
            modi[schluessel]["ausgehzeit"] = werte["ausgehzeit"]
        if werte.get("eintrittszeit") is not None:
            modi[schluessel]["eintrittszeit"] = werte["eintrittszeit"]

    linien = store.get("linien", default={}) or {}
    if werte.get("ausloesezeit") is not None:
        linien["einbruch"]["ausloesezeit"] = werte["ausloesezeit"]
    if any(m["linie"] == "wasser" for m in melder):
        linien["wasser"]["aktiv"] = True

    return {
        "automationen": gefunden,
        "konfig": {
            "modi": modi,
            "linien": linien,
            "melder": melder,
            "scharfschaltung": {
                "quelle": "anwesenheit",
                "personen": sorted(set(personen)),
            },
            "entschaerfung": {"schloesser": sorted(set(schloesser))},
            "eskalation": _eskalation(sorted(set(push)), sorted(set(sprache))),
        },
    }


def arten_verfeinern() -> int:
    """Rauchmelder, die in Wahrheit Gas oder Kohlenmonoxid melden.

    Bis Fassung 1.7.4 fielen smoke, gas, carbon_monoxide und heat alle
    unter "rauch". Die Geräteklasse in Home Assistant weiß es genauer, und
    der Unterschied steht am Ende in der Meldung: Wer nachts geweckt wird
    und "Rauch" liest, sucht nach dem Falschen.

    Ändert nur die *Art*, nicht die Linie und nicht das Verhalten.
    """
    melder = store.melder()
    if not melder:
        return 0
    klassen = {}
    for eintrag in ha.zustaende(erzwingen=True):
        klasse = eintrag.get("attributes", {}).get("device_class")
        if klasse in ha.GEFAHR:
            klassen[eintrag["entity_id"]] = ha.GEFAHR[klasse]

    geaendert = 0
    for eintrag in melder:
        genauer = klassen.get(eintrag.get("entity"))
        if genauer and eintrag.get("art") != genauer:
            log.info("%s: Art '%s' -> '%s'", eintrag.get("entity"),
                     eintrag.get("art"), genauer)
            eintrag["art"] = genauer
            geaendert += 1
    if geaendert:
        store.melder_setzen(melder)
        protokoll.schreiben("betrieb",
                            f"{geaendert} Melder genauer eingeordnet "
                            "(Gas, Kohlenmonoxid, Hitze)")
    return geaendert


def _melder_aufnehmen(melder, entity_id, art, bekannt, bereiche) -> None:
    if any(m["entity"] == entity_id for m in melder):
        return
    info = bekannt.get(entity_id, {})
    melder_art = info.get("art", "sonstige")
    if melder_art in ("rauch", "gas", "kohlenmonoxid", "hitze"):
        linie = "rauch"
    elif art == "rauch":
        linie, melder_art = "rauch", "rauch"
    elif melder_art == "wasser":
        linie = "wasser"
    else:
        linie = "einbruch"
        if melder_art == "sonstige":
            melder_art = "bewegung"
    name = info.get("name") or entity_id
    melder.append({
        "id": neue_id(),
        "entity": entity_id,
        "name": name,
        # Der Ort steht in der Ansage: "In Lunas Zimmer wurde Rauch
        # erkannt". Vorgeschlagen wird der Bereich aus Home Assistant,
        # weil Meldernamen wie "RM Luna Rauch" sich schlecht vorlesen.
        "ort": bereiche.get(entity_id) or name,
        "art": melder_art,
        "linie": linie,
        "modi": [],
        # Die alte Anlage ließ jeden Melder über die Eintrittsverzögerung
        # laufen (delay_time des Bedienfelds galt für alle). Das wird
        # übernommen, damit die Übernahme nichts verschärft.
        "verzoegert": linie == "einbruch",
        "ausloesezustand": "on",
        "aktiv": True,
    })


def _eskalation(push: list, sprache: list) -> dict:
    """Meldewege aus den Automationen, Lautstärke nach Gefahrenlage."""
    grund = store.get("eskalation", default={}) or {}
    for linie in ("einbruch", "rauch", "wasser"):
        for stufe in grund.get(linie, {}):
            grund[linie][stufe]["push"] = list(push)
    # Ansagen nur dort, wo die alte Anlage sie hatte: bei Rauch. Zehn
    # sprechende Lautsprecher bei jedem Fehlalarm der Bewegungsmelder
    # wären ein sicherer Weg, die Anlage wieder abzuschalten.
    if sprache:
        grund["rauch"]["alarm"]["alexa"] = list(sprache)
    # Der Voralarm bleibt still: Wer in den 45 Sekunden entschärft, soll
    # keine Meldung bekommen.
    grund["einbruch"]["voralarm"]["push"] = []
    grund["einbruch"]["voralarm"]["aktiv"] = False
    grund["einbruch"]["entwarnung"]["kritisch"] = False
    grund["einbruch"]["entwarnung"]["persistent"] = True
    return grund


def uebernehmen(auswahl: dict) -> dict:
    """Den Vorschlag (oder eine bearbeitete Fassung) einspielen."""
    store.konfig_ersetzen(auswahl)
    if "melder" in auswahl:
        store.melder_setzen(auswahl["melder"])
    protokoll.schreiben("uebernahme",
                        f"Konfiguration übernommen – {len(auswahl.get('melder', []))} "
                        f"Melder")
    return {"ok": True}


def automationen_abschalten(aliasse: list) -> dict:
    """Die abgelösten Automationen ausschalten – nach einer Sicherung.

    Zurückdrehen heißt: diese Automationen wieder einschalten **und** den
    Trockenlauf wieder an. Beides steht in der Sicherungsdatei.
    """
    SICHERUNG_DIR.mkdir(parents=True, exist_ok=True)
    vorher = []
    entitaeten = []
    for eintrag in ha.zustaende(erzwingen=True):
        eid = eintrag.get("entity_id", "")
        if not eid.startswith("automation."):
            continue
        name = eintrag.get("attributes", {}).get("friendly_name")
        if name not in aliasse:
            continue
        vorher.append({"entity_id": eid, "alias": name,
                       "zustand": eintrag.get("state")})
        if eintrag.get("state") == "on":
            entitaeten.append(eid)

    stempel = time.strftime("%Y%m%d-%H%M%S")
    datei = SICHERUNG_DIR / f"automationen-vor-uebernahme-{stempel}.json"
    datei.write_text(json.dumps(vorher, ensure_ascii=False, indent=2),
                     encoding="utf-8")

    if not entitaeten:
        return {"ok": True, "abgeschaltet": [], "sicherung": str(datei)}

    ha.dienst("automation", "turn_off", {"entity_id": entitaeten})
    store.set("uebernahme", "ersetzte_automationen", [v["alias"] for v in vorher])
    store.set("uebernahme", "abgeschaltet_am", time.time())
    protokoll.schreiben("uebernahme",
                        f"{len(entitaeten)} Automationen abgeschaltet "
                        f"(Sicherung: {datei.name})", automationen=entitaeten)
    return {"ok": True, "abgeschaltet": entitaeten, "sicherung": str(datei)}


def automationen_zurueck() -> dict:
    """Die jüngste Sicherung wieder einschalten."""
    if not SICHERUNG_DIR.is_dir():
        return {"ok": False, "grund": "keine_sicherung"}
    dateien = sorted(SICHERUNG_DIR.glob("automationen-vor-uebernahme-*.json"))
    if not dateien:
        return {"ok": False, "grund": "keine_sicherung"}
    try:
        vorher = json.loads(dateien[-1].read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        return {"ok": False, "grund": str(err)}
    an = [v["entity_id"] for v in vorher if v.get("zustand") == "on"]
    if an:
        ha.dienst("automation", "turn_on", {"entity_id": an})
    store.set("betrieb", "trockenlauf", True)
    protokoll.schreiben("uebernahme",
                        f"{len(an)} Automationen wieder eingeschaltet, "
                        "Trockenlauf an", datei=dateien[-1].name)
    return {"ok": True, "eingeschaltet": an}
