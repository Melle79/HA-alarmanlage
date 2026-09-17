"""Schloss, Nachlaufsperre und der Weg zurück in den scharfen Zustand."""

import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from basis import AnlagenTest  # noqa: E402


class AmSchloss(AnlagenTest):

    def setUp(self):
        super().setUp()
        self.store.set("entschaerfung", "schloesser",
                       ["lock.haustuer", "lock.cloud"])
        self.setze("lock.haustuer", "locked")
        self.setze("lock.cloud", "locked")

    def test_aufschliessen_entschaerft(self):
        """Wer aufschließt, hat sich am Schloss ausgewiesen."""
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("lock.haustuer", "unlocked")
        self.assertEqual(self.anlage.panel, "disarmed")

    def test_jede_schlossquelle_zaehlt(self):
        """Die Quellen sind sich nicht einig.

        Ein Cloud-Schloss hinkt hinterher oder schweigt ganz, während das
        lokale sofort meldet. Wer sich für eine entscheidet, entscheidet
        sich irgendwann falsch – und der Alarm geht los, während jemand
        mit dem Schlüssel in der Tür steht.
        """
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("lock.cloud", "unlocked")
        self.assertEqual(self.anlage.panel, "disarmed")

    def test_zusatzmelder_zaehlt_ebenfalls(self):
        self.store.set("entschaerfung", "zusatzmelder",
                       ["sensor.schlosszustand"])
        self.setze("sensor.schlosszustand", "locked")
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("sensor.schlosszustand", "unlocked")
        self.assertEqual(self.anlage.panel, "disarmed")

    def test_der_hausmodus_bleibt_abwesend(self):
        """Entschärft heißt nicht 'jemand wohnt wieder hier'.

        Panel-Zustand und Hausmodus laufen hier auseinander – genau
        deshalb sind es zwei Größen.
        """
        self.anlage.hausmodus_setzen("abwesend")
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("lock.haustuer", "unlocked")
        self.assertEqual(self.anlage.panel, "disarmed")
        self.assertEqual(self.anlage.hausmodus, "abwesend")


class Nachlaufsperre(AnlagenTest):

    def setUp(self):
        super().setUp()
        self.store.set("entschaerfung", "schloesser", ["lock.haustuer"])
        self.store.set("entschaerfung", "nachlauf_minuten", 5)
        self.store.set("entschaerfung", "nachlauf_hoechstens_minuten", 60)
        self.setze("lock.haustuer", "unlocked")
        self.melder_anlegen("binary_sensor.bwm")

    def test_bewegung_loest_nicht_aus_solange_das_schloss_offen_steht(self):
        """Wer die Tür offen lässt, ist noch im Haus.

        Der Vorfall dahinter: Beim Fischefüttern blieb die Entschärfung
        aus, und danach alarmierte die Anlage alle fünf Minuten neu, weil
        sie nach der Auslösezeit von selbst wieder scharf schaltete –
        während die Person noch im Haus war.
        """
        self.store.z_set(letzte_entsperrung=time.time())
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.anlage.panel, "armed_away")

    def test_die_sperre_endet_kurz_nach_dem_abschliessen(self):
        self.store.z_set(letzte_entsperrung=time.time() - 600)
        # Vor zehn Minuten abgeschlossen: die Sperre ist vorbei.
        self.zustaende["lock.haustuer"] = {
            "entity_id": "lock.haustuer", "state": "locked",
            "attributes": {},
            "last_changed": (datetime.now(timezone.utc)
                             - timedelta(minutes=10)).isoformat(),
        }
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.anlage.panel, "triggered")

    def test_obergrenze_macht_die_anlage_nicht_dauerhaft_blind(self):
        """Ein Schloss, das 'abgeschlossen' nie meldet, darf sie nicht
        stilllegen. Nach der Obergrenze zählt Bewegung wieder."""
        self.store.z_set(letzte_entsperrung=time.time() - 3 * 3600)
        self.anlage.scharf_schalten("abwesend", sofort=True)
        self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(self.anlage.panel, "triggered")

    def test_unterdrueckung_meldet_hoechstens_im_abstand(self):
        """Sichtbar soll sie bleiben, hörbar nicht bei jeder Bewegung.

        In einer einzigen Nacht kamen so 82 Pushes zusammen: kein Alarm,
        aber 82 Wecker.
        """
        self.store.set("entschaerfung", "meldung_abstand_minuten", 30)
        self.store.set("eskalation", "einbruch", "alarm", "push",
                       ["notify.mobile_app_test"])
        self.store.z_set(letzte_entsperrung=time.time())
        self.anlage.scharf_schalten("abwesend", sofort=True)
        for _ in range(5):
            self.ereignis("binary_sensor.bwm", "off")
            self.ereignis("binary_sensor.bwm", "on")
        self.assertEqual(len(self.dienste_mit("notify.mobile_app_test")), 1)

    def test_unterdrueckte_bewegung_steht_trotzdem_im_protokoll(self):
        self.store.z_set(letzte_entsperrung=time.time())
        self.anlage.scharf_schalten("abwesend", sofort=True)
        for _ in range(3):
            self.ereignis("binary_sensor.bwm", "off")
            self.ereignis("binary_sensor.bwm", "on")
        eintraege = self.protokoll.lesen(50, art="unterdrueckt")
        self.assertEqual(len(eintraege), 3)


