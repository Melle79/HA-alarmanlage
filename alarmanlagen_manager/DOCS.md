# Alarmanlagen-Manager

Einbruch- und Gefahrenmeldung für Home Assistant, vollständig über eine
Oberfläche einzurichten.

> **Das ausführliche [Handbuch](https://github.com/Melle79/HA-alarmanlage/blob/main/HANDBUCH.md)**
> erklärt jede Seite, die wiederkehrenden Aufgaben und die Fehlersuche. Hier
> steht die Kurzfassung. Das Add-on ersetzt das, was sonst aus einem
YAML-Bedienfeld, einer Handvoll Helfer und einem Dutzend Automationen
zusammenwächst.

## Warum überhaupt

Eine Alarmanlage aus Automationen funktioniert – bis man etwas ändern will.
Dann steht die Eintrittsverzögerung in `configuration.yaml` (und jede
Änderung kostet einen Neustart), die Melderliste in einem Trigger, die
Meldewege in fünf Aktionen und die Bedingung „nur wenn niemand zu Hause
ist" in drei Automationen gleichzeitig. Wer eine davon vergisst, merkt es
in der Nacht, in der es darauf ankommt.

Hier steht all das an **einer** Stelle, und die Stelle hat eine Oberfläche.

![Übersicht](https://raw.githubusercontent.com/Melle79/HA-alarmanlage/main/docs/bilder/uebersicht.png)

## Das Modell

Vier Begriffe, und es lohnt sich, sie auseinanderzuhalten:

| Begriff | Was er bedeutet |
| --- | --- |
| **Hausmodus** | Was gelten *soll*: Zuhause, Abwesend, Urlaub, Nacht. Folgt der Anwesenheit oder wird von Hand gesetzt. |
| **Panel-Zustand** | Was die Anlage gerade *tut*: entschärft, schaltet scharf, scharf, Eintrittsverzögerung, ausgelöst. |
| **Linie** | Eine Gefahrenart: Einbruch, Rauch, Wasser. Jede hat eigene Meldewege. |
| **Melder** | Eine Entität mit Art, Linie, Modi und Verzögerung. |

Hausmodus und Panel-Zustand laufen absichtlich auseinander. Schließt jemand
die Haustür auf, entschärft die Anlage – der Hausmodus bleibt aber
„Abwesend", und die Anlage kommt nach der Sperrfrist von selbst zurück.
Presste man beides in eine Größe, bräuchte man für diesen einen Fall wieder
einen Kunstgriff.

## Linien: scharf oder rund um die Uhr

* **Nur wenn scharf** (Einbruch): Melder zählen, wenn die Anlage scharf ist.
* **Rund um die Uhr** (Rauch, Wasser): Melder zählen immer. Rauch kümmert es
  nicht, ob jemand zu Hause ist – und wer die Einbruchanlage entschärft, hat
  damit nicht das Feuer gelöscht. Diese Linien rühren den Panel-Zustand
  deshalb nicht an; sie melden über eigene Sensoren.

## Melder

Die Melder stehen nach **Linie** gruppiert und darin nach **Bereich**
sortiert. Zugeklappt sagt jede Zeile, was man beim Durchsehen wissen will:
Art, in welchen Modi der Melder gilt und ob er verzögert auslöst. Der Punkt
links zeigt seinen Zustand – grau ruhig, gelb angesprungen, roter Ring
heißt „gibt es in Home Assistant nicht mehr".

Gegen Fehlalarme trägt jeder Melder zwei Felder: eine **Mindestdauer**
(gegen kurze Zucker unbekannter Ursache) und **Ruhequellen** – Entitäten,
deren Bewegung ihn erklärbar auslöst, etwa der Rollladen im selben Zimmer.
Gegen eine bekannte Ursache hilft kein Zeitfilter, sondern Wissen.

Je Linie steht außerdem, **welche passenden Melder Home Assistant kennt,
die hier nicht eingerichtet sind**. Ein Rauchmelder, der in keiner
Alarmanlage steht, fällt sonst niemandem auf.

Der Vorschlag geht nach der Geräteklasse, und die ist gutgläubig: In einer
gewachsenen Installation tragen auch Dinge die Klasse *opening*, die mit
dem Haus nichts zu tun haben – etwa der Öffnungszustand von Tankstellen.
Solche Vorschläge lassen sich mit **✕** dauerhaft ausblenden; ein Schalter
über der Liste holt sie wieder hervor. Die eigenen Sammelsensoren des
Add-ons stehen gar nicht erst zur Auswahl.

## Erste Einrichtung

![Einrichtungsassistent](https://raw.githubusercontent.com/Melle79/HA-alarmanlage/main/docs/bilder/assistent.png)

Beim ersten Start führt ein **Assistent** durch zehn Schritte – von den
Personen über die Melder und Haustiere bis zur Testmeldung. Er ist später
über *Übersicht → Einrichtung* wieder erreichbar, schaltet nie scharf und
speichert jeden Schritt sofort. Wer lieber von Hand einrichtet, klickt ihn
mit *Später* weg.

![Melder](https://raw.githubusercontent.com/Melle79/HA-alarmanlage/main/docs/bilder/melder.png)

1. **Übernahme** öffnen und *Automationen durchsehen*. Das Add-on liest
   `automations.yaml`, erkennt, was zur Alarmanlage gehört, und baut daraus
   einen vollständigen Vorschlag: Melder mit Linie und Ort, Personen,
   Schlösser, Meldewege – und die Verzögerungen aus dem alten
   `manual`-Bedienfeld, damit die Übernahme nichts stillschweigend
   verschärft.
2. *Übernehmen*. Die Anlage läuft ab jetzt im **Trockenlauf**: Sie rechnet,
   protokolliert und zeigt alles, schickt aber nichts hinaus.
3. Unter **Melder**, **Modi**, **Scharfschaltung** und **Meldewege**
   nachjustieren.
4. Ein paar Tage mitlaufen lassen und ins **Protokoll** sehen. Dort steht,
   was die Anlage getan *hätte*.
5. Passt es: Trockenlauf aus, dann unter *Übernahme* die alten Automationen
   abschalten. Sie werden **abgeschaltet, nicht gelöscht**, und ihr Zustand
   wird vorher unter `/data/sicherungen/` weggeschrieben. *Wieder
   einschalten* dreht beides zurück – Automationen an, Trockenlauf an.

## Was das Add-on in Home Assistant anlegt

| Entität | Wofür |
| --- | --- |
| `alarm_control_panel.alarmanlage_bedienfeld` | Das Bedienfeld. Trägt alle Angaben als Attribute. |
| `select.alarmanlage_hausmodus` | Der Sollzustand, auch für Automationen und Sprache. |
| `switch.alarmanlage_automatik` | Automatische Scharfschaltung an/aus. |
| `switch.alarmanlage_trockenlauf` | Probebetrieb an/aus. |
| `sensor.alarmanlage_letzter_ausloser` | Wer zuletzt angesprochen hat. |
| `sensor.alarmanlage_zustand_seit` | Seit wann der Zustand gilt. |
| `binary_sensor.alarmanlage_rauch` | Rauchlinie, rund um die Uhr. |
| `binary_sensor.alarmanlage_wasser` | Wasserlinie, rund um die Uhr. |
| `binary_sensor.alarmanlage_offene_kontakte` | Offene Kontakte. |
| `button.alarmanlage_alarme_quittieren` | Offene Dauerlinien-Alarme schließen. |

Das Bedienfeld heißt ausdrücklich *Bedienfeld*, damit es nicht mit einem
vorhandenen `alarm_control_panel.alarmanlage` aus `configuration.yaml`
zusammenstößt. Home Assistant bildet die entity_id nämlich aus Geräte- und
Entitätsname; bei einem Zusammenstoß hängt es wortlos ein `_2` an, und das
bliebe für immer stehen.

`sensor.alarmanlage_seit` gibt es, weil `last_changed` bei jedem Neustart
von Home Assistant auf die Startzeit springt. Ohne eigenen Zeitstempel
stünde nach einem Neustart um 16:37 „entschärft seit 16:37" auf der Karte,
obwohl es seit vorgestern so ist.

## Die Dashboard-Karte

Das Add-on legt `alarmanlage-card.js` nach `/config/www` und trägt sie als
Lovelace-Ressource ein. Kein HACS nötig.

```yaml
type: custom:alarmanlage-card
entity: alarm_control_panel.alarmanlage_bedienfeld
titel: Alarmanlage
textgroesse: gross   # klein | normal | gross | riesig oder eine Zahl
knoepfe: true
```

`textgroesse` steht standardmäßig auf *gross* (1,2×), weil solche Karten
regelmäßig auch an einem Wandtablett hängen und 11-px-Text dort aus
anderthalb Metern unlesbar ist. Mitskaliert wird alles – Schrift, Symbole,
Knöpfe –, sonst wächst der Text in einen gleich großen Knopf.

## Scharfschaltung

![Scharfschaltung](https://raw.githubusercontent.com/Melle79/HA-alarmanlage/main/docs/bilder/schaltung.png)

**Der Anwesenheit folgen** (Vorgabe): Kommt jemand nach Hause, geht der
Hausmodus auf *Zuhause*. Ist die eingestellte Zeit lang niemand da, geht er
auf den gewählten Modus.

Geprüft wird ausschließlich auf den Zustand `home`. Manche Ortungsquellen
setzen unterwegs eigene Standzonen statt `not_home`; eine Prüfung darauf
ginge nie auf.

**Nie scharf, solange jemand als zu Hause gemeldet ist** steht als eigener
Schalter da und ist der Rettungsanker gegen jede falsche
Abwesenheitsmeldung. Ohne ihn genügt eine Ortung, die kurz aussetzt, und die
Anlage steht scharf, während die Familie schläft.

**Handmodus**: Ein Modus (üblicherweise Urlaub), der nicht von selbst
kippt. Sonst beendete ein einzelnes Heimkommen den Urlaubsmodus.

## Entschärfen am Schloss

Wer die Haustür aufschließt, hat sich am Schloss ausgewiesen – das ist der
Nachweis, nicht der Bewegungsmelder danach.

**Mehrere Schlossquellen dürfen nebeneinander stehen**, und das ist keine
Bequemlichkeit: Sie sind sich nicht einig. Ein Cloud-Schloss hinkt
hinterher oder schweigt stundenlang, während ein lokales sofort meldet. Wer
sich für eine Quelle entscheidet, entscheidet sich irgendwann falsch – und
der Alarm geht los, während jemand mit dem Schlüssel in der Tür steht.

> **Das Schloss hält nur das *Wieder*-Scharfschalten auf.** Ein Schloss im
> Zustand `unlocked` heißt nicht „Tür offen", sondern nur „Riegel nicht
> vorgeschoben" – in vielen Haushalten der Normalzustand. Als Bedingung für
> jedes Scharfschalten ergäbe das eine Anlage, die nie scharf wird und dabei
> gesund aussieht. Die Anlage merkt sich deshalb, *warum* sie entschärft
> ist; nur nach einer Entschärfung am Schloss zählt das Schloss.

### Nachlaufsperre

Nach dem Aufschließen löst Bewegung nicht aus. Die Sperre hängt am Schloss,
nicht an einer festen Frist: Solange ein Schloss offen steht, ist jemand im
Haus. Abgeschlossen wird von außen, deshalb endet sie kurz danach.

Daraus ergibt sich die Reihenfolge, und sie ist Absicht: **Sperre endet nach
5 Minuten, scharf wird die Anlage erst nach 10** – kein blindes Fenster.

Die **Obergrenze ab dem Aufschließen** ist der Rückfallschutz. Ein Schloss,
das „abgeschlossen" nie meldet, darf die Anlage nicht dauerhaft blind
machen.

Unterdrückte Bewegung wird gemeldet, aber höchstens im eingestellten
Abstand. Sichtbar soll sie bleiben, hörbar nicht bei jeder Bewegung.

## Meldewege

![Meldewege](https://raw.githubusercontent.com/Melle79/HA-alarmanlage/main/docs/bilder/meldewege.png)

Je Linie drei Stufen: **Voralarm** (während der Eintrittsverzögerung),
**Alarm**, **Entwarnung**. Jede Stufe kann Push (auch kritisch),
Sprachausgabe, Licht und Schalter ansprechen.

Jede Stufe ist aufklappbar, und jeder Meldeweg darin ist eine eigene Karte.
Zugeklappt steht dort, **was gewählt ist** – das ist die Frage, die man beim
Draufsehen hat. Die volle Liste kommt erst auf Verlangen, mit Suche, dem
Gewählten obenan und dem Bereich neben jedem Eintrag. Gesucht wird auch im
Bereichsnamen: „wohnzimmer" findet die Downlights, ohne dass man ihre Namen
kennt.

**Kritischer Push** durchbricht den Fokusmodus. Eine normale Meldung bleibt
nachts liegen – genau dann, wenn sie gebraucht wird. Umgekehrt weckt ein
kritischer Push für einen Hinweis die halbe Familie ohne Anlass. Die
Vorgabe ist deshalb: kritisch nur beim Alarm.

Der **Voralarm ist ab Werk aus**. Wer in der Eintrittsverzögerung
entschärft, soll keine Meldung bekommen.

Mit *Einmal auslösen* lässt sich jede Stufe von Hand abschicken. Ob der
kritische Push wirklich durch den Fokusmodus kommt, will man nicht im
Ernstfall herausfinden.

Platzhalter im eigenen Text: `{ausloeser}`, `{ort}`, `{modus}`, `{rest}`,
`{zeit}`.

### Ein Satz für einen einzelnen Melder

Am Melder selbst steht ein **eigener Meldetext**, der den der Stufe
schlägt. Eine Linie umfasst nämlich mehr als eine Gefahr: Auf der
Rauchlinie hängt auch der Kohlenmonoxidmelder, und „meldet Rauch" wäre dort
falsch. Ebenso kann ein Erschütterungsmelder an der Terrassentür
„Glasbruch an der Terrassentür" melden statt „Bewegung erkannt".

Er gilt für den **Alarm**, nicht für die Entwarnung – ein Satz, der eine
Gefahr meldet, taugt nicht als Meldung, dass nichts mehr anliegt.

## Vorprüfung beim Scharfschalten

Was passiert, wenn ein Kontakt offen steht:

* **Melden** (Vorgabe): schaltet trotzdem scharf, schreibt es ins Protokoll.
* **Überbrücken**: der offene Kontakt zählt in diesem Durchgang nicht.
* **Verhindern**: schaltet nicht scharf. Sicher – aber bei einem klemmenden
  Fenster steht die Anlage offen.

## Trockenlauf

Im Trockenlauf läuft die ganze Zustandsmaschine mit, und das Protokoll
zeigt, was geschehen wäre. Hinausgeschickt wird nichts: kein Push, keine
Ansage, kein Licht. Ein Add-on im Probebetrieb, das nachts zehn
Lautsprecher zum Schreien bringt, wäre schlimmer als eines, das im
Ernstfall nichts tut.

## Was überlebt einen Neustart

Der Scharfzustand steht in `/data/zustand.json` und wird bei jeder Änderung
geschrieben. Sonst stünde das Haus nach jedem Update der Add-ons unscharf
da, ohne dass es jemandem auffällt.

## Optionen

| Option | Bedeutung |
| --- | --- |
| `mqtt_enabled` | MQTT benutzen. Ohne Broker gibt es kein Bedienfeld in Home Assistant. |
| `mqtt_host`, `mqtt_port`, `mqtt_user`, `mqtt_password` | Nur nötig für einen Broker außerhalb von Home Assistant. Sonst meldet der Supervisor ihn selbst. |
| `entity_praefix` | Erster Teil der Entitäts-IDs. **Nach der ersten Einrichtung nicht mehr ändern** – alle Entitäten bekämen sonst neue IDs, und jede Automation liefe stillschweigend ins Leere. |
| `log_level` | `debug` zeigt jede Melderauswertung. |

## Was das Add-on nicht tut

* **Es fährt keine Rollos.** Wer bei Rauch den Fluchtweg öffnen will, macht
  das dort, wo die Rollos gesteuert werden. Zwei Stellen, die bei Rauch
  Rollos fahren, fahren irgendwann gegeneinander. Die Übernahme erkennt
  solche Automationen und schlägt sie nicht zur Ablösung vor.
* **Es ersetzt keine zertifizierte Einbruchmeldeanlage.** Es hängt an
  WLAN, Zigbee, einer Cloud und dem Strom im Haus.
