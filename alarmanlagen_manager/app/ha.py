"""Zugriff auf Home Assistant über den Supervisor-Proxy.

Gelesen wird über REST, gehandelt ebenfalls. Die *Ereignisse* der Melder
kommen dagegen über WebSocket (siehe ``ereignisse.py``) – eine Alarmanlage,
die alle zwei Sekunden nachfragt, ist keine.
"""

import logging
import os
import time

import requests

log = logging.getLogger("alarm.ha")

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
CORE_API = "http://supervisor/core/api"
TIMEOUT = 10

# Zustandsliste: ändert sich ständig, wird aber nur für die Auswahllisten
# der Oberfläche gebraucht. Ein paar Sekunden Alter schaden dort nicht.
STATES_TTL = 5
_states_cache: tuple[float, list] = (0.0, [])

# Geräteklassen, die als Einbruchmelder taugen.
BEWEGUNG = {"motion", "occupancy", "presence"}
KONTAKT = {"door", "window", "opening", "garage_door"}
ERSCHUETTERUNG = {"vibration", "tamper"}
RAUCH = {"smoke", "gas", "carbon_monoxide", "heat"}
WASSER = {"moisture"}


def verfuegbar() -> bool:
    return bool(SUPERVISOR_TOKEN)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }


def zustaende(erzwingen: bool = False) -> list:
    global _states_cache
    alter, gespeichert = _states_cache
    if not erzwingen and gespeichert and time.time() - alter < STATES_TTL:
        return gespeichert
    if not verfuegbar():
        return []
    try:
        antwort = requests.get(f"{CORE_API}/states", headers=_headers(),
                               timeout=TIMEOUT)
        antwort.raise_for_status()
        daten = antwort.json()
    except (requests.RequestException, ValueError) as err:
        log.warning("Home Assistant nicht erreichbar: %s", err)
        return gespeichert
    _states_cache = (time.time(), daten)
    return daten


def zustand(entity_id: str) -> dict | None:
    """Einzelner Zustand, immer frisch.

    Bewusst ohne Zwischenspeicher: Hieran hängt die Frage, ob ein Melder
    ausgelöst hat.
    """
    if not verfuegbar():
        return None
    try:
        antwort = requests.get(f"{CORE_API}/states/{entity_id}",
                               headers=_headers(), timeout=TIMEOUT)
        if antwort.status_code == 404:
            return None
        antwort.raise_for_status()
        return antwort.json()
    except (requests.RequestException, ValueError) as err:
        log.warning("Zustand von %s nicht lesbar: %s", entity_id, err)
        return None


def ist_zustand(entity_id: str, *werte: str) -> bool:
    eintrag = zustand(entity_id)
    return bool(eintrag and eintrag.get("state") in werte)


def dienst(bereich: str, dienstname: str, daten: dict | None = None) -> bool:
    """Einen Dienst aufrufen. Gibt zurück, ob es geklappt hat."""
    if not verfuegbar():
        return False
    try:
        antwort = requests.post(
            f"{CORE_API}/services/{bereich}/{dienstname}",
            headers=_headers(), json=daten or {}, timeout=TIMEOUT,
        )
        antwort.raise_for_status()
        return True
    except requests.RequestException as err:
        log.warning("Dienst %s.%s fehlgeschlagen: %s", bereich, dienstname, err)
        return False


def dienste() -> dict:
    """Alle Dienste – gebraucht für die Liste der Meldewege."""
    if not verfuegbar():
        return {}
    try:
        antwort = requests.get(f"{CORE_API}/services", headers=_headers(),
                               timeout=TIMEOUT)
        antwort.raise_for_status()
        return {eintrag["domain"]: eintrag.get("services", {})
                for eintrag in antwort.json()}
    except (requests.RequestException, ValueError, KeyError) as err:
        log.warning("Dienstliste nicht lesbar: %s", err)
        return {}


# ------------------------------------------------------------ Auswahllisten

def _name(eintrag: dict) -> str:
    attrs = eintrag.get("attributes", {})
    return attrs.get("friendly_name") or eintrag.get("entity_id", "")


