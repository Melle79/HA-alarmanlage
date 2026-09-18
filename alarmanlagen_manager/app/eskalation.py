"""Was passiert, wenn etwas passiert.

Eine Stufe (Voralarm, Alarm, Entwarnung) beschreibt vier Dinge: wer einen
Push bekommt, ob er den Fokusmodus durchbricht, welche Lautsprecher es
ansagen und welche Lampen oder Schalter angehen. Die Fachlogik weiß davon
nichts – sie ruft nur ``ausfuehren("einbruch", "alarm", ...)``.

Zwei Regeln, die aus Svens Anlage stammen:

* **Kritischer Push nur, wo er hingehört.** Eine normale Meldung bleibt
  nachts im Fokusmodus liegen – genau dann, wenn sie gebraucht wird. Ein
  kritischer Push für eine unterdrückte Bewegung dagegen weckt fünf
  Menschen ohne Anlass.
* **Im Trockenlauf geht nichts hinaus.** Ein Add-on im Probebetrieb, das
  nachts zehn Echos zum Schreien bringt, wäre schlimmer als eines, das im
  Ernstfall nichts tut.
"""

import logging

import ha
import protokoll
from store import store

log = logging.getLogger("alarm.eskalation")

# Die vorgegebenen Sätze, wenn am Meldeweg kein eigener Text steht.
VORGABETEXTE = {
    ("einbruch", "voralarm"): "Ein Melder hat angesprochen: {ausloeser}. "
                              "Noch {rest} Sekunden bis zum Alarm.",
    ("einbruch", "alarm"): "Bewegung erkannt: {ausloeser}. Modus: {modus}.",
    ("einbruch", "entwarnung"): "Die Anlage wurde entschärft. "
                                "Auslöser war: {ausloeser}",
    ("rauch", "alarm"): "Achtung! {ort} meldet Rauch.",
    ("rauch", "entwarnung"): "{ort} meldet keinen Rauch mehr.",
    ("wasser", "alarm"): "Achtung! {ort} meldet Wasser.",
    ("wasser", "entwarnung"): "{ort} meldet kein Wasser mehr.",
}

# Auf einer Linie liegen verwandte Gefahren, aber nicht dieselbe. Wer
# nachts von einem kritischen Push geweckt wird und "Rauch" liest, sucht
# nach dem Falschen, wenn es Kohlenmonoxid war - das riecht man nicht und
# sieht man nicht. Der Satz richtet sich deshalb nach der Art des Melders,
# solange die Stufe keinen eigenen trägt.
ART_VORGABETEXTE = {
    ("gas", "alarm"): "Achtung! {ort} meldet Gas.",
    ("gas", "entwarnung"): "{ort} meldet kein Gas mehr.",
    ("kohlenmonoxid", "alarm"): "Achtung! {ort} meldet Kohlenmonoxid.",
    ("kohlenmonoxid", "entwarnung"): "{ort} meldet kein Kohlenmonoxid mehr.",
    ("hitze", "alarm"): "Achtung! {ort} meldet Hitze.",
    ("hitze", "entwarnung"): "{ort} meldet keine Hitze mehr.",
}

ART_TITEL = {
    ("gas", "alarm"): "☣️ Gasalarm",
    ("kohlenmonoxid", "alarm"): "☣️ Kohlenmonoxid",
    ("hitze", "alarm"): "🔥 Hitzealarm",
}

TITEL = {
    ("einbruch", "voralarm"): "Alarmanlage: Voralarm",
    ("einbruch", "alarm"): "🚨 Alarm im Haus",
    ("einbruch", "entwarnung"): "Alarm beendet",
    ("rauch", "alarm"): "🔥 Rauchalarm",
    ("rauch", "entwarnung"): "Rauchalarm beendet",
    ("wasser", "alarm"): "💧 Wasseralarm",
    ("wasser", "entwarnung"): "Wasseralarm beendet",
}


def stufe(linie: str, name: str) -> dict:
    return store.get("eskalation", linie, name, default={}) or {}


