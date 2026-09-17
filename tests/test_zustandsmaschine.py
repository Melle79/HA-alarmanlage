"""Scharf, entschärft und die Wege dazwischen."""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from basis import AnlagenTest  # noqa: E402


class Scharfschalten(AnlagenTest):

    def test_ausgehverzoegerung_laeuft_und_endet(self):
        self.store.set("modi", "abwesend", "ausgehzeit", 60)
        self.anlage.scharf_schalten("abwesend")
        self.assertEqual(self.anlage.panel, "arming")

        # Die Frist vorspulen, statt eine Minute zu warten.
        self.store.z_set(frist=time.time() - 1)
        self.anlage._fristen_pruefen()
        self.assertEqual(self.anlage.panel, "armed_away")

    def test_ohne_ausgehzeit_sofort_scharf(self):
        self.store.set("modi", "abwesend", "ausgehzeit", 0)
        self.anlage.scharf_schalten("abwesend")
        self.assertEqual(self.anlage.panel, "armed_away")

    def test_wiederholung_startet_die_verzoegerung_nicht_neu(self):
        """Sonst käme die Anlage nie scharf.

        Der Takt ruft das Scharfschalten wieder und wieder auf. Setzte
        jeder Aufruf die Frist neu, liefe die Ausgehverzögerung ewig von
        vorn los und die Anlage stünde dauerhaft auf "schaltet scharf".
        """
        self.store.set("modi", "abwesend", "ausgehzeit", 60)
        self.anlage.scharf_schalten("abwesend")
        erste_frist = self.store.z_get("frist")
        time.sleep(0.01)
        self.anlage.scharf_schalten("abwesend")
        self.assertEqual(erste_frist, self.store.z_get("frist"))

    def test_nie_scharf_wenn_jemand_da_ist(self):
        """Der Rettungsanker gegen jede falsche Abwesenheitsmeldung."""
        self.store.set("scharfschaltung", "personen", ["person.sven"])
        self.setze("person.sven", "home")
        ergebnis = self.anlage.scharf_schalten("abwesend")
        self.assertFalse(ergebnis["ok"])
        self.assertEqual(ergebnis["grund"], "jemand_da")
        self.assertEqual(self.anlage.panel, "disarmed")

    def test_unterwegs_zaehlt_nicht_als_zuhause(self):
        """Nur 'home' zählt – eine Standzone ist kein Zuhause."""
        self.store.set("scharfschaltung", "personen", ["person.sven"])
        self.setze("person.sven", "StatZon1")
        self.assertTrue(self.anlage.scharf_schalten("abwesend")["ok"])

    def test_offene_kontakte_koennen_das_schaerfen_verhindern(self):
        self.store.set("vorpruefung", "offene_kontakte", "verhindern")
        self.melder_anlegen("binary_sensor.fenster", art="kontakt")
        self.setze("binary_sensor.fenster", "on")
        ergebnis = self.anlage.scharf_schalten("abwesend")
        self.assertFalse(ergebnis["ok"])
        self.assertEqual(ergebnis["grund"], "offene_kontakte")

    def test_offene_kontakte_ueberbruecken(self):
        self.store.set("vorpruefung", "offene_kontakte", "ueberbruecken")
        melder = self.melder_anlegen("binary_sensor.fenster", art="kontakt")
        self.setze("binary_sensor.fenster", "on")
        self.assertTrue(self.anlage.scharf_schalten("abwesend")["ok"])
        self.assertIn(melder["id"], self.store.z_get("ueberbrueckt"))

    def test_ueberbrueckung_endet_beim_entschaerfen(self):
        self.store.z_set(ueberbrueckt=["irgendwas"])
        self.anlage.scharf_schalten("abwesend")
        self.anlage.entschaerfen()
        self.assertEqual(self.store.z_get("ueberbrueckt"), [])


