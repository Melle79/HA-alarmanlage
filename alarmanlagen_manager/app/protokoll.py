"""Das Ereignisbuch der Anlage.

Bei einer Alarmanlage ist das Protokoll kein Beiwerk, sondern der einzige
Weg, hinterher zu beantworten, was eigentlich passiert ist. Es überlebt
deshalb den Neustart und wird nicht bei jedem Update geleert.

Geschrieben wird eine Zeile je Ereignis im JSON-Lines-Format: anhängen ist
ein einzelner Schreibvorgang, und eine halb geschriebene letzte Zeile
kostet ein Ereignis statt der ganzen Datei.
"""

import json
import logging
import os
import threading
import time
from pathlib import Path

log = logging.getLogger("alarm.protokoll")

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
DATEI = DATA_DIR / "protokoll.jsonl"

# Wie viele Zeilen aufgehoben werden. 5000 sind bei Svens Anlage mehrere
# Monate; darüber wird beim Start gekürzt.
HOECHSTZAHL = 5000

_lock = threading.Lock()


def schreiben(art: str, text: str, **felder) -> dict:
    """Ein Ereignis festhalten und zurückgeben.

    ``art`` ist ein Schlüssel, kein Satz – die Oberfläche übersetzt und
    färbt danach. ``text`` ist die Kurzfassung für Menschen.
    """
    eintrag = {"zeit": time.time(), "art": art, "text": text}
    eintrag.update(felder)
    with _lock:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with DATEI.open("a", encoding="utf-8") as datei:
                datei.write(json.dumps(eintrag, ensure_ascii=False) + "\n")
        except OSError as err:
            log.warning("Protokoll nicht schreibbar: %s", err)
    log.info("[%s] %s", art, text)
    return eintrag


def lesen(anzahl: int = 200, art: str | None = None) -> list:
    """Die jüngsten Einträge, neueste zuerst."""
    with _lock:
        if not DATEI.is_file():
            return []
        try:
            zeilen = DATEI.read_text(encoding="utf-8").splitlines()
        except OSError as err:
            log.warning("Protokoll nicht lesbar: %s", err)
            return []
    out = []
    for zeile in reversed(zeilen):
        if not zeile.strip():
            continue
        try:
            eintrag = json.loads(zeile)
        except ValueError:
            continue
        if art and eintrag.get("art") != art:
            continue
        out.append(eintrag)
        if len(out) >= anzahl:
            break
    return out


def kuerzen() -> None:
    """Beim Start auf HOECHSTZAHL zurückschneiden."""
    with _lock:
        if not DATEI.is_file():
            return
        try:
            zeilen = DATEI.read_text(encoding="utf-8").splitlines()
            if len(zeilen) <= HOECHSTZAHL:
                return
            rest = zeilen[-HOECHSTZAHL:]
            tmp = DATEI.with_suffix(".tmp")
            tmp.write_text("\n".join(rest) + "\n", encoding="utf-8")
            tmp.replace(DATEI)
            log.info("Protokoll auf %d Einträge gekürzt", HOECHSTZAHL)
        except OSError as err:
            log.warning("Protokoll nicht kürzbar: %s", err)
