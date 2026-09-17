"""Rauch und Wasser: die Linien, die rund um die Uhr gelten."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from basis import AnlagenTest  # noqa: E402


class Dauerlinien(AnlagenTest):

    def setUp(self):
        super().setUp()
        self.store.set("eskalation", "rauch", "alarm", "push",
                       ["notify.mobile_app_test"])
        self.store.set("eskalation", "rauch", "alarm", "alexa",
                       ["notify.alexa_media_kueche"])
        self.melder_anlegen("binary_sensor.rm_luna", art="rauch",
                            linie="rauch", ort="Lunas Zimmer")

    def test_rauch_meldet_auch_im_entschaerften_zustand(self):
        """Rauch kümmert es nicht, ob jemand zu Hause ist."""
        self.assertEqual(self.anlage.panel, "disarmed")
        self.ereignis("binary_sensor.rm_luna", "on")
        self.assertEqual(len(self.dienste_mit("notify.mobile_app_test")), 1)

    def test_rauch_ruehrt_das_bedienfeld_nicht_an(self):
        """Ein Rauchmelder im Kinderzimmer ist kein Einbruch.

        Andersherum: Wer die Einbruchanlage entschärft, hat damit nicht
        das Feuer gelöscht.
        """
        self.ereignis("binary_sensor.rm_luna", "on")
        self.assertEqual(self.anlage.panel, "disarmed")

    def test_der_ort_steht_in_der_ansage(self):
        self.ereignis("binary_sensor.rm_luna", "on")
        ansagen = self.dienste_mit("notify.alexa_media_kueche")
        self.assertEqual(len(ansagen), 1)
        self.assertIn("Lunas Zimmer", ansagen[0][1]["message"])
        self.assertEqual(ansagen[0][1]["data"]["type"], "tts")

    def test_ein_stehender_melder_meldet_nur_einmal(self):
        """Ein Rauchmelder, der zehn Minuten schreit, schickt sonst
        zehn Minuten lang Pushes."""
        for _ in range(4):
            self.anlage._melder_ausgeloest(self.store.melder()[0])
        self.assertEqual(len(self.dienste_mit("notify.mobile_app_test")), 1)

    def test_entwarnung_beim_zurueckgehen(self):
        self.store.set("eskalation", "rauch", "entwarnung", "aktiv", True)
        self.store.set("eskalation", "rauch", "entwarnung", "push",
                       ["notify.mobile_app_test"])
        self.ereignis("binary_sensor.rm_luna", "on")
        self.gerufen.clear()
        self.ereignis("binary_sensor.rm_luna", "off")
        meldungen = self.dienste_mit("notify.mobile_app_test")
        self.assertEqual(len(meldungen), 1)
        self.assertIn("Lunas Zimmer", meldungen[0][1]["message"])

    def test_quittieren_raeumt_die_offenen_alarme(self):
        self.ereignis("binary_sensor.rm_luna", "on")
        self.assertTrue(self.store.z_get("offene_alarme"))
        self.anlage.alarme_quittieren()
        self.assertEqual(self.store.z_get("offene_alarme"), {})

    def test_abgeschaltete_linie_meldet_nicht(self):
        self.store.set("linien", "rauch", "aktiv", False)
        self.ereignis("binary_sensor.rm_luna", "on")
        self.assertEqual(self.dienste_mit("notify."), [])


class Reihenfolge(AnlagenTest):

    def test_jede_linie_hat_eine_reihenfolge(self):
        """Die Anzeigereihenfolge darf nicht an der Schlüsselfolge hängen.

        Flask sortiert die JSON-Schlüssel alphabetisch. Wer sich darauf
        verlässt, bekommt den Voralarm hinter die Entwarnung sortiert –
        also hinter das, was er ankündigt.
        """
        for schluessel, linie in self.store.get("linien").items():
            self.assertIsInstance(linie.get("reihenfolge"), int, schluessel)

    def test_einbruch_steht_vorn(self):
        linien = self.store.get("linien")
        folge = sorted(linien, key=lambda k: linien[k]["reihenfolge"])
        self.assertEqual(folge[0], "einbruch")


class Trockenlauf(AnlagenTest):

    def setUp(self):
        super().setUp()
        self.store.set("betrieb", "trockenlauf", True)
        self.store.set("eskalation", "einbruch", "alarm", "push",
                       ["notify.mobile_app_test"])
        self.store.set("eskalation", "einbruch", "alarm", "alexa",
                       ["notify.alexa_media_kueche"])
        self.store.set("eskalation", "einbruch", "alarm", "licht",
                       ["light.flur"])
        self.melder_anlegen("binary_sensor.bwm")

    def test_im_trockenlauf_geht_nichts_hinaus(self):
        """Ein Add-on im Probebetrieb, das nachts zehn Lautsprecher zum
        Schreien bringt, wäre schlimmer als eines, das nichts tut."""
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.dienste_mit("notify.mobile_app_test"), [])
        self.assertEqual(self.dienste_mit("notify.alexa_media_kueche"), [])
        self.assertEqual(self.dienste_mit("light.turn_on"), [])

    def test_die_zustandsmaschine_laeuft_trotzdem(self):
        """Sonst ließe sich im Probebetrieb nicht prüfen, ob es gepasst hätte."""
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.anlage.panel, "triggered")

    def test_der_probebetrieb_hinterlaesst_eine_spur(self):
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertTrue(self.protokoll.lesen(50, art="probe"))
        hinweise = self.dienste_mit("persistent_notification.create")
        self.assertTrue(hinweise)
        self.assertIn("Probebetrieb", hinweise[0][1]["title"])


class Meldewege(AnlagenTest):

    def test_kritischer_push_traegt_die_apple_kennzeichnung(self):
        """Ohne sie bleibt die Meldung nachts im Fokusmodus liegen –
        genau dann, wenn sie gebraucht wird."""
        import eskalation
        self.store.set("eskalation", "einbruch", "alarm", "push",
                       ["notify.mobile_app_test"])
        self.store.set("eskalation", "einbruch", "alarm", "kritisch", True)
        eskalation.ausfuehren("einbruch", "alarm", ausloeser="Test")
        daten = self.dienste_mit("notify.mobile_app_test")[0][1]
        self.assertEqual(daten["data"]["push"]["sound"]["critical"], 1)

    def test_ohne_kritisch_kein_lauter_ton(self):
        import eskalation
        self.store.set("eskalation", "einbruch", "entwarnung", "push",
                       ["notify.mobile_app_test"])
        eskalation.ausfuehren("einbruch", "entwarnung", ausloeser="Test")
        daten = self.dienste_mit("notify.mobile_app_test")[0][1]
        self.assertNotIn("data", daten)

    def test_abgeschaltete_stufe_schweigt(self):
        import eskalation
        self.store.set("eskalation", "einbruch", "voralarm", "aktiv", False)
        self.store.set("eskalation", "einbruch", "voralarm", "push",
                       ["notify.mobile_app_test"])
        eskalation.ausfuehren("einbruch", "voralarm", ausloeser="Test")
        self.assertEqual(self.dienste_mit("notify."), [])

    def test_eigener_text_mit_platzhaltern(self):
        import eskalation
        self.store.set("eskalation", "einbruch", "alarm", "push",
                       ["notify.mobile_app_test"])
        self.store.set("eskalation", "einbruch", "alarm", "text",
                       "Achtung: {ausloeser} im Modus {modus}")
        eskalation.ausfuehren("einbruch", "alarm", ausloeser="Flur",
                              modus="Abwesend")
        daten = self.dienste_mit("notify.mobile_app_test")[0][1]
        self.assertEqual(daten["message"], "Achtung: Flur im Modus Abwesend")

    def test_ein_tippfehler_im_text_verhindert_die_meldung_nicht(self):
        """Lieber ein unschöner Satz als gar keine Warnung."""
        import eskalation
        self.store.set("eskalation", "einbruch", "alarm", "push",
                       ["notify.mobile_app_test"])
        self.store.set("eskalation", "einbruch", "alarm", "text",
                       "Achtung {gibtesnicht}")
        eskalation.ausfuehren("einbruch", "alarm", ausloeser="Flur")
        self.assertEqual(len(self.dienste_mit("notify.mobile_app_test")), 1)

    def test_licht_geht_an_und_wieder_aus(self):
        import eskalation
        self.store.set("eskalation", "einbruch", "alarm", "licht",
                       ["light.flur"])
        eskalation.ausfuehren("einbruch", "alarm", ausloeser="Flur")
        an = self.dienste_mit("light.turn_on")
        self.assertEqual(an[0][1]["rgb_color"], [255, 0, 0])
        eskalation.zuruecknehmen("einbruch", "alarm")
        self.assertTrue(self.dienste_mit("light.turn_off"))


if __name__ == "__main__":
    unittest.main()
