"""Der Fortschritt des Einrichtungsassistenten."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from basis import AnlagenTest  # noqa: E402


class Einrichtung(AnlagenTest):

    def test_eine_frische_anlage_gilt_als_nicht_eingerichtet(self):
        """Daran erkennt die Oberfläche, dass der Assistent führen soll."""
        e = self.store.get("einrichtung")
        self.assertFalse(e["abgeschlossen"])
        self.assertEqual(e["schritt"], 0)

    def test_der_fortschritt_ueberlebt_den_neustart(self):
        """Eine Einrichtung in zehn Schritten schafft nicht jeder in einem
        Zug. Wer abbricht, soll dort weitermachen, wo er aufgehört hat."""
        self.store.set("einrichtung", {"abgeschlossen": False, "schritt": 6,
                                       "uebersprungen": ["haustiere"]})
        self.store.laden()
        e = self.store.get("einrichtung")
        self.assertEqual(e["schritt"], 6)
        self.assertEqual(e["uebersprungen"], ["haustiere"])

    def test_abschliessen_laesst_die_konfiguration_in_ruhe(self):
        """Der Assistent schreibt den Fortschritt bei jedem Schritt. Das
        darf nichts anderes anfassen."""
        self.store.set("scharfschaltung", "personen", ["person.sven"])
        self.store.set("einrichtung", {"abgeschlossen": True, "schritt": 9,
                                       "uebersprungen": []})
        self.assertEqual(self.store.get("scharfschaltung", "personen"),
                         ["person.sven"])
        self.assertTrue(self.store.get("einrichtung", "abgeschlossen"))

    def test_eine_frische_anlage_steht_im_trockenlauf(self):
        """Eine Einrichtung, die am Ende eine scharfe Anlage hinterlässt,
        die niemand geprüft hat, wäre ein Fehler.

        Geprüft wird die **Vorgabe**, nicht der laufende Zustand: Das
        Testgerüst schaltet den Trockenlauf absichtlich ab, damit die
        übrigen Tests sehen, was hinausginge.
        """
        import store as store_modul
        self.assertTrue(store_modul.DEFAULTS["betrieb"]["trockenlauf"])
        self.assertEqual(self.store.z_get("panel"), "disarmed")


if __name__ == "__main__":
    unittest.main()