class WiederScharf(AnlagenTest):

    def setUp(self):
        super().setUp()
        self.store.set("entschaerfung", "schloesser", ["lock.haustuer"])
        self.store.set("entschaerfung", "wieder_scharf_minuten", 10)
        self.store.set("entschaerfung", "rueckfall_stunden", 2)

    def _schloss_zu_seit(self, minuten):
        self.zustaende["lock.haustuer"] = {
            "entity_id": "lock.haustuer", "state": "locked",
            "attributes": {},
            "last_changed": (datetime.now(timezone.utc)
                             - timedelta(minutes=minuten)).isoformat(),
        }

    def test_noch_nicht_lange_genug_zu(self):
        self.store.z_set(letzte_entsperrung=time.time() - 300)
        self._schloss_zu_seit(2)
        self.assertFalse(self.anlage._darf_wieder_scharf())

    def test_zehn_minuten_zu_reicht(self):
        self.store.z_set(letzte_entsperrung=time.time() - 900)
        self._schloss_zu_seit(11)
        self.assertTrue(self.anlage._darf_wieder_scharf())

    def test_rueckfall_nach_zwei_stunden(self):
        """Ohne ihn bliebe die Anlage nach einmal Aufschließen für immer aus."""
        self.store.z_set(letzte_entsperrung=time.time() - 3 * 3600,
                         seit=time.time() - 3 * 3600)
        self.setze("lock.haustuer", "unknown")
        self.assertTrue(self.anlage._darf_wieder_scharf())

    def test_der_takt_schaltet_wieder_scharf(self):
        self.store.set("scharfschaltung", "personen", ["person.sven"])
        self.setze("person.sven", "not_home")
        self.anlage.hausmodus_setzen("abwesend")
        self.store.z_set(panel="disarmed", modus=None,
                         letzte_entsperrung=time.time() - 1800)
        self._schloss_zu_seit(15)
        self.anlage._sollzustand_durchsetzen()
        self.assertIn(self.anlage.panel, ("arming", "armed_away"))

    def test_kein_wiederschaerfen_solange_offen(self):
        self.anlage.hausmodus_setzen("abwesend")
        self.store.z_set(panel="disarmed", letzte_entsperrung=time.time())
        self.setze("lock.haustuer", "unlocked")
        self.anlage._sollzustand_durchsetzen()
        self.assertEqual(self.anlage.panel, "disarmed")


if __name__ == "__main__":
    unittest.main()
