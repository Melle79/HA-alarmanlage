# Änderungen

## 1.6.2 – 18.09.2026

**Fehlende Übersetzungen.** An vier Stellen schlugen rohe Schlüssel durch:

* Bei den Modi stand „Bedienfeld-Zustand: `armed_away`". Jetzt:
  „Bedienfeld: scharf – niemand zu Hause".
* Im Protokoll war die Art des Eintrags der Schlüssel selbst –
  `uebernahme`, `beruhigt`, `beobachtet`. Jetzt deutsch, und der Filter
  darüber bietet dieselben Wörter an.
* In der Übernahme stand „Linie: `einbruch`".
* Einige Rückmeldungen der Schnittstelle (`bereits_scharf`,
  `schaltet_bereits`, `keine_sicherung`) kamen unübersetzt als Meldung an.

Die **Schlüssel selbst bleiben englisch**: Sie stehen in Home Assistant, in
der Konfiguration und im Protokoll. Eine Übersetzung dort würde bei jedem
Sprachwechsel Entitäten und alte Einträge ungültig machen. Übersetzt wird
nur, was ein Mensch liest.

## 1.6.1 – 18.09.2026

**Der aufgeklappte Melder war eine Wand aus Feldern.** Er steht jetzt in
vier Abschnitten: *Was er ist*, *Wann er zählt*, *Gegen Fehlalarme*, *Was
gemeldet wird*.

* Die Ruhezeit sitzt **in** der Ruhequelle statt daneben – ohne Quelle ist
  sie bedeutungslos, und als eigenes Feld sah sie aus wie eine zweite
  Mindestdauer.
* Die lange Warnung zur Mindestdauer ist ein Tooltip; im Abschnitt steht
  ein Satz, der sagt, worum es geht.
* „In diesen Modi" und die Eintrittsverzögerung stehen beieinander, statt
  die Verzögerung ans andere Zeilenende zu schieben.

Dazu ein Textfehler: In der Kurzfassung stand **„mit Ruhequelle · mit
Ruhequelle"**. Sie wurde an zwei Stellen gebaut, und prompt liefen sie
auseinander. Jetzt baut sie genau eine Funktion – ein Text, der zweimal
gebaut wird, wird irgendwann zweimal verschieden gebaut.

## 1.6.0 – 18.09.2026

**Zwei Werkzeuge gegen Fehlalarme, je Melder.** Beide entstanden am selben
Vorfall, lösen aber verschiedene Probleme.

* **Mindestdauer** – der Melder muss so lange anhalten, bevor er zählt.
  Gegen kurze Zucker unbekannter Ursache. Fällt er vorher ab, fängt die
  Messung beim nächsten Mal von vorn an, und am Ende der Frist wird er noch
  einmal gefragt.
* **Ruhequelle** – Entitäten, deren Bewegung diesen Melder erklärbar
  auslöst. Der Melder wird dann für die eingestellte Ruhezeit übergangen,
  mit Eintrag im Protokoll.

Der Anlass: Ein Präsenzmelder im Büro sprang vier Morgen hintereinander um
08:30 an, immer genau **vier Sekunden** nachdem das Rollladen im selben
Zimmer auffuhr. Am vierten Morgen war das Haus leer – Alarm.

Die Mindestdauer allein hätte das *nicht* gelöst, und das ist die
interessantere Erkenntnis: Der Melder hält von sich aus rund 60 Sekunden.
Die Rollo-Auslösungen dauerten 65–70 s, echte Anwesenheit ab 58 s. Es gibt
keine Schwelle, die beide trennt – bei 90 s wären zwar alle vier
Rollo-Auslösungen weggefallen, aber auch 25 von 90 echten.

Gegen eine **bekannte** Ursache hilft kein Zeitfilter, sondern Wissen.
Deshalb die Ruhequelle.

## 1.5.0 – 18.09.2026

**Die Anlage hätte nicht scharf geschaltet.** Gefunden im Trockenlauf, und
es ist der schlimmste denkbare Fehler: Sie sah dabei gesund aus.

Am Morgen des 18.09. ging der Hausmodus um 07:47 korrekt auf *Abwesend* –
und dann geschah nichts. Kein Eintrag, keine Meldung, Bedienfeld weiter auf
*entschärft*. Ursache: Beide Haustürschlösser meldeten seit dem Vorabend
durchgehend `unlocked`, nicht weil die Tür offen stand, sondern weil der
Riegel nicht vorgeschoben war. In vielen Haushalten ist das der
Normalzustand rund um die Uhr.

