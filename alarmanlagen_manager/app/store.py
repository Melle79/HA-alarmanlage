"""Einstellungen und Betriebszustand unter /data.

Zwei Dateien, mit Absicht getrennt:

* ``konfig.json`` – was der Benutzer eingestellt hat. Änderbar, sicherbar,
  bei einem Umzug mitzunehmen.
* ``zustand.json`` – wo die Anlage gerade steht. Muss einen Neustart
  überleben, sonst steht das Haus nach jedem Update der Add-ons unscharf
  da, ohne dass es jemandem auffällt.

Der Zustand wird bei jeder Änderung geschrieben, nicht im Takt: Ein
Stromausfall eine Sekunde nach dem Scharfschalten darf nicht dazu führen,
dass die Anlage sich für entschärft hält.
"""

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path

log = logging.getLogger("alarm.store")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
KONFIG_DATEI = DATA_DIR / "konfig.json"
ZUSTAND_DATEI = DATA_DIR / "zustand.json"

# Die Gefahrenlinien. "scharf" heißt: zählt nur, wenn die Anlage scharf ist.
# "immer" heißt: rund um die Uhr, unabhängig vom Scharfzustand – Rauch und
# Wasser kümmert es nicht, ob jemand zu Hause ist.
LINIEN_VORGABE = {
    "einbruch": {
        "reihenfolge": 1,
        "name": "Einbruch",
        "geltung": "scharf",
        "symbol": "mdi:shield-alert",
        # Wie lange der Zustand "ausgelöst" anhält, bevor die Anlage von
        # selbst wieder scharf schaltet. 0 = bis jemand entschärft.
        "ausloesezeit": 300,
        "aktiv": True,
    },
    "rauch": {
        "reihenfolge": 2,
        "name": "Rauch und Feuer",
        "geltung": "immer",
        "symbol": "mdi:smoke-detector-variant-alert",
        "ausloesezeit": 0,
        "aktiv": True,
    },
    "wasser": {
        "reihenfolge": 3,
        "name": "Wasser",
        "geltung": "immer",
        "symbol": "mdi:water-alert",
        "ausloesezeit": 0,
        "aktiv": False,
    },
}

# Die Scharfmodi. Jeder bildet einen Zustand des Bedienfelds ab; die
# Zuordnung ist fest, weil Home Assistant nur diese kennt.
MODI_VORGABE = {
    "abwesend": {
        "name": "Abwesend",
        "panel_zustand": "armed_away",
        "ausgehzeit": 60,
        "eintrittszeit": 45,
        "aktiv": True,
        "reihenfolge": 1,
    },
    "urlaub": {
        "name": "Urlaub",
        "panel_zustand": "armed_vacation",
        "ausgehzeit": 60,
        "eintrittszeit": 45,
        "aktiv": True,
        "reihenfolge": 2,
    },
    "nacht": {
        "name": "Nacht",
        "panel_zustand": "armed_night",
        "ausgehzeit": 30,
        "eintrittszeit": 45,
        "aktiv": False,
        "reihenfolge": 3,
    },
    "teilscharf": {
        "name": "Teilscharf",
        "panel_zustand": "armed_home",
        "ausgehzeit": 0,
        "eintrittszeit": 45,
        "aktiv": False,
        "reihenfolge": 4,
    },
}

# Eine Meldestufe: an wen, wie laut, worüber.
def _stufe(kritisch: bool = False) -> dict:
    return {
        "aktiv": True,
        "push": [],           # notify.mobile_app_*
        "kritisch": kritisch,  # kritischer Push durchbricht den Fokusmodus
        "persistent": True,    # Meldung in Home Assistant selbst
        "alexa": [],          # notify.alexa_media_*
        "licht": [],          # light.* – gehen auf volle Helligkeit
        "licht_farbe": [255, 0, 0],
        "schalter": [],       # switch.* – etwa eine Sirene
        "text": "",           # leer = der vorgegebene Satz der Stufe
    }


