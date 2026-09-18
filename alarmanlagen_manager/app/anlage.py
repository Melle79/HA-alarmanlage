"""Die Anlage selbst: Zustandsmaschine, Melderauswertung, Scharfschaltung.

Drei Größen, die nicht verwechselt werden dürfen:

* **Hausmodus** – was gelten *soll*: Zuhause, Abwesend, Urlaub, Nacht.
  Er folgt der Anwesenheit oder wird von Hand gesetzt.
* **Panel-Zustand** – was die Anlage gerade *tut*: entschärft, schaltet
  scharf, scharf, Eintrittsverzögerung, ausgelöst.
* **Melder** – was die Welt meldet.

Der Hausmodus kann "Abwesend" sagen, während die Anlage entschärft ist:
genau das ist der Fall nach dem Aufschließen der Haustür. Wer beides in
eine Größe presst, baut sich die Falle ein, die in Svens alten
Automationen drei Nachbesserungen gekostet hat.

Rund um die Uhr laufen die Linien mit der Geltung "immer" (Rauch, Wasser).
Sie fragen nicht, ob jemand zu Hause ist, und sie rühren den Panel-Zustand
nicht an: Ein Rauchmelder im Kinderzimmer ist kein Einbruch, und wer die
Einbruchanlage entschärft, hat damit nicht das Feuer gelöscht.
"""

import logging
import threading
import time

import eskalation
import ha
import protokoll
from ereignisse import strom
from store import store

log = logging.getLogger("alarm.anlage")

SCHARF_ZUSTAENDE = {"armed_away", "armed_home", "armed_night", "armed_vacation"}
TAKT = 1.0

# Nach diesem Zustand fragt die Anwesenheit. Bewusst nur "home": manche
# Ortungsquellen setzen unterwegs eigene Standzonen statt "not_home", eine
# Prüfung auf "not_home" ginge dann nie auf.
ZUHAUSE = "home"