Das Schloss war bis hierher eine Bedingung für **jedes** Scharfschalten.
Jetzt zählt es nur noch dort, wo es etwas bedeutet: **nachdem es die Anlage
selbst entschärft hat**. Dafür merkt sich die Anlage, *warum* sie entschärft
ist (`entschaerft_durch`). Ein neu gesetzter Scharfmodus hebt die Sperre
auf – wer den Modus von Hand wählt, meint es.

Dazu greift ab jetzt auch hier die Obergrenze ab dem Aufschließen (Vorgabe
60 Minuten), dieselbe wie bei der Nachlaufsperre und aus demselben Grund:
Ein Schloss, das „abgeschlossen" nie meldet, darf die Anlage weder blind
machen noch dauerhaft unscharf halten.

Vier neue Tests halten den Fall fest.

## 1.4.0 – 17.09.2026

**Jeder Melder darf einen eigenen Meldetext haben.**

Aufgefallen beim Aufnehmen eines Kohlenmonoxidmelders: Er gehört auf die
Rauchlinie – dieselbe Gefahr, dieselben Meldewege –, aber „Achtung!
Wohnzimmer meldet Rauch" wäre dort schlicht falsch. Wer nachts von einem
kritischen Push geweckt wird, soll erfahren, wonach er sucht.

Der Satz steht am Melder und schlägt den der Stufe. Er gilt für den Alarm,
nicht für die Entwarnung – „Achtung, Kohlenmonoxid!" taugt nicht als
Meldung, dass nichts mehr anliegt. Im Feld steht blass, was ohne ihn gesagt
würde.

Gilt auf jeder Linie: Ein Erschütterungsmelder an der Terrassentür kann so
„Glasbruch an der Terrassentür" melden statt „Bewegung erkannt".

## 1.3.0 – 17.09.2026

Nachbesserung am Hinweis „was fehlt hier", der in 1.2.0 dazugekommen ist.
Auf der echten Anlage schlug er zwei Dinge vor, die er nicht vorschlagen
darf:

* **Die eigenen Sensoren.** Das Add-on veröffentlicht selbst einen Rauch-,
  einen Wasser- und einen Kontaktsensor als Zusammenfassung. Die standen in
  der Auswahl – der Sammelsensor wäre zum Melder für sich selbst geworden.
  Sie sind jetzt ausgenommen.
* **Alles, was zufällig dieselbe Geräteklasse trägt.** „binary_sensor mit
  Geräteklasse *opening*" trifft in einer gewachsenen Installation auch auf
  den Öffnungszustand von zwölf Tankstellen zu. Dagegen hilft kein
  Erkennungstrick, sondern ein Knopf: Jeder Vorschlag lässt sich mit **✕
  dauerhaft ausblenden**, ein Schalter holt die Ausgeblendeten wieder
  hervor. Ausgeblendetes zählt auch im Hinweis nicht mehr mit.

Außerdem hat der Hinweis einen zweiten Knopf: *Einzeln ansehen* öffnet die
Liste, statt nur „alle hinzufügen" anzubieten.

## 1.2.0 – 17.09.2026

**Die Melderseite ist jetzt nach Linien geordnet**, in derselben Art wie
die Meldewege. Vorher standen dort 23 gleich große Kästen untereinander,
ohne erkennbare Ordnung.

* Melder sind nach **Linie** gruppiert und darin nach **Bereich** sortiert.
  Jede Gruppe ist aufklappbar und zählt, wie viele davon abgeschaltet sind.
* Jeder Melder ist eine Zeile, die zugeklappt sagt, was man beim Durchsehen
  wissen will: Name, Bereich, Art, in welchen Modi er gilt und ob er
  verzögert. Die Einstellungen kommen auf Verlangen.
* Ein **Punkt links** zeigt den Zustand: grau ruhig, gelb angesprungen,
  roter Ring heißt „diese Entität gibt es in Home Assistant nicht mehr".
  Beim Einrichten läuft man einmal durchs Haus und sieht zu.
* **Was fehlt, wird benannt.** Je Linie steht, welche passenden Melder Home
  Assistant kennt, die hier nicht eingerichtet sind – mit einem Knopf, der
  sie alle übernimmt. Fünf Rauchmelder, die in keiner Alarmanlage stehen,
  fallen sonst niemandem auf.
* **Suche über die eingerichteten Melder**, auch über den Bereichsnamen.
* *Melder hinzufügen* ist eine zugeklappte Karte und nimmt nicht mehr den
  halben Bildschirm ein. In der Liste stehen **„sonstige" zuletzt**: Bei
  einem gewachsenen Haus sind das die große Mehrheit, und es sind fast
  immer Diagnosemelder statt Alarmmelder.
* Wechselt ein Melder die Linie, wird die Eintrittsverzögerung mit
  umgestellt – bei einer Dauerlinie gibt es keine, der Haken bliebe sonst
  wirkungslos stehen.

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
