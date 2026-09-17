"""Der Hausmodus folgt der Anwesenheit – und wo er es nicht tut."""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from basis import AnlagenTest  # noqa: E402

PERSONEN = ["person.sven", "person.isabel", "person.finn"]


class Anwesenheit(AnlagenTest):

    def setUp(self):
        super().setUp()
        self.store.set("scharfschaltung", "personen", PERSONEN)
        self.store.set("scharfschaltung", "leer_sekunden", 300)
        for person in PERSONEN:
            self.setze(person, "not_home")

    def test_jemand_kommt_heim_und_der_modus_wird_zuhause(self):
        self.anlage.hausmodus_setzen("abwesend")
        self.setze("person.sven", "home")
        self.anlage._anwesenheit_auswerten()
        self.assertEqual(self.anlage.hausmodus, "zuhause")

    def test_erst_nach_der_frist_wird_abwesend(self):
        self.anlage.hausmodus_setzen("zuhause")
        self.anlage._anwesenheit_auswerten()   # startet die Frist
        self.assertEqual(self.anlage.hausmodus, "zuhause")
        self.anlage._leer_seit = time.time() - 400
        self.anlage._anwesenheit_auswerten()
        self.assertEqual(self.anlage.hausmodus, "abwesend")

    def test_der_handmodus_kippt_nicht_von_selbst(self):
        """Urlaub bleibt Urlaub, auch wenn einer kurz heimkommt.

        Sonst beendete ein einzelnes Heimkommen den Urlaubsmodus, und
        beim nächsten Weggehen stünde die Anlage in der falschen
        Betriebsart.
        """
        self.store.set("scharfschaltung", "handmodus", "urlaub")
        self.anlage.hausmodus_setzen("urlaub")
        self.setze("person.sven", "home")
        self.anlage._anwesenheit_auswerten()
        self.assertEqual(self.anlage.hausmodus, "urlaub")

    def test_kein_scharfschalten_bei_anwesenheit_trotz_falschem_modus(self):
        """Der Fall, der einmal eine ganze Familie im Schlaf scharf
        geschaltet hat: Der Hausmodus stand fälschlich auf Abwesend,
        während alle fünf im Haus waren."""
        self.setze("person.sven", "home")
        self.store.z_set(hausmodus="abwesend")
        self.anlage._sollzustand_durchsetzen()
        self.assertEqual(self.anlage.panel, "disarmed")

    def test_zuhause_entschaerft(self):
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.anlage.hausmodus_setzen("zuhause")
        self.assertEqual(self.anlage.panel, "disarmed")

    def test_scharfschalten_zieht_den_hausmodus_mit(self):
        """Sonst entschärft der Takt zehn Sekunden später wieder."""
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.assertEqual(self.anlage.hausmodus, "abwesend")
        self.anlage._sollzustand_durchsetzen()
        self.assertEqual(self.anlage.panel, "armed_away")

    def test_entschaerfen_von_hand_bleibt_entschaerft(self):
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.anlage.entschaerfen("oberflaeche", auch_hausmodus=True)
        self.anlage._sollzustand_durchsetzen()
        self.assertEqual(self.anlage.panel, "disarmed")

    def test_ohne_automatik_bleibt_alles_stehen(self):
        self.store.set("betrieb", "automatik", False)
        self.store.z_set(hausmodus="abwesend")
        self.anlage._sollzustand_durchsetzen()
        self.assertEqual(self.anlage.panel, "disarmed")

    def test_von_hand_geht_auch_ohne_automatik(self):
        self.store.set("betrieb", "automatik", False)
        self.assertTrue(self.anlage.scharf_schalten("abwesend", sofort=True)["ok"])

    def test_nur_von_hand_laesst_die_anwesenheit_liegen(self):
        self.store.set("scharfschaltung", "quelle", "nur_hand")
        self.anlage.hausmodus_setzen("abwesend")
        self.setze("person.sven", "home")
        self.anlage._anwesenheit_auswerten()
        self.assertEqual(self.anlage.hausmodus, "abwesend")

    def test_waehrend_der_ausgehverzoegerung_zaehlt_kein_melder(self):
        """Wer das Haus verlässt, läuft am eigenen Bewegungsmelder vorbei."""
        self.melder_anlegen("binary_sensor.bwm")
        self.store.set("modi", "abwesend", "ausgehzeit", 60)
        self.anlage.scharf_schalten("abwesend")
        self.assertEqual(self.anlage.panel, "arming")
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.anlage.panel, "arming")

    def test_ein_laufender_alarm_wird_vom_takt_nicht_uebergangen(self):
        """Sonst schaltete der Takt den Alarm weg, während er läuft."""
        self.melder_anlegen("binary_sensor.bwm")
        self.store.set("modi", "abwesend", "ausgehzeit", 0)
        self.anlage.hausmodus_setzen("abwesend")
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.anlage.panel, "triggered")
        self.anlage._sollzustand_durchsetzen()
        self.assertEqual(self.anlage.panel, "triggered")


if __name__ == "__main__":
    unittest.main()
