# Alarmanlagen-Manager

Ein Home-Assistant-Add-on für Einbruch- und Gefahrenmeldung, das ohne eine
einzige Automation auskommt – und die vorhandenen ablöst.

![Übersicht](docs/bilder/uebersicht.png)

![Melder](docs/bilder/melder.png)

## Was es löst

Eine Alarmanlage aus Automationen funktioniert, bis man etwas ändern will.
Dann steht die Eintrittsverzögerung in `configuration.yaml` und braucht für
jede Änderung einen Neustart, die Melderliste steckt in einem Trigger, die
Meldewege in fünf Aktionen, und „nur wenn niemand zu Hause ist" steht in
drei Automationen gleichzeitig. Wer eine davon vergisst, merkt es in der
Nacht, in der es darauf ankommt.

Dieses Add-on legt all das an eine Stelle und gibt ihr eine Oberfläche.

## Funktionen

* **Vollständige Zustandsmaschine** – Ausgehverzögerung, Eintrittsverzögerung,
  Voralarm, Auslösung, automatische Rückkehr in den scharfen Zustand.
* **Scharfmodi** mit eigenen Verzögerungen; jeder Melder gilt in den Modi,
  die man ihm gibt.
* **Gefahrenlinien**: Einbruch zählt nur im scharfen Zustand, Rauch und
  Wasser rund um die Uhr – mit eigenen Meldewegen und eigenen Sensoren.
* **Scharfschaltung nach Anwesenheit**, mit dem Sicherheitsnetz „nie scharf,
  solange jemand zu Hause gemeldet ist".
* **Entschärfen am Türschloss**, mit mehreren Schlossquellen nebeneinander
  und einer Nachlaufsperre, die am Schloss hängt statt an einer Stoppuhr.
* **Meldewege je Stufe**: Push (auch kritisch), Sprachausgabe, Licht,
  Sirene – einzeln einstellbar und einzeln zu erproben.
* **Übernahme**: liest die vorhandenen Automationen, baut daraus einen
  Vorschlag und schaltet sie auf Knopfdruck ab (nicht: löscht sie).
* **Trockenlauf**: rechnet und protokolliert alles, schickt nichts hinaus.
* **Protokoll**, das den Neustart überlebt.
* **Dashboard-Karte** – bringt das Add-on selbst mit, kein HACS nötig.

## Einbau

1. In Home Assistant: **Einstellungen → Add-ons → Add-on-Store → ⋮ →
   Repositories** und `https://github.com/Melle79/HA-alarmanlage` eintragen.
2. *Alarmanlagen-Manager* installieren und starten.
3. Die Oberfläche über den Eintrag **Alarmanlage** in der Seitenleiste
   öffnen.

Ein MQTT-Broker wird gebraucht – ohne ihn entsteht kein Bedienfeld in Home
Assistant. Das Mosquitto-Add-on genügt; der Supervisor meldet es von selbst.

## Von vorhandenen Automationen kommen

Unter **Übernahme → Automationen durchsehen**. Der Rest steht in
[DOCS.md](alarmanlagen_manager/DOCS.md#erste-einrichtung).

Das Add-on ändert die Automationen nie von sich aus. Abgeschaltet wird nur,
was ausdrücklich ausgewählt wurde, und ihr Zustand liegt vorher gesichert
unter `/data/sicherungen/`.

## Tests

```bash
python3 -m unittest discover -s tests
```

Siehe [tests/README.md](tests/README.md).

## Lizenz

MIT – siehe [LICENSE](LICENSE).
