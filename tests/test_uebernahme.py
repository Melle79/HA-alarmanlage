"""Die vorhandenen Automationen lesen und daraus einen Vorschlag bauen."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from basis import AnlagenTest  # noqa: E402

BEISPIEL = str(Path(__file__).parent / "beispiel")


class Kandidaten(AnlagenTest):

    def test_eigene_sensoren_werden_nicht_vorgeschlagen(self):
        """Sonst würde der Sammelsensor zum Melder für sich selbst.

        Das Add-on veröffentlicht binary_sensor.alarmanlage_rauch als
        Zusammenfassung aller Rauchmelder. Stünde der in der Auswahl,
        könnte er sich selbst auslösen.
        """
        self.setze("binary_sensor.alarmanlage_rauch", "off",
                   device_class="smoke", friendly_name="Alarmanlage Rauch")
        self.setze("binary_sensor.rm_echt", "off",
                   device_class="smoke", friendly_name="RM Keller")
        ids = [k["entity_id"] for k in self.ha.melderkandidaten("alarmanlage")]
        self.assertIn("binary_sensor.rm_echt", ids)
        self.assertNotIn("binary_sensor.alarmanlage_rauch", ids)

    def test_ohne_praefix_wird_nichts_ausgenommen(self):
        self.setze("binary_sensor.alarmanlage_rauch", "off",
                   device_class="smoke")
        ids = [k["entity_id"] for k in self.ha.melderkandidaten()]
        self.assertIn("binary_sensor.alarmanlage_rauch", ids)

    def test_mehrere_auf_einmal_ausblenden(self):
        """Der Hinweis auf der Melderseite blendet eine ganze Gruppe aus.

        Dafür drei Anfragen hintereinander zu schicken wäre unnötig – und
        bei einem Abbruch zwischendrin bliebe die Hälfte ausgeblendet.
        """
        self.store.set("ignorierte_melder", [])
        liste = self.store.get("ignorierte_melder")
        for e in ("binary_sensor.a", "binary_sensor.b", "binary_sensor.c"):
            if e not in liste:
                liste.append(e)
        self.store.set("ignorierte_melder", liste)
        self.assertEqual(len(self.store.get("ignorierte_melder")), 3)

    def test_alle_zurueckholen_leert_die_liste(self):
        self.store.set("ignorierte_melder", ["binary_sensor.a"])
        self.store.set("ignorierte_melder", [])
        self.assertEqual(self.store.get("ignorierte_melder"), [])

    def test_ausgeblendete_werden_gemerkt(self):
        self.assertEqual(self.store.get("ignorierte_melder"), [])
        self.store.set("ignorierte_melder", ["binary_sensor.tankstelle"])
        self.store.laden()
        self.assertEqual(self.store.get("ignorierte_melder"),
                         ["binary_sensor.tankstelle"])


class Uebernahme(AnlagenTest):

    def setUp(self):
        os.environ["HA_CONFIG_DIR"] = BEISPIEL
        super().setUp()
        # Was Home Assistant über die Melder weiß.
        for eid, klasse, name in [
            ("binary_sensor.rm_luna_rauch", "smoke", "RM Luna Rauch"),
            ("binary_sensor.rm_keller_rauch", "smoke", "RM Keller Rauch"),
            ("binary_sensor.bwm_eg_motion", "motion", "BWM EG"),
            ("binary_sensor.bwm_og_motion", "motion", "BWM OG"),
            ("binary_sensor.flur_motion", "motion", "Flur"),
        ]:
            self.setze(eid, "off", device_class=klasse, friendly_name=name)
        self.ha.bereiche = lambda: {"binary_sensor.rm_luna_rauch": "Lunas Zimmer",
                                    "binary_sensor.rm_keller_rauch": "Keller"}
        import uebernahme
        self.uebernahme = uebernahme

    def test_findet_die_alarmautomationen(self):
        aliasse = [a["alias"] for a in self.uebernahme.kandidaten()]
        self.assertIn("Alarmanlage - Melder loest aus", aliasse)
        self.assertIn("Alarm Rauchmelder Luna", aliasse)
        self.assertIn("Hausmodus folgt der Anwesenheit", aliasse)

    def test_laesst_fremde_automationen_liegen(self):
        aliasse = [a["alias"] for a in self.uebernahme.kandidaten()]
        self.assertNotIn("Waschmaschine fertig", aliasse)

    def test_markiert_was_woandershin_gehoert(self):
        """Eine Automation, die bei Rauch Rollos fährt, gehört zum
        Rollladenplaner – nicht in die Alarmanlage. Sie wird gezeigt,
        aber nicht vorgeschlagen."""
        rollos = next(a for a in self.uebernahme.kandidaten()
                      if a["alias"] == "RM Alarm öffnet alle Rollos")
        self.assertTrue(rollos["fremdwirkung"])
        self.assertFalse(rollos["vorschlagen"])

    def test_zeiten_kommen_aus_dem_alten_bedienfeld(self):
        """Damit die Übernahme nichts stillschweigend verschärft."""
        werte = self.uebernahme.panel_werte()
        self.assertEqual(werte["ausgehzeit"], 60)
        self.assertEqual(werte["eintrittszeit"], 45)
        self.assertEqual(werte["ausloesezeit"], 300)

    def test_der_vorschlag_sortiert_die_melder_auf_die_linien(self):
        konfig = self.uebernahme.vorschlag()["konfig"]
        nach_linie = {}
        for melder in konfig["melder"]:
            nach_linie.setdefault(melder["linie"], []).append(melder["entity"])
        self.assertIn("binary_sensor.rm_luna_rauch", nach_linie["rauch"])
        self.assertIn("binary_sensor.bwm_eg_motion", nach_linie["einbruch"])

    def test_der_ort_kommt_aus_dem_bereich(self):
        """'RM Luna Rauch' liest sich schlecht vor. 'Lunas Zimmer' nicht."""
        konfig = self.uebernahme.vorschlag()["konfig"]
        luna = next(m for m in konfig["melder"]
                    if m["entity"] == "binary_sensor.rm_luna_rauch")
        self.assertEqual(luna["ort"], "Lunas Zimmer")

    def test_personen_und_schloesser_werden_erkannt(self):
        konfig = self.uebernahme.vorschlag()["konfig"]
        self.assertEqual(konfig["scharfschaltung"]["personen"],
                         ["person.finn", "person.isabel", "person.sven"])
        self.assertEqual(konfig["entschaerfung"]["schloesser"],
                         ["lock.haustur", "lock.lock_ultra_db"])

    def test_ansagen_nur_bei_rauch(self):
        """Zehn sprechende Lautsprecher bei jedem Fehlalarm der
        Bewegungsmelder wären ein sicherer Weg, die Anlage wieder
        abzuschalten."""
        konfig = self.uebernahme.vorschlag()["konfig"]
        self.assertTrue(konfig["eskalation"]["rauch"]["alarm"]["alexa"])
        self.assertFalse(konfig["eskalation"]["einbruch"]["alarm"]["alexa"])

    def test_push_geht_an_beide_telefone(self):
        konfig = self.uebernahme.vorschlag()["konfig"]
        push = konfig["eskalation"]["einbruch"]["alarm"]["push"]
        self.assertIn("notify.mobile_app_svens_iphone", push)
        self.assertIn("notify.mobile_app_isabels_iphone", push)

    def test_der_voralarm_bleibt_still(self):
        """Wer in der Eintrittsverzögerung entschärft, soll nicht geweckt
        werden."""
        konfig = self.uebernahme.vorschlag()["konfig"]
        self.assertFalse(konfig["eskalation"]["einbruch"]["voralarm"]["aktiv"])

    def test_uebernehmen_fuellt_die_konfiguration(self):
        vorschlag = self.uebernahme.vorschlag()["konfig"]
        self.uebernahme.uebernehmen(vorschlag)
        self.assertEqual(len(self.store.melder()), len(vorschlag["melder"]))
        self.assertEqual(self.store.get("modi", "abwesend", "eintrittszeit"), 45)

    def test_abschalten_sichert_vorher(self):
        self.setze("automation.alarmanlage_melder_loest_aus", "on",
                   friendly_name="Alarmanlage - Melder loest aus")
        ergebnis = self.uebernahme.automationen_abschalten(
            ["Alarmanlage - Melder loest aus"])
        self.assertTrue(Path(ergebnis["sicherung"]).is_file())
        self.assertIn(("automation.turn_off",
                       {"entity_id": ["automation.alarmanlage_melder_loest_aus"]}),
                      self.gerufen)

    def test_zurueck_ohne_automationen_laesst_den_trockenlauf_aus(self):
        """Der gefährlichste Knopf im ganzen Add-on.

        Die Sicherung hält fest, welche Automationen **an** waren – nicht,
        was in ihnen stand. Wer sie inzwischen gelöscht hat, bekommt sie
        hierüber nicht zurück. Den Trockenlauf trotzdem einzuschalten
        legte die Anlage still, ohne dass etwas anderes über das Haus
        wachte.
        """
        self.setze("automation.weg", "on", friendly_name="Weg")
        self.uebernahme.automationen_abschalten(["Weg"])
        self.store.set("betrieb", "trockenlauf", False)
        # Jetzt ist sie geloescht.
        self.zustaende.pop("automation.weg")

        ergebnis = self.uebernahme.automationen_zurueck()
        self.assertFalse(ergebnis["ok"])
        self.assertEqual(ergebnis["grund"], "automationen_geloescht")
        self.assertIn("automation.weg", ergebnis["fehlen"])
        self.assertFalse(self.store.get("betrieb", "trockenlauf"))

    def test_zurueck_schaltet_wieder_ein_und_den_trockenlauf_an(self):
        self.setze("automation.alarmanlage_melder_loest_aus", "on",
                   friendly_name="Alarmanlage - Melder loest aus")
        self.uebernahme.automationen_abschalten(
            ["Alarmanlage - Melder loest aus"])
        self.store.set("betrieb", "trockenlauf", False)
        ergebnis = self.uebernahme.automationen_zurueck()
        self.assertTrue(ergebnis["ok"])
        self.assertTrue(self.store.get("betrieb", "trockenlauf"))


if __name__ == "__main__":
    unittest.main()
