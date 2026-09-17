"""Zeichensätze – der Ort steht in der Sprachansage."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from basis import AnlagenTest  # noqa: E402


class Umlaute(AnlagenTest):

    def test_bereiche_kommen_als_utf8(self):
        """Home Assistant liefert text/plain ohne Zeichensatz. Wer sich auf
        die Vermutung von requests verlässt, bekommt ISO-8859-1 – und ein
        Lautsprecher liest hinterher "In KÃ¼che wurde Rauch erkannt" vor.
        """
        class FalscheAntwort:
            content = "binary_sensor.rm|Küche\nbinary_sensor.x|Büro".encode("utf-8")
            text = content.decode("iso-8859-1")

            def raise_for_status(self):
                pass

        import requests
        alt = requests.post
        requests.post = lambda *a, **k: FalscheAntwort()
        try:
            bereiche = self.ha.bereiche()
        finally:
            requests.post = alt

        self.assertEqual(bereiche["binary_sensor.rm"], "Küche")
        self.assertEqual(bereiche["binary_sensor.x"], "Büro")