class Anlage:
    def __init__(self):
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        # Wann zuletzt niemand mehr da war – für die Leerlauf-Frist.
        self._leer_seit: float | None = None
        # Melder, die ihre Mindestdauer noch absitzen: id -> Frist. Bewusst
        # nur im Arbeitsspeicher: Nach einem Neustart fängt die Messung von
        # vorn an, und das ist richtig so – wer weiß schon, was in der
        # Zwischenzeit war.
        self._wartende: dict[str, float] = {}
        # Wird von außen gesetzt (der MQTT-Teil hängt sich hier ein).
        self.on_zustand = None
        self._letzte_veroeffentlichung = 0.0

    # -------------------------------------------------------------- Start

    def start(self) -> None:
        strom.on_change = self._melder_ereignis
        strom.on_verbunden = self._abgleichen
        self.beobachtung_erneuern()
        strom.start()
        self._stop.clear()
        self._thread = threading.Thread(target=self._takten, daemon=True,
                                        name="alarm-takt")
        self._thread.start()
        protokoll.schreiben("start", "Alarmanlagen-Manager gestartet",
                            panel=self.panel, hausmodus=self.hausmodus)

    def stop(self) -> None:
        self._stop.set()
        strom.stop()

    def beobachtung_erneuern(self) -> None:
        """Dem Ereignisstrom sagen, was ihn interessiert."""
        entitaeten = set()
        for eintrag in store.melder():
            if eintrag.get("aktiv", True) and eintrag.get("entity"):
                entitaeten.add(eintrag["entity"])
        entschaerfung = store.get("entschaerfung", default={}) or {}
        entitaeten.update(entschaerfung.get("schloesser") or [])
        entitaeten.update(entschaerfung.get("zusatzmelder") or [])
        scharf = store.get("scharfschaltung", default={}) or {}
        entitaeten.update(scharf.get("personen") or [])
        if scharf.get("quelle") == "entitaet" and scharf.get("entitaet"):
            entitaeten.add(scharf["entitaet"])
        strom.beobachten(entitaeten)

    # ------------------------------------------------------------ Zustand

    @property
    def panel(self) -> str:
        return store.z_get("panel", "disarmed")

    @property
    def hausmodus(self) -> str:
        return store.z_get("hausmodus", "zuhause")

    def _modus(self, schluessel: str) -> dict:
        return (store.get("modi", schluessel, default={}) or {})

    def _panel_zustand(self, modus_schluessel: str) -> str:
        return self._modus(modus_schluessel).get("panel_zustand", "armed_away")

    def zustand(self) -> dict:
        """Alles, was Oberfläche und Karte brauchen."""
        z = store.zustand()
        modus = z.get("modus")
        rest = None
        if z.get("frist"):
            rest = max(0, int(z["frist"] - time.time()))
        # Wie lang die laufende Frist insgesamt ist. Ohne das kann eine
        # Karte keinen Fortschritt zeigen - sie kennt nur den Rest und
        # wüsste nicht, wovon.
        gesamt = None
        panel = z.get("panel")
        if panel == "arming":
            gesamt = self._modus(modus).get("ausgehzeit")
        elif panel == "pending":
            gesamt = self._modus(modus).get("eintrittszeit")
        elif panel == "triggered":
            linie = z.get("ausloeser_linie") or "einbruch"
            gesamt = (store.get("linien", linie, "ausloesezeit", default=0)
                      or None)
        return {
            "panel": z.get("panel", "disarmed"),
            "hausmodus": z.get("hausmodus", "zuhause"),
            "modus": modus,
            "modus_name": self._modus(modus).get("name") if modus else None,
            "seit": z.get("seit"),
            "rest_sekunden": rest,
            "frist_gesamt": gesamt,
            "ausloeser": z.get("ausloeser"),
            "ausloeser_zeit": z.get("ausloeser_zeit"),
            "ausloeser_linie": z.get("ausloeser_linie"),
            "trockenlauf": bool(store.get("betrieb", "trockenlauf", default=True)),
            "automatik": bool(store.get("betrieb", "automatik", default=True)),
            "jemand_da": self._jemand_da(),
            "nachlaufsperre": self._nachlaufsperre()[0],
            "offene_kontakte": self.offene_kontakte(),
            "offene_alarme": z.get("offene_alarme", {}),
            "ueberbrueckt": z.get("ueberbrueckt", []),
            "verbunden": strom.verbunden,
        }

    def _veroeffentlichen(self, sofort: bool = True) -> None:
        if not self.on_zustand:
            return
        jetzt = time.time()
        if not sofort and jetzt - self._letzte_veroeffentlichung < 1.0:
            return
        self._letzte_veroeffentlichung = jetzt
        try:
            self.on_zustand(self.zustand())
        except Exception as err:  # noqa: BLE001
            log.warning("Zustand nicht veröffentlichbar: %s", err)

    # ------------------------------------------------------- Anwesenheit

    def _jemand_da(self) -> bool:
        personen = store.get("scharfschaltung", "personen", default=[]) or []
        for entity_id in personen:
            if ha.ist_zustand(entity_id, ZUHAUSE):
                return True
        return False

    def _personen_stand(self) -> list:
        out = []
        for entity_id in store.get("scharfschaltung", "personen", default=[]) or []:
            eintrag = ha.zustand(entity_id)
            out.append({
                "entity_id": entity_id,
                "name": (eintrag or {}).get("attributes", {})
                        .get("friendly_name", entity_id),
                "zustand": (eintrag or {}).get("state"),
                "zuhause": bool(eintrag and eintrag.get("state") == ZUHAUSE),
            })
        return out

    # -------------------------------------------------------- Schlösser

    def _schloss_offen(self) -> bool:
        konfig = store.get("entschaerfung", default={}) or {}
        for entity_id in konfig.get("schloesser") or []:
            if ha.ist_zustand(entity_id, "unlocked", "open", "opening"):
                return True
        zustand_offen = konfig.get("zusatz_zustand", "unlocked")
        for entity_id in konfig.get("zusatzmelder") or []:
            if ha.ist_zustand(entity_id, zustand_offen):
                return True
        return False

    def _zu_seit(self) -> float:
        """Sekunden, seit das zuletzt abgeschlossene Schloss zu ist."""
        juengste = 999999.0
        for entity_id in store.get("entschaerfung", "schloesser", default=[]) or []:
            eintrag = ha.zustand(entity_id)
            if not eintrag or eintrag.get("state") != "locked":
                continue
            alter = _alter(eintrag.get("last_changed"))
            if alter is not None and alter < juengste:
                juengste = alter
        return juengste

    def _nachlaufsperre(self) -> tuple[bool, str]:
        """Gilt die Sperre nach einer Türöffnung gerade?

        Sie hängt am Schloss, nicht an einer festen Frist: Solange ein
        Schloss offen steht, ist jemand im Haus. Abgeschlossen wird von
        außen, deshalb endet sie kurz nach dem Abschließen. Die Obergrenze
        ab dem Aufschließen ist der Rückfallschutz – ein Schloss, das
        "abgeschlossen" nie meldet, darf die Anlage nicht dauerhaft blind
        machen.
        """
        konfig = store.get("entschaerfung", default={}) or {}
        seit = store.z_get("letzte_entsperrung")
        if not seit:
            return False, ""
        seit_offen = time.time() - seit
        if seit_offen > (konfig.get("nachlauf_hoechstens_minuten", 60) or 60) * 60:
            return False, ""
        if self._schloss_offen():
            return True, "Ein Schloss steht offen"
        if self._zu_seit() < (konfig.get("nachlauf_minuten", 5) or 5) * 60:
            return True, "Kurz nach dem Abschließen"
        return False, ""

    # ------------------------------------------------------ Melderauswahl

    def _melder_fuer(self, entity_id: str) -> list:
        return [m for m in store.melder()
                if m.get("entity") == entity_id and m.get("aktiv", True)]

    def _gilt_im_modus(self, melder: dict, modus: str | None) -> bool:
        modi = melder.get("modi") or []
        if not modi:
            # Kein Modus angehakt heißt: in jedem scharfen Modus.
            return True
        return modus in modi

    def offene_kontakte(self) -> list:
        """Kontakte, die gerade offen stehen – die Vorprüfung beim Schärfen."""
        out = []
        for melder in store.melder():
            if melder.get("art") != "kontakt" or not melder.get("aktiv", True):
                continue
            if ha.ist_zustand(melder.get("entity", ""),
                              melder.get("ausloesezustand", "on")):
                out.append({"id": melder.get("id"), "entity": melder.get("entity"),
                            "name": melder.get("name")})
        return out

    # ------------------------------------------------------ Ereigniseingang

    def _melder_ereignis(self, entity_id: str, alt, neu) -> None:
        neuer_zustand = (neu or {}).get("state")
        alter_zustand = (alt or {}).get("state")
        if neuer_zustand == alter_zustand:
            return

        with self._lock:
            # 1. Schloss aufgeschlossen -> das ist ein Ausweis.
            self._schloss_ereignis(entity_id, alter_zustand, neuer_zustand)
            # 2. Person gekommen oder gegangen.
            self._personen_ereignis(entity_id, neuer_zustand)
            # 3. Melder.
            for melder in self._melder_fuer(entity_id):
                aus = melder.get("ausloesezustand", "on")
                if neuer_zustand == aus:
                    self._melder_ausgeloest(melder)
                elif alter_zustand == aus:
                    self._melder_beruhigt(melder)
        self._veroeffentlichen()

    def _schloss_ereignis(self, entity_id, alt, neu) -> None:
        konfig = store.get("entschaerfung", default={}) or {}
        schloesser = konfig.get("schloesser") or []
        zusatz = konfig.get("zusatzmelder") or []
        if entity_id not in schloesser and entity_id not in zusatz:
            return
        offen_wert = "unlocked" if entity_id in schloesser else \
            konfig.get("zusatz_zustand", "unlocked")
        if neu != offen_wert:
            return

        # Es horchen bewusst alle Schlossmeldungen zugleich. Die Quellen
        # sind sich nicht einig: Ein Cloud-Schloss hinkt hinterher oder
        # schweigt ganz, während das lokale sofort meldet. Wer sich für
        # eine Quelle entscheidet, entscheidet sich irgendwann falsch.
        store.z_set(letzte_entsperrung=time.time())
        if self.panel == "disarmed":
            protokoll.schreiben("tuer", f"Aufgeschlossen ({entity_id}) – "
                                        "Anlage war bereits entschärft",
                                entity=entity_id)
            return
        protokoll.schreiben("tuer", f"Aufgeschlossen ({entity_id}) – entschärft",
                            entity=entity_id)
        self.entschaerfen("schloss", f"Haustür entsperrt ({entity_id})")

    def _personen_ereignis(self, entity_id, neu) -> None:
        if entity_id not in (store.get("scharfschaltung", "personen",
                                       default=[]) or []):
            return
        if neu == ZUHAUSE:
            self._leer_seit = None
            self._anwesenheit_auswerten(gerade_gekommen=True)

    # ----------------------------------------------------- Melderauswertung

    def _ruht_gerade(self, melder: dict) -> str:
        """Hat sich etwas bewegt, das diesen Melder erklärbar auslöst?

        Ein Präsenzmelder sieht den Rollladen im selben Zimmer fahren. Das
        ist keine Unzuverlässigkeit des Melders, sondern eine bekannte
        Ursache – und gegen bekannte Ursachen hilft kein Zeitfilter,
        sondern Wissen. Gibt den Grund zurück, oder "".
        """
        quellen = melder.get("ruhe_bei") or []
        if not quellen:
            return ""
        fenster = melder.get("ruhe_sekunden", 120) or 120
        for entity_id in quellen:
            eintrag = ha.zustand(entity_id)
            if not eintrag:
                continue
            alter = _alter(eintrag.get("last_changed"))
            if alter is not None and alter <= fenster:
                name = eintrag.get("attributes", {}).get("friendly_name",
                                                         entity_id)
                return f"{name} hat sich vor {int(alter)} s bewegt"
        return ""

    def _warten_lassen(self, melder: dict, ort: str) -> None:
        """Die Mindestdauer anlaufen lassen."""
        melder_id = melder.get("id")
        if melder_id in self._wartende:
            return
        dauer = melder.get("mindestdauer") or 0
        self._wartende[melder_id] = time.time() + dauer
        protokoll.schreiben("beobachtet",
                            f"{ort} – zählt erst, wenn es {dauer} s anhält",
                            melder=melder_id)

    def _wartende_pruefen(self) -> None:
        if not self._wartende:
            return
        jetzt = time.time()
        for melder_id, frist in list(self._wartende.items()):
            if jetzt < frist:
                continue
            self._wartende.pop(melder_id, None)
            melder = next((m for m in store.melder()
                           if m.get("id") == melder_id), None)
            if not melder:
                continue
            # Nur zählen, wenn es *immer noch* anliegt. Ein Melder, der
            # zwischendurch abgefallen und wieder angesprungen ist, hat
            # seine Mindestdauer nicht durchgehalten.
            if not ha.ist_zustand(melder.get("entity", ""),
                                  melder.get("ausloesezustand", "on")):
                continue
            with self._lock:
                self._melder_ausgeloest(melder, sofort=True)

    def _melder_ausgeloest(self, melder: dict, sofort: bool = False) -> None:
        linie_schluessel = melder.get("linie", "einbruch")
        linie = store.get("linien", linie_schluessel, default={}) or {}
        if not linie.get("aktiv", True):
            return

        ort = melder.get("ort") or melder.get("name") or melder.get("entity")

        if not sofort:
            grund = self._ruht_gerade(melder)
            if grund:
                protokoll.schreiben("beruhigt", f"{ort} übergangen – {grund}",
                                    melder=melder.get("id"))
                return
            if (melder.get("mindestdauer") or 0) > 0:
                self._warten_lassen(melder, ort)
                return

        if linie.get("geltung") == "immer":
            self._dauerlinie_ausgeloest(melder, linie_schluessel, ort)
            return

        # Ab hier: eine Linie, die nur im scharfen Zustand zählt.
        if self.panel not in SCHARF_ZUSTAENDE:
            return
        if melder.get("id") in (store.z_get("ueberbrueckt", []) or []):
            protokoll.schreiben("uebergangen", f"{ort} ist überbrückt",
                                melder=melder.get("id"))
            return
        if not self._gilt_im_modus(melder, store.z_get("modus")):
            return

        gesperrt, grund = self._nachlaufsperre()
        if gesperrt:
            self._unterdrueckung_melden(ort, grund)
            return

        # Der Auslöser wird sofort weggeschrieben, nicht erst beim Alarm:
        # Bis die Eintrittsverzögerung abgelaufen ist, hat längst ein
        # zweiter Melder angesprochen, und der überschriebe den ersten.
        store.z_set(ausloeser=f"{ort} um {time.strftime('%H:%M:%S')}",
                    ausloeser_zeit=time.time(),
                    ausloeser_linie=linie_schluessel,
                    ausloeser_text=melder.get("text", ""))

        eintrittszeit = self._modus(store.z_get("modus")).get("eintrittszeit", 45)
        if melder.get("verzoegert", True) and eintrittszeit > 0:
            self._nach("pending", frist=time.time() + eintrittszeit)
            protokoll.schreiben("voralarm",
                                f"{ort} – {eintrittszeit} s bis zum Alarm",
                                melder=melder.get("id"), linie=linie_schluessel)
            eskalation.ausfuehren(linie_schluessel, "voralarm", ausloeser=ort,
                                  rest=eintrittszeit,
                                  modus=self._modus(store.z_get("modus"))
                                  .get("name", ""))
        else:
            protokoll.schreiben("ausloesung", f"{ort} – sofort",
                                melder=melder.get("id"), linie=linie_schluessel)
            self._ausloesen(linie_schluessel)

    def _melder_beruhigt(self, melder: dict) -> None:
        if self._wartende.pop(melder.get("id"), None) is not None:
            protokoll.schreiben("beobachtet",
                                f"{melder.get('ort') or melder.get('name')} – "
                                "zu kurz, kein Alarm",
                                melder=melder.get("id"))
        linie_schluessel = melder.get("linie", "einbruch")
        linie = store.get("linien", linie_schluessel, default={}) or {}
        if linie.get("geltung") != "immer":
            return
        offene = store.z_get("offene_alarme", {}) or {}
        if melder.get("id") not in offene:
            return
        offene.pop(melder.get("id"), None)
        store.z_set(offene_alarme=offene)
        ort = melder.get("ort") or melder.get("name")
        protokoll.schreiben("entwarnung", f"{ort} meldet nichts mehr",
                            melder=melder.get("id"), linie=linie_schluessel)
        # Der eigene Text gilt nur für den Alarm. Die Entwarnung sagt, dass
        # nichts mehr anliegt - dafür taugt derselbe Satz nicht.
        eskalation.ausfuehren(linie_schluessel, "entwarnung",
                              art=melder.get("art", ""), ort=ort)
        if not offene:
            eskalation.zuruecknehmen(linie_schluessel, "alarm")

    def _dauerlinie_ausgeloest(self, melder, linie_schluessel, ort) -> None:
        """Rauch, Wasser – gilt rund um die Uhr und rührt das Panel nicht an."""
        offene = store.z_get("offene_alarme", {}) or {}
        if melder.get("id") in offene:
            return
        offene[melder.get("id")] = {"ort": ort, "zeit": time.time(),
                                    "linie": linie_schluessel}
        store.z_set(offene_alarme=offene)
        protokoll.schreiben("alarm", f"{linie_schluessel}: {ort}",
                            melder=melder.get("id"), linie=linie_schluessel)
        eskalation.ausfuehren(linie_schluessel, "alarm",
                              text_vorrang=melder.get("text", ""),
                              art=melder.get("art", ""),
                              ort=ort, ausloeser=ort,
                              zeit=time.strftime("%H:%M"))

    def _unterdrueckung_melden(self, ort: str, grund: str) -> None:
        """Eine unterdrückte Bewegung soll sichtbar bleiben, nicht hörbar.

        In einer einzigen Nacht kamen hier einmal 82 Meldungen zusammen,
        weil ein Schloss stundenlang "aufgeschlossen" meldete. Kein
        einziger Alarm, aber 82 Wecker.
        """
        konfig = store.get("entschaerfung", default={}) or {}
        if not konfig.get("melden", True):
            return
        abstand = (konfig.get("meldung_abstand_minuten", 30) or 30) * 60
        letzte = store.z_get("letzte_unterdrueckungsmeldung")
        protokoll.schreiben("unterdrueckt", f"{ort} – {grund}")
        if letzte and time.time() - letzte < abstand:
            return
        store.z_set(letzte_unterdrueckungsmeldung=time.time())
        if store.get("betrieb", "trockenlauf", default=True):
            return
        for dienst in (eskalation.stufe("einbruch", "alarm").get("push") or []):
            bereich, _, name = dienst.partition(".")
            ha.dienst(bereich, name, {
                "title": "Bewegung unterdrückt",
                "message": f"{ort} um {time.strftime('%H:%M')} – kein Alarm, "
                           f"{grund.lower()}.",
            })

    # -------------------------------------------------------- Übergänge

    def _nach(self, panel: str, frist: float | None = None,
              modus: str | None = ...) -> None:
        felder = {"panel": panel, "seit": time.time(), "frist": frist}
        if modus is not ...:
            felder["modus"] = modus
        store.z_set(**felder)
        self._veroeffentlichen()

    def _ausloesen(self, linie_schluessel: str = "einbruch") -> None:
        linie = store.get("linien", linie_schluessel, default={}) or {}
        dauer = linie.get("ausloesezeit", 300) or 0
        self._nach("triggered", frist=time.time() + dauer if dauer else None)
        modus = self._modus(store.z_get("modus"))
        eskalation.ausfuehren(linie_schluessel, "alarm",
                              text_vorrang=store.z_get("ausloeser_text") or "",
                              ausloeser=store.z_get("ausloeser") or "",
                              ort=store.z_get("ausloeser") or "",
                              modus=modus.get("name", ""),
                              zeit=time.strftime("%H:%M"))
        protokoll.schreiben("alarm", f"Alarm: {store.z_get('ausloeser')}",
                            linie=linie_schluessel)

    def scharf_schalten(self, modus_schluessel: str, quelle: str = "hand",
                        sofort: bool = False) -> dict:
        """Scharf schalten. Gibt zurück, was daraus geworden ist."""
        with self._lock:
            modus = self._modus(modus_schluessel)
            if not modus:
                return {"ok": False, "grund": "unbekannter_modus"}

            # Steht die Anlage schon so oder ist sie gerade dabei, wird
            # nichts angefasst: Jede Wiederholung startete sonst die
            # Ausgehverzögerung von vorn, und die Anlage käme nie scharf.
            ziel = modus.get("panel_zustand", "armed_away")
            if self.panel == ziel and store.z_get("modus") == modus_schluessel:
                return {"ok": True, "grund": "bereits_scharf"}
            if self.panel == "arming" and store.z_get("modus") == modus_schluessel:
                return {"ok": True, "grund": "schaltet_bereits"}

            if store.get("scharfschaltung", "nie_scharf_wenn_jemand_da",
                         default=True) and self._jemand_da():
                protokoll.schreiben("verhindert",
                                    "Nicht scharf geschaltet – jemand ist zu Hause",
                                    quelle=quelle)
                return {"ok": False, "grund": "jemand_da"}

            offen = self.offene_kontakte()
            umgang = store.get("vorpruefung", "offene_kontakte", default="melden")
            if offen and umgang == "verhindern":
                protokoll.schreiben("verhindert",
                                    "Nicht scharf geschaltet – offene Kontakte: "
                                    + ", ".join(o["name"] for o in offen),
                                    quelle=quelle)
                return {"ok": False, "grund": "offene_kontakte", "offen": offen}
            if offen and umgang == "ueberbruecken":
                store.z_set(ueberbrueckt=[o["id"] for o in offen])
                protokoll.schreiben("ueberbrueckt",
                                    "Überbrückt: " + ", ".join(o["name"]
                                                               for o in offen))
            else:
                store.z_set(ueberbrueckt=[])
                if offen:
                    protokoll.schreiben("hinweis",
                                        "Offen beim Scharfschalten: "
                                        + ", ".join(o["name"] for o in offen))

            # Der Hausmodus wird mitgezogen. Ohne das schaltet die
            # Oberfläche scharf, der Takt sieht zehn Sekunden später einen
            # Hausmodus "Zuhause" und entschärft wieder – ein Knopf, der
            # sichtbar nichts tut, ist schlimmer als gar keiner.
            if self.hausmodus != modus_schluessel:
                store.z_set(hausmodus=modus_schluessel)
            store.z_set(entschaerft_durch=None)

            ausgehzeit = 0 if sofort else (modus.get("ausgehzeit", 0) or 0)
            if ausgehzeit > 0:
                self._nach("arming", frist=time.time() + ausgehzeit,
                           modus=modus_schluessel)
                protokoll.schreiben("schaltet", f"{modus.get('name')} in "
                                                f"{ausgehzeit} s", quelle=quelle)
            else:
                self._nach(ziel, frist=None, modus=modus_schluessel)
                protokoll.schreiben("scharf", f"Scharf: {modus.get('name')}",
                                    quelle=quelle)
            return {"ok": True, "grund": "geschaltet"}

    def entschaerfen(self, quelle: str = "hand", text: str = "",
                     auch_hausmodus: bool = False) -> dict:  # noqa: D401
        """Entschärfen.

        ``auch_hausmodus`` unterscheidet zwei grundverschiedene Fälle. Ein
        Mensch, der auf "Entschärfen" drückt, meint auch den Sollzustand –
        sonst schaltet der Takt sofort wieder scharf. Das Aufschließen der
        Haustür meint ihn *nicht*: Der Hausmodus bleibt "Abwesend", und die
        Anlage kommt nach der Sperrfrist von selbst zurück.
        """
        with self._lock:
            war = self.panel
            if auch_hausmodus and self.hausmodus != "zuhause":
                store.z_set(hausmodus="zuhause")
            if war == "disarmed":
                return {"ok": True, "grund": "bereits_entschaerft"}
            self._nach("disarmed", frist=None, modus=None)
            # **Warum** entschärft wurde, entscheidet über den Weg zurück:
            # Nur wenn das Schloss es war, steht jemand im Haus und das
            # Schloss darf das Schärfen aufhalten.
            store.z_set(ueberbrueckt=[], entschaerft_durch=quelle)
            protokoll.schreiben("entschaerft", text or f"Entschärft ({quelle})",
                                quelle=quelle, vorher=war)
            if war == "triggered":
                eskalation.ausfuehren("einbruch", "entwarnung",
                                      ausloeser=store.z_get("ausloeser") or "",
                                      zeit=time.strftime("%H:%M"))
                eskalation.zuruecknehmen("einbruch", "alarm")
            elif war == "pending":
                eskalation.meldung_loeschen("einbruch", "voralarm")
            return {"ok": True, "grund": "entschaerft"}

    def hausmodus_setzen(self, schluessel: str, quelle: str = "hand") -> dict:
        """Den Sollzustand setzen. Was daraus wird, entscheidet der Takt."""
        with self._lock:
            if schluessel != "zuhause" and not self._modus(schluessel):
                return {"ok": False, "grund": "unbekannter_modus"}
            if self.hausmodus == schluessel:
                return {"ok": True, "grund": "unveraendert"}
            # Ein neu gesetzter Scharfmodus ist eine frische Absicht und
            # hebt eine Entschärfung am Schloss auf - sonst käme die Anlage
            # nach einem Weggang nie mehr scharf.
            store.z_set(hausmodus=schluessel,
                        entschaerft_durch=None if schluessel != "zuhause"
                        else store.z_get("entschaerft_durch"))
            protokoll.schreiben("hausmodus", f"Hausmodus: {schluessel}",
                                quelle=quelle)
        self._sollzustand_durchsetzen(quelle=quelle)
        return {"ok": True}

    # ------------------------------------------------------------- Takt

    def _takten(self) -> None:
        letzte_pruefung = 0.0
        while not self._stop.is_set():
            try:
                self._fristen_pruefen()
                self._wartende_pruefen()
                # Läuft eine Frist, wird jede Sekunde veröffentlicht. Sonst
                # bekäme eine Dashboard-Karte den Rest nur alle zehn
                # Sekunden zu sehen und müsste die Lücke raten - und beim
                # Zählen von 45 auf 0 fällt jede Ungenauigkeit auf.
                if store.z_get("frist"):
                    self._veroeffentlichen(sofort=False)
                # Die Anwesenheit wird abgefragt, nicht nur über Ereignisse
                # geführt: Die Leerlauf-Frist läuft ab, ohne dass irgendwo
                # etwas passiert, und ein Ereignis während einer Trennung
                # käme nie an.
                if time.time() - letzte_pruefung >= 10:
                    letzte_pruefung = time.time()
                    self._anwesenheit_auswerten()
                    self._sollzustand_durchsetzen()
                    self._veroeffentlichen(sofort=False)
            except Exception as err:  # noqa: BLE001
                log.exception("Fehler im Takt: %s", err)
            self._stop.wait(TAKT)

    def _fristen_pruefen(self) -> None:
        frist = store.z_get("frist")
        if not frist or time.time() < frist:
            return
        with self._lock:
            panel = self.panel
            modus = store.z_get("modus")
            if panel == "arming":
                self._nach(self._panel_zustand(modus), frist=None)
                protokoll.schreiben("scharf",
                                    f"Scharf: {self._modus(modus).get('name')}")
            elif panel == "pending":
                self._ausloesen(store.z_get("ausloeser_linie") or "einbruch")
            elif panel == "triggered":
                # Nach der Auslösezeit von selbst wieder scharf. Das ist
                # die Stelle, an der eine Anlage im Haus mit anwesenden
                # Menschen im Fünfminutentakt weiter alarmiert – deshalb
                # gilt die Nachlaufsperre auch hier.
                self._nach(self._panel_zustand(modus), frist=None)
                eskalation.zuruecknehmen("einbruch", "alarm")
                protokoll.schreiben("scharf", "Auslösezeit vorbei – wieder scharf")
            else:
                store.z_set(frist=None)

    def _abgleichen(self) -> None:
        """Nach einem Verbindungsabriss: hat sich etwas geändert?

        Ein Melder, der während der Trennung angesprungen und wieder
        ruhig geworden ist, bleibt unbemerkt – das ist hinnehmbar. Ein
        Melder, der noch *steht*, nicht.
        """
        with self._lock:
            if self.panel in SCHARF_ZUSTAENDE:
                for melder in store.melder():
                    if not melder.get("aktiv", True):
                        continue
                    if ha.ist_zustand(melder.get("entity", ""),
                                      melder.get("ausloesezustand", "on")):
                        self._melder_ausgeloest(melder)
        self._veroeffentlichen()

    # --------------------------------------------------- Scharfschaltung

    def _anwesenheit_auswerten(self, gerade_gekommen: bool = False) -> None:
        """Den Hausmodus der Anwesenheit nachführen."""
        scharf = store.get("scharfschaltung", default={}) or {}
        if scharf.get("quelle") != "anwesenheit":
            return
        if not store.get("betrieb", "automatik", default=True):
            return
        handmodus = scharf.get("handmodus") or ""
        if handmodus and self.hausmodus == handmodus:
            # Urlaub kippt nicht, weil einer kurz heimkommt. Er wird von
            # Hand gesetzt und von Hand beendet.
            return

        jemand_da = self._jemand_da()
        if jemand_da:
            self._leer_seit = None
            if self.hausmodus != "zuhause":
                protokoll.schreiben("hausmodus",
                                    "Jemand ist zu Hause – Hausmodus: Zuhause",
                                    quelle="anwesenheit")
                store.z_set(hausmodus="zuhause")
            return

        if self._leer_seit is None:
            self._leer_seit = time.time()
            return
        frist = scharf.get("leer_sekunden", 300) or 0
        if time.time() - self._leer_seit < frist:
            return
        ziel = scharf.get("modus_leer") or "abwesend"
        if self.hausmodus != ziel:
            protokoll.schreiben("hausmodus",
                                f"Niemand da seit {int(frist / 60)} min – "
                                f"Hausmodus: {self._modus(ziel).get('name', ziel)}",
                                quelle="anwesenheit")
            store.z_set(hausmodus=ziel)

    def _sollzustand_durchsetzen(self, quelle: str = "automatik") -> None:
        """Panel-Zustand an den Hausmodus angleichen.

        Hier laufen die drei Bedingungen zusammen, die in den alten
        Automationen dreimal einzeln standen: niemand zu Hause, kein
        Schloss offen, und nach einer Türöffnung erst nach der Sperrfrist.
        """
        if not store.get("betrieb", "automatik", default=True):
            return
        modus = self.hausmodus
        panel = self.panel

        if modus == "zuhause":
            if panel != "disarmed":
                self.entschaerfen("automatik", "Hausmodus Zuhause – entschärft")
            return

        if panel in ("pending", "triggered"):
            return
        if store.get("scharfschaltung", "nie_scharf_wenn_jemand_da",
                     default=True) and self._jemand_da():
            return
        # Das Schloss hält das Schärfen nur dort auf, wo es etwas bedeutet:
        # nachdem es die Anlage selbst entschärft hat. Ein Schloss im
        # Zustand "unlocked" heißt sonst nämlich nicht "Tür offen", sondern
        # nur "Riegel nicht vorgeschoben" - in vielen Haushalten der
        # Normalzustand rund um die Uhr. Wer daraus eine Bedingung fürs
        # Schärfen macht, baut eine Anlage, die nie scharf wird und dabei
        # gesund aussieht.
        if panel == "disarmed" \
                and store.z_get("entschaerft_durch") == "schloss" \
                and not self._darf_wieder_scharf():
            return
        self.scharf_schalten(modus, quelle=quelle)

    def _darf_wieder_scharf(self) -> bool:
        """Nach einer Türöffnung: ist es Zeit?

        Zwei Wege zurück – der übliche zehn Minuten nach dem Abschließen,
        der andere nach ein paar Stunden Entschärftsein. Der zweite ist
        Rückfallschutz für ein Schloss, das "abgeschlossen" nie meldet;
        ohne ihn bliebe die Anlage nach einmal Aufschließen für immer aus.
        """
        konfig = store.get("entschaerfung", default={}) or {}
        entsperrt = store.z_get("letzte_entsperrung")
        if not entsperrt:
            return True
        # Obergrenze ab dem Aufschließen - dieselbe wie bei der
        # Nachlaufsperre, aus demselben Grund: Ein Schloss, das
        # "abgeschlossen" nie meldet, darf die Anlage weder blind machen
        # noch dauerhaft unscharf halten.
        hoechstens = (konfig.get("nachlauf_hoechstens_minuten", 60) or 60) * 60
        if time.time() - entsperrt >= hoechstens:
            return True
        seit_entschaerft = time.time() - (store.z_get("seit") or 0)
        if seit_entschaerft >= (konfig.get("rueckfall_stunden", 2) or 2) * 3600:
            return True
        if self._schloss_offen():
            return False
        return self._zu_seit() >= (konfig.get("wieder_scharf_minuten", 10) or 10) * 60

    # --------------------------------------------------------- Handgriffe

    def ueberbruecken(self, melder_id: str, an: bool) -> None:
        with self._lock:
            liste = store.z_get("ueberbrueckt", []) or []
            if an and melder_id not in liste:
                liste.append(melder_id)
            elif not an and melder_id in liste:
                liste.remove(melder_id)
            store.z_set(ueberbrueckt=liste)
        self._veroeffentlichen()

    def alarme_quittieren(self) -> None:
        """Offene Dauerlinien-Alarme (Rauch, Wasser) von Hand schließen."""
        with self._lock:
            offene = store.z_get("offene_alarme", {}) or {}
            linien = {e.get("linie") for e in offene.values()}
            store.z_set(offene_alarme={})
            for linie in linien:
                eskalation.zuruecknehmen(linie, "alarm")
                eskalation.meldung_loeschen(linie, "alarm")
            protokoll.schreiben("quittiert", "Alarme quittiert")
        self._veroeffentlichen()


def _alter(zeitstempel: str | None) -> float | None:
    if not zeitstempel:
        return None
    try:
        from datetime import datetime, timezone
        wann = datetime.fromisoformat(zeitstempel.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - wann).total_seconds()
    except ValueError:
        return None


anlage = Anlage()
