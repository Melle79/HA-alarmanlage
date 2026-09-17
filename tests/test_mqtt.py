"""Was das Add-on bei Home Assistant anmeldet – ohne echten Broker."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from basis import AnlagenTest  # noqa: E402


class FalscherClient:
    def __init__(self):
        self.nachrichten = []

    def publish(self, thema, nutzlast, retain=False):
        self.nachrichten.append((thema, nutzlast, retain))

    def subscribe(self, thema):
        pass

    def konfig(self, teil):
        """Die Ankündigung, deren Thema ``teil`` enthält."""
        for thema, nutzlast, _ in self.nachrichten:
            if thema.endswith("/config") and teil in thema:
                return json.loads(nutzlast)
        return None

    def wert(self, thema_ende):
        for thema, nutzlast, _ in reversed(self.nachrichten):
            if thema.endswith(thema_ende):
                return nutzlast
        return None


class Discovery(AnlagenTest):

    def setUp(self):
        super().setUp()
        sys.modules.pop("mqtt_publisher", None)
        import mqtt_publisher
        self.publisher = mqtt_publisher.publisher
        self.client = FalscherClient()
        self.publisher.client = self.client
        self.publisher.connected = True
        self.publisher.ankuendigen(erzwingen=True)

    def test_das_bedienfeld_wird_angemeldet(self):
        panel = self.client.konfig("alarmanlage_bedienfeld")
        self.assertEqual(panel["state_topic"], "alarmanlage/panel")
        self.assertEqual(panel["command_topic"], "alarmanlage/panel/set")
        self.assertFalse(panel["code_arm_required"])

    def test_nur_benutzte_modi_stehen_am_bedienfeld(self):
        """Ein Knopf für einen Modus, den es nicht gibt, ist eine Lüge."""
        panel = self.client.konfig("alarmanlage_bedienfeld")
        self.assertIn("arm_away", panel["supported_features"])
        self.assertIn("arm_vacation", panel["supported_features"])
        self.assertNotIn("arm_night", panel["supported_features"])

    def test_ein_neuer_modus_taucht_nach_dem_erneuern_auf(self):
        self.store.set("modi", "nacht", "aktiv", True)
        self.client.nachrichten.clear()
        self.publisher.erneut_ankuendigen()
        panel = self.client.konfig("alarmanlage_bedienfeld")
        self.assertIn("arm_night", panel["supported_features"])

    def test_die_ids_haengen_nicht_am_namen(self):
        """Eine entity_id wird nie aus einem Namen zurückgerechnet.

        Sie entsteht einmal beim Anlegen und folgt keiner Umbenennung –
        wer sie aus dem aktuellen Anzeigenamen ableitet, zeigt nach der
        ersten Umbenennung ins Leere.
        """
        self.store.set("modi", "abwesend", "name", "Keiner da")
        self.client.nachrichten.clear()
        self.publisher.erneut_ankuendigen()
        auswahl = self.client.konfig("alarmanlage_hausmodus")
        self.assertEqual(auswahl["object_id"], "alarmanlage_hausmodus")
        self.assertIn("Keiner da", auswahl["options"])

    def test_schalter_tragen_state_on_und_state_off(self):
        """Ohne sie steht der Schalter in Home Assistant auf 'unknown'."""
        schalter = self.client.konfig("alarmanlage_trockenlauf")
        self.assertEqual(schalter["state_on"], "ON")
        self.assertEqual(schalter["state_off"], "OFF")

    def test_jede_entitaet_hat_eine_verfuegbarkeitsmeldung(self):
        """Der Unterschied zwischen 'scharf' und 'weiß es nicht mehr' ist
        bei einer Alarmanlage der ganze Punkt."""
        for thema, nutzlast, _ in self.client.nachrichten:
            if not thema.endswith("/config") or not nutzlast:
                continue
            self.assertIn("availability_topic", json.loads(nutzlast), thema)

    def test_das_bedienfeld_traegt_einen_eigenen_namen(self):
        """Ohne ihn erbt es den Gerätenamen und stößt mit einem
        vorhandenen alarm_control_panel.alarmanlage zusammen. Home
        Assistant hängt dann wortlos ein '_2' an - für immer."""
        panel = self.client.konfig("alarmanlage_bedienfeld")
        self.assertEqual(panel["name"], "Bedienfeld")

    def test_die_alte_ankuendigung_wird_zurueckgenommen(self):
        """Sonst bliebe die '_2'-Entität aus der ersten Fassung stehen."""
        leer = [(t, n) for t, n, _ in self.client.nachrichten
                if t.endswith("alarmanlage_panel/config") and n == ""]
        self.assertEqual(len(leer), 1)

    def test_der_zustand_geht_als_attribute_mit(self):
        self.publisher.veroeffentlichen(self.anlage.zustand())
        self.assertEqual(self.client.wert("/panel"), "disarmed")
        attribute = json.loads(self.client.wert("/attribute"))
        self.assertIn("nachlaufsperre", attribute)
        self.assertIn("offene_kontakte", attribute)
        self.assertIn("trockenlauf", attribute)

    def test_der_zeitstempel_ist_iso_mit_zeitzone(self):
        """Anders nimmt Home Assistant ihn für device_class timestamp
        nicht an – die Entität stünde dauerhaft auf 'unknown'."""
        self.publisher.veroeffentlichen(self.anlage.zustand())
        seit = self.client.wert("/seit")
        self.assertRegex(seit, r"^\d{4}-\d{2}-\d{2}T.*[+-]\d{2}:\d{2}$")

    def test_rauch_meldet_sich_am_eigenen_sensor(self):
        melder = self.melder_anlegen("binary_sensor.rm", art="rauch",
                                     linie="rauch", ort="Keller")
        self.ereignis("binary_sensor.rm", "on")
        self.publisher.veroeffentlichen(self.anlage.zustand())
        self.assertEqual(self.client.wert("/rauch"), "ON")
        self.assertEqual(self.client.wert("/panel"), "disarmed")
        self.assertIn(melder["id"], self.store.z_get("offene_alarme"))


if __name__ == "__main__":
    unittest.main()
