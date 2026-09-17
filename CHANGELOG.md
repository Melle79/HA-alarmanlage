# Änderungen

## 1.1.0 – 17.09.2026

**Die Meldewege sind jetzt Karten.** Vorher standen dort drei endlose
Spalten Kästchen nebeneinander – bei über hundert Lampen im Haus lagen die
zwei angehakten irgendwo dazwischen, und eine Stufe war 3000 Pixel hoch.

* Jede Stufe (Voralarm, Alarm, Entwarnung) ist aufklappbar und zeigt
  zugeklappt, ob sie aktiv und ob sie kritisch ist. Offen ist beim Start
  nur der Alarm.
* Jeder Meldeweg darin ist eine eigene, zugeklappte Karte mit der Antwort
  auf die Frage, die man beim Draufsehen hat: *was ist gewählt*. Also
  „Isabels Iphone, Svens Iphone" und „2 von 2" statt einer Liste.
* Aufgeklappt gibt es eine Suche (ab zehn Einträgen), das Gewählte steht
  obenan, und neben jedem Eintrag steht sein Bereich. Gesucht wird auch im
  Bereichsnamen – „wohnzimmer" findet die Downlights.
* Sortiert wird nur beim Aufklappen, nicht bei jedem Haken: Sonst springt
  der eben angeklickte Eintrag unter der Maus weg.
* Die Liste wird erst beim Aufklappen gebaut. Sonst entstünden beim Laden
  der Seite ein paar tausend Kästchen, die niemand sieht.

Weiter:

* **Bereiche gibt es jetzt für alle Domänen**, nicht nur für Melder – dafür
  mit Zwischenspeicher, weil das Template über einige tausend Entitäten
  läuft.
* **Die Reihenfolge der Stufen und Linien steht ausgeschrieben.** Sie aus
  der Schlüsselfolge des JSON zu lesen ging schief: Flask sortiert
  alphabetisch, und damit stand der Voralarm hinter der Entwarnung.
* **Statische Dateien werden nicht mehr blind aus dem Zwischenspeicher
  bedient.** Ohne das behält der Browser nach einem Update die alte
  Oberfläche und zeigt tagelang etwas, das es nicht mehr gibt.

## 1.0.2 – 17.09.2026

* **Bereichsnamen kamen verstümmelt an** – aus „Küche" wurde „KÃ¼che".
  Die Template-Schnittstelle von Home Assistant liefert `text/plain` ohne
  Zeichensatz, und `requests` fällt dann auf ISO-8859-1 zurück. Das Add-on
  entschlüsselt jetzt selbst als UTF-8. Aufgefallen ist es erst auf der
  echten Anlage, weil der Ort in der Sprachansage steht: Ein Lautsprecher
  hätte „In KÃ¼che wurde Rauch erkannt" vorgelesen.

## 1.0.1 – 17.09.2026

Nachbesserung aus dem ersten echten Aufbau.

* **Das Bedienfeld heißt jetzt `alarm_control_panel.alarmanlage_bedienfeld`.**
  Vorher trug es keinen eigenen Namen und stieß deshalb mit einem
  vorhandenen `alarm_control_panel.alarmanlage` aus `configuration.yaml`
  zusammen – Home Assistant hängte wortlos ein `_2` an. Die alte
  Ankündigung wird beim Start einmal zurückgenommen, damit die
  `_2`-Entität verschwindet statt liegenzubleiben.
* Damit verbunden die Lehre im Code: `object_id` ist ein Wunsch, kein
  Befehl. Die entity_id entsteht aus Geräte- plus Entitätsname.
* Die Dashboard-Karte zeigt in der Vorgabe auf das richtige Bedienfeld –
  vorher auf das alte aus der YAML.
* DOCS.md nennt die Entitäts-IDs, die wirklich entstehen.

## 1.0.0 – 17.09.2026

Erste Fassung.

* Zustandsmaschine mit Ausgehverzögerung, Eintrittsverzögerung, Voralarm,
  Auslösung und automatischer Rückkehr in den scharfen Zustand. Der Zustand
  überlebt den Neustart.
* Scharfmodi (Abwesend, Urlaub, Nacht, Teilscharf) mit eigenen
  Verzögerungen; je Melder einstellbar, in welchen Modi er gilt.
* Gefahrenlinien mit zwei Geltungen: *nur wenn scharf* (Einbruch) und *rund
  um die Uhr* (Rauch, Wasser). Die Dauerlinien rühren den Panel-Zustand
  nicht an.
* Scharfschaltung nach Anwesenheit, mit Handmodus und dem Schalter „nie
  scharf, solange jemand zu Hause gemeldet ist".
* Entschärfen am Türschloss über beliebig viele Schlossquellen; Sperrfrist
  nach der Türöffnung mit Obergrenze und gedrosselter Meldung.
* Meldewege je Stufe: Push (auch kritisch), Sprachausgabe, Licht, Schalter.
  Jede Stufe einzeln erprobbar.
* Vorprüfung beim Scharfschalten: melden, überbrücken oder verhindern.
* Übernahme vorhandener Automationen samt Verzögerungen aus einem
  `manual`-Bedienfeld; Abschalten mit Sicherung und Rückweg.
* Trockenlauf.
* Protokoll in `/data/protokoll.jsonl`, auf 5000 Zeilen begrenzt.
* Dashboard-Karte `custom:alarmanlage-card`, vom Add-on selbst
  bereitgestellt und als Lovelace-Ressource angemeldet.
* 84 Tests.