class Auslosen(AnlagenTest):

    def test_melder_im_entschaerften_zustand_tut_nichts(self):
        self.melder_anlegen("binary_sensor.bwm")
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.anlage.panel, "disarmed")

    def test_sofortmelder_loest_sofort_aus(self):
        self.melder_anlegen("binary_sensor.bwm", verzoegert=False)
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.anlage.panel, "triggered")

    def test_verzoegerter_melder_geht_ueber_pending(self):
        self.store.set("modi", "abwesend", "eintrittszeit", 45)
        self.melder_anlegen("binary_sensor.bwm", verzoegert=True)
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.anlage.panel, "pending")

        self.store.z_set(frist=time.time() - 1)
        self.anlage._fristen_pruefen()
        self.assertEqual(self.anlage.panel, "triggered")

    def test_wer_rechtzeitig_entschaerft_bekommt_keinen_alarm(self):
        self.store.set("modi", "abwesend", "eintrittszeit", 45)
        self.melder_anlegen("binary_sensor.bwm", verzoegert=True)
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.gerufen.clear()
        self.anlage.entschaerfen()
        self.assertEqual(self.anlage.panel, "disarmed")
        self.assertEqual(self.dienste_mit("notify.mobile"), [])

    def test_ausloeser_wird_sofort_festgehalten(self):
        """Nicht erst beim Alarm.

        Bis die Eintrittsverzögerung abgelaufen ist, hat längst ein
        zweiter Melder angesprochen – der überschriebe den ersten, und im
        Protokoll stünde der falsche.
        """
        self.store.set("modi", "abwesend", "eintrittszeit", 45)
        self.melder_anlegen("binary_sensor.erster", verzoegert=True)
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.erster", "on")
        self.assertIn("binary_sensor.erster", self.store.z_get("ausloeser"))

    def test_melder_gilt_nur_in_seinen_modi(self):
        self.melder_anlegen("binary_sensor.nur_urlaub", modi=["urlaub"])
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.nur_urlaub", "on")
        self.assertEqual(self.anlage.panel, "armed_away")

        self.anlage.entschaerfen()
        self.anlage.scharf_schalten("urlaub", sofort=True)
        self.ereignis("binary_sensor.nur_urlaub", "off")
        self.ereignis("binary_sensor.nur_urlaub", "on")
        self.assertEqual(self.anlage.panel, "triggered")

    def test_leere_modusliste_heisst_in_allen(self):
        self.melder_anlegen("binary_sensor.ueberall", modi=[])
        self.anlage.scharf_schalten("nacht", sofort=True)
        self.ereignis("binary_sensor.ueberall", "on")
        self.assertEqual(self.anlage.panel, "triggered")

    def test_abgeschalteter_melder_loest_nicht_aus(self):
        self.melder_anlegen("binary_sensor.aus", aktiv=False)
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.aus", "on")
        self.assertEqual(self.anlage.panel, "armed_away")

    def test_ueberbrueckter_melder_loest_nicht_aus(self):
        melder = self.melder_anlegen("binary_sensor.bwm")
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.anlage.ueberbruecken(melder["id"], True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.anlage.panel, "armed_away")

    def test_nach_der_ausloesezeit_wieder_scharf(self):
        self.store.set("linien", "einbruch", "ausloesezeit", 300)
        self.melder_anlegen("binary_sensor.bwm")
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.anlage.panel, "triggered")
        self.store.z_set(frist=time.time() - 1)
        self.anlage._fristen_pruefen()
        self.assertEqual(self.anlage.panel, "armed_away")

    def test_ausloesezeit_null_bleibt_ausgeloest(self):
        self.store.set("linien", "einbruch", "ausloesezeit", 0)
        self.melder_anlegen("binary_sensor.bwm")
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertIsNone(self.store.z_get("frist"))
        self.anlage._fristen_pruefen()
        self.assertEqual(self.anlage.panel, "triggered")


class NeustartUeberlebt(AnlagenTest):

    def test_scharfer_zustand_ueberlebt_den_neustart(self):
        """Sonst steht das Haus nach jedem Update unscharf da."""
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.store.laden()
        self.assertEqual(self.store.z_get("panel"), "armed_away")
        self.assertEqual(self.store.z_get("modus"), "abwesend")


if __name__ == "__main__":
    unittest.main()
