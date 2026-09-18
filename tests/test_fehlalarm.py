"""Zwei Werkzeuge gegen Fehlalarme – und wogegen sie jeweils helfen."""

import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from basis import AnlagenTest  # noqa: E402


class Ruhequelle(AnlagenTest):
    """Der Fall vom 18.09.2026.

    Der Präsenzmelder im Büro sprang vier Morgen hintereinander um 08:30 an,
    immer genau vier Sekunden nachdem das Rollo im selben Zimmer auffuhr.
    Am vierten Morgen war das Haus leer – und die Anlage alarmierte.

    Das ist keine Unzuverlässigkeit des Melders, sondern eine bekannte
    Ursache. Gegen bekannte Ursachen hilft kein Zeitfilter, sondern Wissen.
    """

    def setUp(self):
        super().setUp()
        self.store.set("eskalation", "einbruch", "alarm", "push",
                       ["notify.mobile_app_test"])
        self.melder = self.melder_anlegen(
            "binary_sensor.praesenz_buero", ort="Büro",
            ruhe_bei=["cover.rollo_buero"], ruhe_sekunden=120)

    def _rollo_fuhr_vor(self, sekunden):
        self.zustaende["cover.rollo_buero"] = {
            "entity_id": "cover.rollo_buero", "state": "open",
            "attributes": {"friendly_name": "Rollo Büro"},
            "last_changed": (datetime.now(timezone.utc)
                             - timedelta(seconds=sekunden)).isoformat(),
        }

    def test_kein_alarm_waehrend_das_rollo_faehrt(self):
        self._rollo_fuhr_vor(4)
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.praesenz_buero", "on")
        self.assertEqual(self.anlage.panel, "armed_away")
        self.assertEqual(self.dienste_mit("notify.mobile_app_test"), [])

    def test_die_unterdrueckung_steht_im_protokoll(self):
        """Übergangen werden darf sie, verschwiegen nicht."""
        self._rollo_fuhr_vor(4)
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.praesenz_buero", "on")
        eintraege = self.protokoll.lesen(20, art="beruhigt")
        self.assertEqual(len(eintraege), 1)
        self.assertIn("Rollo Büro", eintraege[0]["text"])

    def test_nach_der_ruhezeit_zaehlt_er_wieder(self):
        """Sonst wäre das Büro nach jedem Rollofahren dauerhaft blind."""
        self._rollo_fuhr_vor(300)
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.praesenz_buero", "on")
        self.assertEqual(self.anlage.panel, "triggered")

    def test_ohne_ruhequelle_aendert_sich_nichts(self):
        anderer = self.melder_anlegen("binary_sensor.bwm_flur", ort="Flur")
        self.assertEqual(anderer.get("ruhe_bei"), None)
        self._rollo_fuhr_vor(4)
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm_flur", "on")
        self.assertEqual(self.anlage.panel, "triggered")


class Mindestdauer(AnlagenTest):
    """Gegen kurze Zucker unbekannter Ursache."""

    def setUp(self):
        super().setUp()
        self.store.set("eskalation", "einbruch", "alarm", "push",
                       ["notify.mobile_app_test"])
        self.melder_anlegen("binary_sensor.bwm", ort="Flur", mindestdauer=30)

    def test_ein_kurzer_ausschlag_loest_nicht_aus(self):
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.anlage.panel, "armed_away")
        self.ereignis("binary_sensor.bwm", "off")
        self.anlage._wartende_pruefen()
        self.assertEqual(self.anlage.panel, "armed_away")

    def test_wer_anhaelt_loest_aus(self):
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        # Frist vorspulen, statt eine halbe Minute zu warten.
        for melder_id in self.anlage._wartende:
            self.anlage._wartende[melder_id] = time.time() - 1
        self.anlage._wartende_pruefen()
        self.assertEqual(self.anlage.panel, "triggered")

    def test_abfallen_und_wieder_anspringen_faengt_von_vorn_an(self):
        """Sonst summierte sich Flackern zur Mindestdauer auf."""
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        erste = dict(self.anlage._wartende)
        self.ereignis("binary_sensor.bwm", "off")
        self.assertEqual(self.anlage._wartende, {})
        self.ereignis("binary_sensor.bwm", "on")
        self.assertNotEqual(self.anlage._wartende, erste)

    def test_zaehlt_nur_wenn_es_immer_noch_anliegt(self):
        """Der Melder wird am Ende der Frist noch einmal gefragt."""
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        for melder_id in self.anlage._wartende:
            self.anlage._wartende[melder_id] = time.time() - 1
        # Er ist inzwischen ruhig, nur hat es niemand gemeldet.
        self.setze("binary_sensor.bwm", "off")
        self.anlage._wartende_pruefen()
        self.assertEqual(self.anlage.panel, "armed_away")

    def test_das_beobachten_steht_im_protokoll(self):
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertTrue(self.protokoll.lesen(20, art="beobachtet"))


if __name__ == "__main__":
    unittest.main()