def melderkandidaten(eigener_praefix: str = "") -> list:
    """Alle binary_sensor, nach Art vorsortiert.

    Der Vorschlag ist eine Hilfe, kein Urteil: Ein Melder ohne Geräteklasse
    landet unter "sonstige" und wird von Hand zugeordnet.

    Die **eigenen** Sensoren fliegen raus. Das Add-on veröffentlicht selbst
    einen Rauch-, einen Wasser- und einen Kontaktsensor; die als Melder
    anzubieten, ergäbe eine Schleife - der Sammelsensor würde zum Melder
    für sich selbst.
    """
    out = []
    eigene = f"binary_sensor.{eigener_praefix}_" if eigener_praefix else None
    for eintrag in zustaende():
        eid = eintrag.get("entity_id", "")
        if not eid.startswith("binary_sensor."):
            continue
        if eigene and eid.startswith(eigene):
            continue
        klasse = eintrag.get("attributes", {}).get("device_class")
        if klasse in BEWEGUNG:
            art = "bewegung"
        elif klasse in KONTAKT:
            art = "kontakt"
        elif klasse in ERSCHUETTERUNG:
            art = "erschuetterung"
        elif klasse in RAUCH:
            art = "rauch"
        elif klasse in WASSER:
            art = "wasser"
        else:
            art = "sonstige"
        out.append({
            "entity_id": eid,
            "name": _name(eintrag),
            "art": art,
            "device_class": klasse,
            "zustand": eintrag.get("state"),
            "bereich": eintrag.get("attributes", {}).get("area_id"),
        })
    out.sort(key=lambda e: (e["art"], e["name"].lower()))
    return out


def entitaeten(*praefixe: str) -> list:
    out = []
    for eintrag in zustaende():
        eid = eintrag.get("entity_id", "")
        if eid.startswith(praefixe):
            out.append({
                "entity_id": eid,
                "name": _name(eintrag),
                "zustand": eintrag.get("state"),
            })
    out.sort(key=lambda e: e["name"].lower())
    return out


def meldewege() -> dict:
    """Push-Ziele, Sprachausgaben und der Rest – aus den notify-Diensten."""
    alle = dienste().get("notify", {})
    push, sprache, sonstige = [], [], []
    for name in sorted(alle):
        voll = f"notify.{name}"
        if name.startswith("mobile_app_"):
            push.append({"dienst": voll, "name": _lesbar(name[11:])})
        elif name.startswith(("alexa_media", "google_assistant", "tts")):
            sprache.append({"dienst": voll, "name": _lesbar(name)})
        elif name in ("notify", "persistent_notification", "send_message"):
            continue
        else:
            sonstige.append({"dienst": voll, "name": _lesbar(name)})
    return {"push": push, "sprache": sprache, "sonstige": sonstige}


def _lesbar(name: str) -> str:
    return name.replace("alexa_media_", "").replace("_", " ").strip().title()


# Bereiche ändern sich so gut wie nie, das Template läuft aber über ein
# paar tausend Entitäten. Einmal je Viertelstunde reicht.
BEREICHE_TTL = 900
_bereiche_cache: tuple[float, dict] = (0.0, {})

# Wovon der Bereich gebraucht wird: Melder (für den Ort in der Ansage) und
# alles, was in den Meldewegen zur Auswahl steht.
BEREICH_DOMAENEN = ("binary_sensor", "light", "switch", "siren", "lock",
                    "media_player", "sensor")


def bereiche(erzwingen: bool = False) -> dict:
    """entity_id -> Bereichsname, über die Template-Schnittstelle.

    Es gibt keine REST-Schnittstelle für das Entitätsregister; das Template
    ist der offizielle Weg dorthin.
    """
    global _bereiche_cache
    alter, gespeichert = _bereiche_cache
    if not erzwingen and gespeichert and time.time() - alter < BEREICHE_TTL:
        return gespeichert
    if not verfuegbar():
        return {}
    domaenen = ",".join(f"'{d}'" for d in BEREICH_DOMAENEN)
    vorlage = (
        "{% set ns = namespace(o=[]) %}"
        f"{{% for s in states if s.domain in [{domaenen}] %}}"
        "{% set a = area_name(s.entity_id) %}"
        "{% if a %}{% set ns.o = ns.o + [s.entity_id ~ '|' ~ a] %}{% endif %}"
        "{% endfor %}{{ ns.o | join('\\n') }}"
    )
    try:
        antwort = requests.post(f"{CORE_API}/template", headers=_headers(),
                                json={"template": vorlage}, timeout=TIMEOUT)
        antwort.raise_for_status()
    except requests.RequestException as err:
        log.warning("Bereiche nicht lesbar: %s", err)
        return {}
    out = {}
    # Selbst entschlüsseln statt .text: Die Template-Schnittstelle liefert
    # text/plain ohne Zeichensatz, und requests fällt dann auf ISO-8859-1
    # zurück. Aus "Küche" würde "KÃ¼che" - und genau das läse hinterher
    # ein Lautsprecher vor.
    for zeile in antwort.content.decode("utf-8", "replace").splitlines():
        if "|" in zeile:
            eid, bereich = zeile.split("|", 1)
            out[eid.strip()] = bereich.strip()
    if out:
        _bereiche_cache = (time.time(), out)
    return out
