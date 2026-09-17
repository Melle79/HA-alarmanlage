# Tests

```bash
python3 -m unittest discover -s tests
```

Gebraucht wird nur PyYAML; alles andere ist Bordmittel. Home Assistant wird
nicht nachgebaut, sondern ersetzt: `basis.py` setzt Zustände direkt und
liest mit, welche Dienste gerufen worden wären.

| Datei | Worum es geht |
| --- | --- |
| `test_zustandsmaschine.py` | Scharf, entschärft, Verzögerungen, Auslösung, Überbrückung |
| `test_entschaerfung.py` | Türschloss, Nachlaufsperre, Rückkehr in den scharfen Zustand |
| `test_linien.py` | Rauch und Wasser rund um die Uhr, Meldewege, Trockenlauf |
| `test_anwesenheit.py` | Hausmodus nach Anwesenheit, Handmodus, Automatik |
| `test_uebernahme.py` | Automationen erkennen, Vorschlag bauen, abschalten |
| `test_mqtt.py` | Was bei Home Assistant angemeldet wird |

Die Tests halten die Fälle fest, an denen echte Anlagen gescheitert sind –
die Nacht mit 82 unterdrückten Bewegungen, das Cloud-Schloss, das zu spät
meldet, die Anlage, die scharf stand, während die Familie schlief. Wer
einen davon löscht, sollte wissen, warum.