DEFAULTS = {
    "version": 2,
    "betrieb": {
        # Trockenlauf: die Anlage rechnet und protokolliert alles, schickt
        # aber nichts hinaus. So lässt sie sich neben den alten
        # Automationen einfahren, ohne dass nachts zwei Anlagen melden.
        "trockenlauf": True,
        # Im Trockenlauf trotzdem eine stille Meldung in Home Assistant
        # hinterlassen – sonst merkt niemand, dass es gepasst hätte.
        "trockenlauf_meldet": True,
        # Der große Hauptschalter. Aus heißt: die Anlage schaltet sich
        # nicht mehr von selbst scharf. Von Hand geht weiter alles.
        "automatik": True,
        "entity_praefix": os.environ.get("ENTITY_PRAEFIX", "alarmanlage"),
    },
    "modi": MODI_VORGABE,
    "linien": LINIEN_VORGABE,
    # Liste, keine Zuordnung: die Reihenfolge ist die Anzeigereihenfolge,
    # und ein Melder darf zweimal dieselbe Entität benutzen (etwa einmal
    # sofort, einmal verzögert in einem anderen Modus).
    #
    # Ein Melder trägt: id, entity, name, ort, art, linie, modi,
    # verzoegert, ausloesezustand, aktiv, text – und gegen Fehlalarme
    # zwei Felder:
    #   mindestdauer   Sekunden, die er anhalten muss, bevor er zählt
    #   ruhe_bei       Entitäten, deren Bewegung ihn erklärbar auslöst
    #   ruhe_sekunden  wie lange danach übergangen wird
    "melder": [],
    "scharfschaltung": {
        # anwesenheit | entitaet | nur_hand
        "quelle": "anwesenheit",
        "personen": [],
        # Welcher Modus greift, wenn niemand mehr da ist.
        "modus_leer": "abwesend",
        # Wie lange leer sein muss, bevor scharf geschaltet wird.
        "leer_sekunden": 300,
        # Nie scharf, solange eine Person als zu Hause gemeldet ist. Steht
        # hier als eigener Schalter, weil es der Rettungsanker gegen jede
        # falsche Abwesenheitsmeldung ist.
        "nie_scharf_wenn_jemand_da": True,
        # Ein Modus, den niemand automatisch verlässt (Urlaub). Solange er
        # steht, ändert die Anwesenheit nichts.
        "handmodus": "urlaub",
        # Nur bei quelle == "entitaet": eine vorhandene input_select o. ä.
        "entitaet": "",
        "entitaet_zuordnung": {},
    },
    "entschaerfung": {
        # Wer am Schloss aufschließt, hat sich ausgewiesen.
        "schloesser": [],
        # Entitäten, die dasselbe melden, aber keine lock-Entität sind
        # (etwa ein Cloud-Sensor mit dem Schlosszustand).
        "zusatzmelder": [],
        "zusatz_zustand": "unlocked",
        # Nachlaufsperre: nach dem Aufschließen löst Bewegung nicht aus.
        "nachlauf_minuten": 5,
        # Obergrenze ab dem Aufschließen – ein Schloss, das "zu" nie
        # meldet, darf die Anlage nicht dauerhaft blind machen.
        "nachlauf_hoechstens_minuten": 60,
        # Wieder scharf, nachdem abgeschlossen wurde.
        "wieder_scharf_minuten": 10,
        # Rückfallschutz, falls "abgeschlossen" nie kommt.
        "rueckfall_stunden": 2,
        # Wie oft eine unterdrückte Bewegung gemeldet werden darf.
        "meldung_abstand_minuten": 30,
        "melden": True,
    },
    # Vorschläge, die der Benutzer dauerhaft nicht mehr sehen will. Nötig,
    # weil "binary_sensor mit Geräteklasse door" auch auf Dinge zutrifft,
    # die mit dem Haus nichts zu tun haben - in einer gewachsenen
    # Installation etwa auf den Öffnungszustand von Tankstellen.
    "ignorierte_melder": [],
    "vorpruefung": {
        # Offene Kontakte beim Scharfschalten: melden | ueberbruecken | verhindern
        "offene_kontakte": "melden",
    },
    "eskalation": {
        "einbruch": {
            "voralarm": dict(_stufe(), aktiv=False, persistent=True),
            "alarm": _stufe(kritisch=True),
            "entwarnung": dict(_stufe(), licht=[], schalter=[]),
        },
        "rauch": {
            "alarm": _stufe(kritisch=True),
            "entwarnung": dict(_stufe(), aktiv=False),
        },
        "wasser": {
            "alarm": _stufe(kritisch=True),
            "entwarnung": dict(_stufe(), aktiv=False),
        },
    },
    # Wird beim ersten Lauf von der Übernahme gefüllt und danach nur noch
    # angezeigt: welche Automationen dieses Add-on ersetzt.
    "uebernahme": {
        "ersetzte_automationen": [],
        "abgeschaltet_am": None,
    },
}


def neue_id() -> str:
    return uuid.uuid4().hex[:12]