def ausfuehren(linie: str, name: str, text_vorrang: str = "",
               art: str = "", **werte) -> dict:
    """Eine Meldestufe auslösen.

    ``werte`` füllt die Platzhalter im Text ({ausloeser}, {ort}, {modus},
    {rest}, {zeit}). Gibt zurück, was tatsächlich getan wurde – die
    Oberfläche zeigt das im Protokoll an.

    ``text_vorrang`` ist der Satz eines einzelnen Melders und schlägt den
    der Stufe. Nötig, weil eine Linie mehr umfasst als eine Gefahr: Auf der
    Rauchlinie hängt auch der Kohlenmonoxidmelder, und "meldet Rauch" wäre
    dort schlicht falsch. Wer im Ernstfall geweckt wird, soll erfahren,
    wonach er sucht.
    """
    konfig = stufe(linie, name)
    getan = {"push": [], "sprache": [], "licht": [], "schalter": [],
             "persistent": False, "unterdrueckt": False}

    if not konfig.get("aktiv", True):
        return getan

    # Rangfolge: der Satz des Melders, dann der eingestellte Satz der Stufe,
    # dann der zur Art des Melders, zuletzt der der Linie.
    text = (text_vorrang or konfig.get("text")
            or ART_VORGABETEXTE.get((art, name))
            or VORGABETEXTE.get((linie, name), "{ausloeser}"))
    titel = (ART_TITEL.get((art, name))
             or TITEL.get((linie, name), "Alarmanlage"))
    try:
        text = text.format(**{"ausloeser": "", "ort": "", "modus": "",
                              "rest": "", "zeit": "", **werte})
    except (KeyError, IndexError, ValueError) as err:
        # Ein Tippfehler im eigenen Text darf die Meldung nicht verhindern.
        log.warning("Text der Stufe %s/%s nicht einsetzbar: %s", linie, name, err)

    trockenlauf = bool(store.get("betrieb", "trockenlauf", default=True))
    if trockenlauf:
        getan["unterdrueckt"] = True
        if store.get("betrieb", "trockenlauf_meldet", default=True):
            ha.dienst("persistent_notification", "create", {
                "title": f"Probebetrieb – {titel}",
                "message": text + "\n\n(Trockenlauf: es wurde nichts "
                                  "hinausgeschickt.)",
                "notification_id": f"alarmanlage_probe_{linie}_{name}",
            })
            getan["persistent"] = True
        protokoll.schreiben("probe", f"{titel}: {text}", linie=linie, stufe=name)
        return getan

    # --------------------------------------------------------------- Push
    kritisch = bool(konfig.get("kritisch"))
    for dienst in konfig.get("push", []) or []:
        bereich, _, dienstname = dienst.partition(".")
        daten = {"title": titel, "message": text}
        if kritisch:
            # Kritischer Push nach Apples Regeln: ohne "critical" landet er
            # im Fokusmodus und wird erst am Morgen gesehen.
            daten["data"] = {"push": {"sound": {"name": "default",
                                                "critical": 1, "volume": 1.0}}}
        if ha.dienst(bereich, dienstname, daten):
            getan["push"].append(dienst)

    # --------------------------------------------------------- Home Assistant
    if konfig.get("persistent", True):
        if ha.dienst("persistent_notification", "create", {
            "title": titel, "message": text,
            "notification_id": f"alarmanlage_{linie}_{name}",
        }):
            getan["persistent"] = True

    # ------------------------------------------------------------- Sprache
    for dienst in konfig.get("alexa", []) or []:
        bereich, _, dienstname = dienst.partition(".")
        # Bei alexa_media gehört der Typ unter "data", nicht unter "target".
        # In Svens alten Automationen stand es an beiden Stellen; die
        # Variante mit "target" wird von neueren Fassungen ignoriert.
        if ha.dienst(bereich, dienstname,
                     {"message": text, "data": {"type": "tts"}}):
            getan["sprache"].append(dienst)

    # --------------------------------------------------------------- Licht
    farbe = konfig.get("licht_farbe") or [255, 0, 0]
    for entity_id in konfig.get("licht", []) or []:
        if ha.dienst("light", "turn_on", {
            "entity_id": entity_id, "brightness": 255, "rgb_color": farbe,
        }):
            getan["licht"].append(entity_id)

    for entity_id in konfig.get("schalter", []) or []:
        bereich = entity_id.split(".")[0]
        if ha.dienst(bereich, "turn_on", {"entity_id": entity_id}):
            getan["schalter"].append(entity_id)

    protokoll.schreiben("meldung", f"{titel}: {text}", linie=linie, stufe=name,
                        getan=getan)
    return getan


def zuruecknehmen(linie: str, name: str) -> None:
    """Licht und Schalter einer Stufe wieder ausschalten.

    Die Meldungen bleiben stehen – wer nachts geweckt wurde, soll morgens
    noch lesen können, warum.
    """
    if store.get("betrieb", "trockenlauf", default=True):
        return
    konfig = stufe(linie, name)
    for entity_id in konfig.get("licht", []) or []:
        ha.dienst("light", "turn_off", {"entity_id": entity_id})
    for entity_id in konfig.get("schalter", []) or []:
        ha.dienst(entity_id.split(".")[0], "turn_off", {"entity_id": entity_id})


def meldung_loeschen(linie: str, name: str) -> None:
    ha.dienst("persistent_notification", "dismiss", {
        "notification_id": f"alarmanlage_{linie}_{name}"})
