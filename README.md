# Alarmanlagen-Manager – Home Assistant Add-on

[![GitHub Release](https://img.shields.io/github/v/release/Melle79/HA-alarmanlage?style=flat-square)](https://github.com/Melle79/HA-alarmanlage/releases)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-green?style=flat-square)](LICENSE)
[![Home Assistant Add-on](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5?style=flat-square&logo=homeassistant&logoColor=white)](https://www.home-assistant.io/addons/)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-melle79-FFDD00?style=flat-square&logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/melle79)

[![Repository zu Home Assistant hinzufügen](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FMelle79%2FHA-alarmanlage)

Einbruch- und Gefahrenmeldung für Home Assistant – vollständig über eine
Oberfläche einzurichten, **ohne eine einzige Automation**. Und mit einem Weg,
die vorhandenen abzulösen.

![Übersicht](docs/bilder/uebersicht.png)

![Einrichtungsassistent](docs/bilder/assistent.png)

---

## Warum

Eine Alarmanlage aus Automationen funktioniert, bis man etwas ändern will.
Dann steht die Eintrittsverzögerung in `configuration.yaml` und braucht für
jede Änderung einen Neustart, die Melderliste steckt in einem Trigger, die
Meldewege in fünf Aktionen, und „nur wenn niemand zu Hause ist“ steht in drei
Automationen gleichzeitig. Wer eine davon vergisst, merkt es in der Nacht, in
der es darauf ankommt.

Dieses Add-on legt all das an eine Stelle und gibt ihr eine Oberfläche.

---

## Features

### 🧭 Einrichtungsassistent
- Zehn Schritte beim ersten Start, später jederzeit wieder aufrufbar
- Erklärt bei jedem Schritt das **Warum**, nicht nur das Feld
- Fragt nach **Haustieren** und stellt die Melder in den betroffenen Räumen
  entsprechend ein
- Schaltet nie scharf: Am Ende läuft die Anlage im Trockenlauf
- Speichert jeden Schritt sofort – abbrechen und später weitermachen

### 🛡️ Vollständige Zustandsmaschine
- Ausgehverzögerung, Eintrittsverzögerung, Voralarm, Auslösung
- Automatische Rückkehr in den scharfen Zustand nach der Auslösezeit
- Der Scharfzustand **überlebt den Neustart** – sonst steht das Haus nach
  jedem Update unscharf da, ohne dass es auffällt

### 🌓 Scharfmodi
- Abwesend, Urlaub, Nacht, Teilscharf – benennbar, je mit eigenen Zeiten
- Je Melder einstellbar, in welchen Modi er gilt
- Ein **Handmodus** (üblich: Urlaub), der nicht von selbst kippt

### 🔥 Gefahrenlinien
- **Einbruch** zählt nur im scharfen Zustand
- **Rauch** und **Wasser** rund um die Uhr – mit eigenen Meldewegen und
  eigenen Sensoren. Sie rühren das Bedienfeld nicht an: Ein Rauchmelder ist
  kein Einbruch, und wer die Einbruchanlage entschärft, hat nicht das Feuer
  gelöscht

### 👥 Scharfschaltung nach Anwesenheit
- Der Hausmodus folgt den Personen, mit einstellbarer Leerlauffrist
- Sicherheitsnetz **„nie scharf, solange jemand zu Hause gemeldet ist“**
- Alternativ: einer vorhandenen Entität folgen, oder nur von Hand

### 🔑 Entschärfen am Türschloss
- Wer aufschließt, hat sich am Schloss ausgewiesen
- **Mehrere Schlossquellen nebeneinander** – sie sind sich selten einig
- **Nachlaufsperre**, die am Schloss hängt statt an einer Stoppuhr, mit
  Obergrenze und gedrosselter Meldung

### 📣 Meldewege je Stufe
- Voralarm, Alarm, Entwarnung – jede Stufe einzeln einstellbar und einzeln
  **erprobbar**
- Push (auch kritisch, durchbricht den Fokusmodus), Sprachausgabe, Licht,
  Sirene
- **Eigener Meldetext je Melder** – der Kohlenmonoxidmelder sagt nicht
  „meldet Rauch“

### 🔎 Melder im Blick
- Nach Linie gruppiert, nach Bereich sortiert
- Zustandspunkt je Melder: ruhig, angesprungen, oder „gibt es nicht mehr“
- **Benennt, was fehlt**: welche passenden Melder Home Assistant kennt, die
  hier nicht eingerichtet sind. Was kein Melder ist, lässt sich dauerhaft
  ausblenden

### 🐕 Gegen Fehlalarme
- **Mindestdauer** je Melder – gegen kurze Zucker unbekannter Ursache
- **Ruhequelle** je Melder – Entitäten, deren Bewegung ihn *erklärbar*
  auslöst. Ein Präsenzmelder sieht den Rollladen im selben Zimmer fahren;
  gegen so eine bekannte Ursache hilft kein Zeitfilter, sondern Wissen
- **Melder nur in bestimmten Modi** – der Wohnzimmermelder gilt nur im
  Urlaub, weil sonst der Hund dort sein darf

### 📥 Übernahme
- Liest `automations.yaml`, erkennt die Alarmanlage darin und baut einen
  vollständigen Vorschlag – samt Verzögerungen aus einem `manual`-Bedienfeld
- Schaltet die abgelösten Automationen auf Knopfdruck **ab** (nicht: löscht
  sie), nach einer Sicherung, mit einem Weg zurück

### 🧪 Trockenlauf
- Rechnet und protokolliert alles, schickt nichts hinaus
- So lässt sich die Anlage neben den alten Automationen einfahren

### 📓 Protokoll
- Überlebt den Neustart. Bei einer Alarmanlage der einzige Weg, hinterher zu
  beantworten, was eigentlich passiert ist

### 🃏 Dashboard-Karte
- `custom:alarmanlage-card` – bringt das Add-on selbst mit und meldet sie als
  Lovelace-Ressource an. **Kein HACS nötig**

---

## Installation

1. [Repository zu Home Assistant hinzufügen](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FMelle79%2FHA-alarmanlage)
   – oder von Hand: **Einstellungen → Add-ons → Add-on-Store → ⋮ →
   Repositories** und `https://github.com/Melle79/HA-alarmanlage` eintragen.
2. *Alarmanlagen-Manager* installieren und starten.
3. Die Oberfläche über den Eintrag **Alarmanlage** in der Seitenleiste öffnen.

Ein MQTT-Broker wird gebraucht – ohne ihn entsteht kein Bedienfeld in Home
Assistant. Das Mosquitto-Add-on genügt; der Supervisor meldet es von selbst.

---

## Von vorhandenen Automationen kommen

**Übernahme → Automationen durchsehen.** Der Rest steht im
[Handbuch](HANDBUCH.md#von-vorhandenen-automationen-kommen).

Das Add-on ändert die Automationen nie von sich aus. Abgeschaltet wird nur,
was ausdrücklich ausgewählt wurde, ihr Zustand liegt vorher gesichert unter
`/data/sicherungen/`, und ein Knopf schaltet sie wieder ein.

![Melder](docs/bilder/melder.png)

---

## Was in Home Assistant entsteht

| Entität | Wofür |
|---|---|
| `alarm_control_panel.alarmanlage_bedienfeld` | Das Bedienfeld, mit allen Angaben als Attribute |
| `select.alarmanlage_hausmodus` | Der Sollzustand – auch für Automationen und Sprache |
| `switch.alarmanlage_automatik` | Automatische Scharfschaltung an/aus |
| `switch.alarmanlage_trockenlauf` | Probebetrieb an/aus |
| `sensor.alarmanlage_letzter_ausloser` | Wer zuletzt angesprochen hat |
| `sensor.alarmanlage_zustand_seit` | Seit wann der Zustand gilt |
| `binary_sensor.alarmanlage_rauch` | Rauchlinie, rund um die Uhr |
| `binary_sensor.alarmanlage_wasser` | Wasserlinie, rund um die Uhr |
| `binary_sensor.alarmanlage_offene_kontakte` | Offene Kontakte |
| `button.alarmanlage_alarme_quittieren` | Offene Dauerlinien-Alarme schließen |

---

## Dashboard-Karte

```yaml
type: custom:alarmanlage-card
entity: alarm_control_panel.alarmanlage_bedienfeld
titel: Alarmanlage
textgroesse: gross   # klein | normal | gross | riesig oder eine Zahl
knoepfe: true
```

`textgroesse` steht standardmäßig auf *gross* (1,2×), weil solche Karten
regelmäßig auch an einem Wandtablett hängen und 11-px-Text dort aus
anderthalb Metern unlesbar ist.

---

## Dokumentation

| Dokument | Für wen |
|---|---|
| **[Handbuch](HANDBUCH.md)** | Alles: Begriffe, Einrichtung, Betrieb, Fehlersuche |
| [DOCS.md](alarmanlagen_manager/DOCS.md) | Dieselbe Sache in Kurzform – wird in Home Assistant angezeigt |
| [CHANGELOG.md](CHANGELOG.md) | Was sich geändert hat, und warum |
| [tests/README.md](tests/README.md) | Was geprüft wird |

---

## Optionen

| Option | Bedeutung |
|---|---|
| `mqtt_enabled` | MQTT benutzen. Ohne Broker gibt es kein Bedienfeld |
| `mqtt_host`, `mqtt_port`, `mqtt_user`, `mqtt_password` | Nur für einen Broker außerhalb von Home Assistant nötig |
| `entity_praefix` | Erster Teil der Entitäts-IDs. **Nach der Einrichtung nicht mehr ändern** |
| `log_level` | `debug` zeigt jede Melderauswertung |

---

## Hinweise

- **`unlocked` heißt nicht „Tür offen“.** Ein Schloss meldet oft nur, dass
  der Riegel nicht vorgeschoben ist – in vielen Haushalten der Normalzustand
  rund um die Uhr. Das Schloss hält deshalb nur das *Wieder*-Scharfschalten
  auf, nachdem es die Anlage selbst entschärft hat. Als Bedingung für jedes
  Scharfschalten ergäbe es eine Anlage, die nie scharf wird und dabei gesund
  aussieht.
- **Das Add-on fährt keine Rollos.** Wer bei Rauch den Fluchtweg öffnen will,
  macht das dort, wo die Rollos gesteuert werden – zwei Stellen, die bei Rauch
  Rollos fahren, fahren irgendwann gegeneinander. Die Übernahme erkennt solche
  Automationen und schlägt sie nicht zur Ablösung vor.
- **Es ersetzt keine zertifizierte Einbruchmeldeanlage.** Es hängt an WLAN,
  Zigbee, einer Cloud und dem Strom im Haus.
- Konfiguration und Zustand liegen unter `/data/`, das Protokoll in
  `/data/protokoll.jsonl`.

---

## Tests

```bash
python3 -m unittest discover -s tests
```

112 Tests, nur PyYAML als Abhängigkeit. Sie halten die Fälle fest, an denen
echte Anlagen gescheitert sind – die Nacht mit 82 unterdrückten Bewegungen,
das Cloud-Schloss, das zu spät meldet, die Anlage, die scharf stand, während
die Familie schlief, und das Schloss, das dauerhaft „offen“ meldete
und damit jedes Scharfschalten verhinderte.

---

## Unterstützung

Wenn dir das Projekt gefällt:

[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/melle79)

---

## Lizenz

MIT – siehe [LICENSE](LICENSE).