class Store:
    def __init__(self):
        self._lock = threading.RLock()
        self._konfig: dict = {}
        self._zustand: dict = {}
        self.laden()

    # ------------------------------------------------------------- Laden

    def laden(self) -> None:
        with self._lock:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            roh = {}
            if KONFIG_DATEI.is_file():
                try:
                    roh = json.loads(KONFIG_DATEI.read_text(encoding="utf-8"))
                except (OSError, ValueError) as err:
                    log.error("konfig.json unlesbar, starte mit Vorgaben: %s", err)
            self._konfig = _vereinen(DEFAULTS, roh)

            self._zustand = {
                "panel": "disarmed",
                # Was gelten soll ("zuhause" oder ein Modusschlüssel) –
                # getrennt vom Panel-Zustand, weil beides auseinanderläuft,
                # sobald jemand die Haustür aufschließt.
                "hausmodus": "zuhause",
                "modus": None,
                "seit": time.time(),
                # Wann der laufende Übergang (arming/pending/triggered) endet.
                "frist": None,
                "ausloeser": None,
                "ausloeser_zeit": None,
                "ausloeser_linie": None,
                "ausloeser_text": None,
                "letzte_entsperrung": None,
                # Warum zuletzt entschärft wurde: "schloss", "hand",
                # "automatik" … Nur beim Schloss steht jemand im Haus.
                "entschaerft_durch": None,
                "letzte_unterdrueckungsmeldung": None,
                "ueberbrueckt": [],
                "offene_alarme": {},
            }
            if ZUSTAND_DATEI.is_file():
                try:
                    gespeichert = json.loads(ZUSTAND_DATEI.read_text(encoding="utf-8"))
                    self._zustand.update(gespeichert)
                except (OSError, ValueError) as err:
                    log.error("zustand.json unlesbar: %s", err)

    # ---------------------------------------------------------- Schreiben

    def _schreiben(self, pfad: Path, inhalt: dict) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = pfad.with_suffix(".tmp")
        tmp.write_text(json.dumps(inhalt, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        # Erst schreiben, dann umbenennen – ein Stromausfall mitten im
        # Schreiben hinterlässt sonst eine halbe Datei.
        tmp.replace(pfad)

    def konfig_speichern(self) -> None:
        with self._lock:
            self._schreiben(KONFIG_DATEI, self._konfig)

    def zustand_speichern(self) -> None:
        with self._lock:
            self._schreiben(ZUSTAND_DATEI, self._zustand)

    # ----------------------------------------------------------- Zugriff

    def konfig(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._konfig))

    def get(self, *pfad, default=None):
        with self._lock:
            knoten = self._konfig
            for schluessel in pfad:
                if not isinstance(knoten, dict) or schluessel not in knoten:
                    return default
                knoten = knoten[schluessel]
            return json.loads(json.dumps(knoten)) if isinstance(knoten, (dict, list)) \
                else knoten

    def set(self, *pfad_und_wert) -> None:
        *pfad, wert = pfad_und_wert
        with self._lock:
            knoten = self._konfig
            for schluessel in pfad[:-1]:
                knoten = knoten.setdefault(schluessel, {})
            knoten[pfad[-1]] = wert
        self.konfig_speichern()

    def konfig_ersetzen(self, neu: dict) -> None:
        """Ganzen Abschnitt aus der Oberfläche übernehmen.

        Es wird vereint, nicht ersetzt: Die Oberfläche schickt nur, was sie
        anzeigt, und ein neuer Schlüssel aus einem Update darf dabei nicht
        stillschweigend verschwinden.
        """
        with self._lock:
            self._konfig = _vereinen(self._konfig, neu)
        self.konfig_speichern()

    # ------------------------------------------------------------ Melder

    def melder(self) -> list:
        with self._lock:
            return json.loads(json.dumps(self._konfig.get("melder", [])))

    def melder_setzen(self, liste: list) -> None:
        with self._lock:
            self._konfig["melder"] = liste
        self.konfig_speichern()

    # ----------------------------------------------------------- Zustand

    def zustand(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._zustand))

    def z_get(self, schluessel, default=None):
        with self._lock:
            return self._zustand.get(schluessel, default)

    def z_set(self, **felder) -> None:
        with self._lock:
            self._zustand.update(felder)
        self.zustand_speichern()


def _vereinen(basis: dict, ueberlagerung: dict) -> dict:
    """Vorgaben mit Gespeichertem überlagern, verschachtelt.

    Wichtig für Updates: Eine neue Einstellung taucht dadurch auch in einer
    alten konfig.json auf, statt zu fehlen. Listen werden ersetzt, nicht
    vereint – bei der Melderliste wäre alles andere ein Ratespiel.
    """
    out = json.loads(json.dumps(basis))
    for schluessel, wert in (ueberlagerung or {}).items():
        if isinstance(wert, dict) and isinstance(out.get(schluessel), dict):
            out[schluessel] = _vereinen(out[schluessel], wert)
        else:
            out[schluessel] = wert
    return out


store = Store()
