"""Die Dashboard-Karte ausliefern und bei Home Assistant anmelden.

Zwei Schritte, die sonst der Benutzer von Hand macht:
  1. Die Kartendatei nach /config/www kopieren, damit sie unter /local/
     erreichbar ist.
  2. Sie als Lovelace-Ressource registrieren, damit das Dashboard sie lädt.

Der zweite Schritt geht nur über die WebSocket-API – für Ressourcen gibt es
keine REST-Schnittstelle. Schlägt er fehl, ist das kein Beinbruch: die Datei
liegt dann trotzdem bereit und lässt sich von Hand eintragen. Der Hinweis
dazu steht im Protokoll.
"""

import json
import logging
import os
import shutil
from pathlib import Path

log = logging.getLogger("alarm.lovelace")

WWW_DIR = Path(os.environ.get("WWW_DIR", "/www"))
CONFIG_WWW = Path(os.environ.get("HA_WWW_DIR", "/config/www"))
KARTEN_DATEI = "alarmanlage-card.js"
RESSOURCE_URL = f"/local/{KARTEN_DATEI}"

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
WS_URL = "ws://supervisor/core/websocket"


def karte_bereitstellen(version: str = "") -> bool:
    """Karte nach /config/www kopieren. True, wenn sie dort liegt."""
    quelle = WWW_DIR / "card.js"
    if not quelle.is_file():
        log.warning("Kartendatei fehlt: %s", quelle)
        return False
    try:
        CONFIG_WWW.mkdir(parents=True, exist_ok=True)
        ziel = CONFIG_WWW / KARTEN_DATEI
        shutil.copyfile(quelle, ziel)
        log.info("Dashboard-Karte bereitgestellt: %s", ziel)
        return True
    except OSError as err:
        log.warning("Karte nicht kopierbar: %s", err)
        return False


def ressource_anmelden(version: str = "") -> str:
    """Die Karte als Lovelace-Ressource eintragen.

    Gibt zurück, was passiert ist: 'vorhanden', 'angelegt', 'aktualisiert'
    oder 'fehlgeschlagen'.
    """
    if not SUPERVISOR_TOKEN:
        return "fehlgeschlagen"
    try:
        import websocket  # noqa: PLC0415 – nur hier gebraucht
    except ImportError:
        log.warning("websocket-client fehlt – Ressource nicht anmeldbar")
        return "fehlgeschlagen"

    # Versionsanhang, damit der Browser eine neue Karte nicht aus dem
    # Zwischenspeicher bedient.
    gewuenscht = f"{RESSOURCE_URL}?v={version}" if version else RESSOURCE_URL

    try:
        ws = websocket.create_connection(WS_URL, timeout=15)
    except Exception as err:  # noqa: BLE001
        log.warning("WebSocket zu Home Assistant nicht erreichbar: %s", err)
        return "fehlgeschlagen"

    try:
        ws.recv()  # auth_required
        ws.send(json.dumps({"type": "auth", "access_token": SUPERVISOR_TOKEN}))
        antwort = json.loads(ws.recv())
        if antwort.get("type") != "auth_ok":
            log.warning("Anmeldung an der WebSocket-API abgelehnt")
            return "fehlgeschlagen"

        ws.send(json.dumps({"id": 1, "type": "lovelace/resources"}))
        liste = json.loads(ws.recv())
        if not liste.get("success"):
            return "fehlgeschlagen"

        vorhandene = liste.get("result", [])
        treffer = next(
            (r for r in vorhandene
             if str(r.get("url", "")).split("?")[0] == RESSOURCE_URL),
            None,
        )

        if treffer and treffer.get("url") == gewuenscht:
            return "vorhanden"

        if treffer:
            ws.send(json.dumps({
                "id": 2, "type": "lovelace/resources/update",
                "resource_id": treffer["id"],
                "url": gewuenscht, "res_type": "module",
            }))
            ergebnis = json.loads(ws.recv())
            return "aktualisiert" if ergebnis.get("success") else "fehlgeschlagen"

        ws.send(json.dumps({
            "id": 2, "type": "lovelace/resources/create",
            "url": gewuenscht, "res_type": "module",
        }))
        ergebnis = json.loads(ws.recv())
        return "angelegt" if ergebnis.get("success") else "fehlgeschlagen"
    except Exception as err:  # noqa: BLE001
        log.warning("Ressource nicht anmeldbar: %s", err)
        return "fehlgeschlagen"
    finally:
        try:
            ws.close()
        except Exception:  # noqa: BLE001
            pass


def einrichten(version: str = "") -> None:
    """Beides zusammen, mit verständlicher Meldung im Protokoll."""
    if not karte_bereitstellen(version):
        return
    ergebnis = ressource_anmelden(version)
    if ergebnis == "fehlgeschlagen":
        log.warning(
            "Dashboard-Karte liegt unter %s, konnte aber nicht automatisch "
            "eingetragen werden. Von Hand: Einstellungen -> Dashboards -> "
            "Ressourcen -> '%s' als JavaScript-Modul hinzufuegen.",
            CONFIG_WWW / KARTEN_DATEI, RESSOURCE_URL,
        )
    else:
        log.info("Dashboard-Karte als Lovelace-Ressource %s", ergebnis)
