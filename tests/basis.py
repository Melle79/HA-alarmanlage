"""Gemeinsames Gerüst für die Tests.

Home Assistant wird nicht nachgebaut, sondern ersetzt: Die Tests setzen
Zustände direkt und lesen mit, welche Dienste gerufen worden wären. Was
geprüft wird, ist die Anlage – nicht die Kiste, auf der sie läuft.
"""

import os
import shutil
import sys
import tempfile
import unittest

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "alarmanlagen_manager", "app")


class AnlagenTest(unittest.TestCase):
    """Jeder Test bekommt ein frisches /data und eine frische Anlage."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="alarmtest-")
        os.environ["DATA_DIR"] = self.tmp
        if APP not in sys.path:
            sys.path.insert(0, APP)
        # Die Module halten Zustand in Modulvariablen. Sie müssen deshalb
        # je Test neu geladen werden, sonst trägt der zweite Test die
        # Konfiguration des ersten mit sich herum.
        for name in ("store", "protokoll", "eskalation", "anlage",
                     "ereignisse", "ha", "uebernahme"):
            sys.modules.pop(name, None)

        import ha
        import store as store_modul
        import protokoll

        self.ha = ha
        self.zustaende = {}
        self.gerufen = []

        def zustand(entity_id):
            return self.zustaende.get(entity_id)

        def dienst(bereich, name, daten=None):
            self.gerufen.append((f"{bereich}.{name}", daten or {}))
            return True

        ha.zustand = zustand
        ha.dienst = dienst
        ha.zustaende = lambda erzwingen=False: list(self.zustaende.values())
        ha.verfuegbar = lambda: True

        import anlage as anlage_modul
        self.store = store_modul.store
        self.protokoll = protokoll
        self.anlage = anlage_modul.anlage
        self.neue_id = store_modul.neue_id

        # Trockenlauf aus: Die Tests wollen sehen, was hinausginge.
        self.store.set("betrieb", "trockenlauf", False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------ Hilfen

    def setze(self, entity_id, zustand, **attribute):
        from datetime import datetime, timezone
        self.zustaende[entity_id] = {
            "entity_id": entity_id,
            "state": zustand,
            "attributes": {"friendly_name": entity_id, **attribute},
            "last_changed": datetime.now(timezone.utc).isoformat(),
        }

    def ereignis(self, entity_id, neu, alt=None):
        """Eine Zustandsänderung, so wie sie über WebSocket ankäme."""
        vorher = self.zustaende.get(entity_id, {}).get("state", alt)
        self.setze(entity_id, neu)
        self.anlage._melder_ereignis(
            entity_id,
            {"entity_id": entity_id, "state": vorher},
            {"entity_id": entity_id, "state": neu,
             "attributes": {"friendly_name": entity_id}},
        )

    def melder_anlegen(self, entity_id, **felder):
        eintrag = {
            "id": self.neue_id(),
            "entity": entity_id,
            "name": entity_id,
            "ort": entity_id,
            "art": "bewegung",
            "linie": "einbruch",
            "modi": [],
            "verzoegert": False,
            "ausloesezustand": "on",
            "aktiv": True,
        }
        eintrag.update(felder)
        liste = self.store.melder()
        liste.append(eintrag)
        self.store.melder_setzen(liste)
        self.setze(entity_id, "off")
        return eintrag

    def dienste_mit(self, praefix):
        return [(name, daten) for name, daten in self.gerufen
                if name.startswith(praefix)]
