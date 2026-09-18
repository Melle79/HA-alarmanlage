"""Rauch, Gas, Kohlenmonoxid und Hitze sind eine Linie, aber nicht dasselbe."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from basis import AnlagenTest  # noqa: E402


class Arten(AnlagenTest):

    def test_die_geraeteklasse_entscheidet_die_art(self):
        for klasse, erwartet in (("smoke", "rauch"), ("gas", "gas"),
                                 ("carbon_monoxide", "kohlenmonoxid"),
                                 ("heat", "hitze")):
            self.setze("binary_sensor." + klasse, "off", device_class=klasse)
        arten = {k["entity_id"]: k["art"] for k in self.ha.melderkandidaten()}
        self.assertEqual(arten["binary_sensor.smoke"], "rauch")
        self.assertEqual(arten["binary_sensor.gas"], "gas")
        self.assertEqual(arten["binary_sensor.carbon_monoxide"], "kohlenmonoxid")
        self.assertEqual(arten["binary_sensor.heat"], "hitze")


class Meldetexte(AnlagenTest):
    """Wer nachts geweckt wird und „Rauch" liest, sucht nach dem Falschen,
    wenn es Kohlenmonoxid war – das riecht man nicht und sieht man nicht."""

    def setUp(self):
        super().setUp()
        self.store.set("eskalation", "rauch", "alarm", "push",
                       ["notify.mobile_app_test"])

    def _text(self):
        return self.dienste_mit("notify.mobile_app_test")[0][1]["message"]

    def test_kohlenmonoxid_meldet_kohlenmonoxid(self):
        self.melder_anlegen("binary_sensor.co", art="kohlenmonoxid",
                            linie="rauch", ort="Wohnzimmer")
        self.ereignis("binary_sensor.co", "on")
        self.assertIn("Kohlenmonoxid", self._text())
        self.assertNotIn("Rauch", self._text())

    def test_gas_meldet_gas(self):
        self.melder_anlegen("binary_sensor.gas", art="gas", linie="rauch",
                            ort="Keller")
        self.ereignis("binary_sensor.gas", "on")
        self.assertIn("Gas", self._text())

    def test_rauch_bleibt_rauch(self):
        self.melder_anlegen("binary_sensor.rm", art="rauch", linie="rauch",
                            ort="Keller")
        self.ereignis("binary_sensor.rm", "on")
        self.assertIn("Rauch", self._text())

    def test_der_eigene_satz_des_melders_schlaegt_auch_die_art(self):
        self.melder_anlegen("binary_sensor.co", art="kohlenmonoxid",
                            linie="rauch", ort="Wohnzimmer",
                            text="Sofort lüften und das Haus verlassen!")
        self.ereignis("binary_sensor.co", "on")
        self.assertEqual(self._text(), "Sofort lüften und das Haus verlassen!")

    def test_ein_eingestellter_satz_der_stufe_schlaegt_die_art(self):
        """Was der Benutzer an der Stufe eingestellt hat, gilt – sonst
        überschriebe ein Update seine Einstellung."""
        self.store.set("eskalation", "rauch", "alarm", "text",
                       "Gefahr in {ort}!")
        self.melder_anlegen("binary_sensor.co", art="kohlenmonoxid",
                            linie="rauch", ort="Wohnzimmer")
        self.ereignis("binary_sensor.co", "on")
        self.assertEqual(self._text(), "Gefahr in Wohnzimmer!")


class Verfeinerung(AnlagenTest):

    def test_alte_rauchmelder_werden_genauer_eingeordnet(self):
        """Bis 1.7.4 fiel alles unter „rauch". Die Geräteklasse weiß es
        genauer, und der Unterschied steht am Ende in der Meldung."""
        self.melder_anlegen("binary_sensor.co", art="rauch", linie="rauch")
        self.melder_anlegen("binary_sensor.rm", art="rauch", linie="rauch")
        # Nach melder_anlegen: Es setzt den Zustand neu und löscht dabei
        # die Geräteklasse wieder.
        self.setze("binary_sensor.co", "off", device_class="carbon_monoxide")
        self.setze("binary_sensor.rm", "off", device_class="smoke")

        import uebernahme
        self.assertEqual(uebernahme.arten_verfeinern(), 1)
        arten = {m["entity"]: m["art"] for m in self.store.melder()}
        self.assertEqual(arten["binary_sensor.co"], "kohlenmonoxid")
        self.assertEqual(arten["binary_sensor.rm"], "rauch")

    def test_die_linie_bleibt_unberuehrt(self):
        """Verfeinert wird die Art, nicht das Verhalten."""
        self.melder_anlegen("binary_sensor.co", art="rauch", linie="rauch")
        self.setze("binary_sensor.co", "off", device_class="carbon_monoxide")
        import uebernahme
        uebernahme.arten_verfeinern()
        self.assertEqual(self.store.melder()[0]["linie"], "rauch")

    def test_zweimal_aufrufen_aendert_nichts_mehr(self):
        self.melder_anlegen("binary_sensor.co", art="rauch", linie="rauch")
        self.setze("binary_sensor.co", "off", device_class="carbon_monoxide")
        import uebernahme
        uebernahme.arten_verfeinern()
        self.assertEqual(uebernahme.arten_verfeinern(), 0)


if __name__ == "__main__":
    unittest.main()
