# Änderungen

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
