"""Zustandsänderungen aus Home Assistant, über WebSocket.

Warum nicht abfragen: Eine Alarmanlage muss in dem Augenblick reagieren, in
dem ein Melder anspringt. Ein Abfragetakt von zwei Sekunden verschenkt im
Mittel eine Sekunde und belastet dabei die Kiste dauerhaft; ein Takt von
dreißig Sekunden übersieht den kurzen Ausschlag eines Bewegungsmelders
ganz.

``subscribe_trigger`` lässt Home Assistant filtern. Das ist der
Unterschied zu ``subscribe_events`` mit ``state_changed``: dort käme jede
Änderung jeder der paar tausend Entitäten über die Leitung, und dieses
Add-on würfe 99 % davon weg.

Die Liste der beobachteten Entitäten ändert sich, sobald jemand einen
Melder hinzufügt. Dann wird ab- und neu angemeldet – deshalb hält diese
Klasse die Anmeldung selbst und nicht der Aufrufer.
"""

import json
import logging
import os
import threading
import time

log = logging.getLogger("alarm.ereignisse")

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
WS_URL = "ws://supervisor/core/websocket"

# Nach einem Abriss: zügig wieder verbinden, aber nicht im Kreis rennen.
WARTEN_MIN = 2
WARTEN_MAX = 30


class Ereignisstrom:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._entitaeten: list[str] = []
        self._neu_anmelden = threading.Event()
        self.verbunden = False
        self.letzter_fehler: str | None = None
        # Wird von außen gesetzt: nimmt (entity_id, alt, neu) entgegen.
        # alt/neu sind die vollen Zustandsobjekte oder None.
        self.on_change = None
        # Wird nach jedem (Neu-)Verbinden gerufen – die Anlage gleicht
        # dann ab, ob sie während der Trennung etwas verpasst hat.
        self.on_verbunden = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._laufen, daemon=True,
                                        name="ha-ereignisse")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def beobachten(self, entitaeten) -> None:
        """Die Liste der beobachteten Entitäten setzen."""
        neu = sorted({e for e in entitaeten if e})
        with self._lock:
            if neu == self._entitaeten:
                return
            self._entitaeten = neu
        log.info("Beobachtet werden %d Entitäten", len(neu))
        self._neu_anmelden.set()

    # ---------------------------------------------------------- innerhalb

    def _laufen(self) -> None:
        wartezeit = WARTEN_MIN
        while not self._stop.is_set():
            try:
                self._sitzung()
                wartezeit = WARTEN_MIN
            except Exception as err:  # noqa: BLE001
                self.verbunden = False
                self.letzter_fehler = str(err)[:200]
                log.warning("Ereignisstrom abgerissen: %s", err)
            if self._stop.is_set():
                return
            time.sleep(wartezeit)
            wartezeit = min(wartezeit * 2, WARTEN_MAX)

    def _sitzung(self) -> None:
        import websocket  # noqa: PLC0415 – nur hier gebraucht

        if not SUPERVISOR_TOKEN:
            raise RuntimeError("Kein SUPERVISOR_TOKEN")

        ws = websocket.create_connection(WS_URL, timeout=30)
        try:
            ws.recv()  # auth_required
            ws.send(json.dumps({"type": "auth", "access_token": SUPERVISOR_TOKEN}))
            antwort = json.loads(ws.recv())
            if antwort.get("type") != "auth_ok":
                raise RuntimeError("Anmeldung abgelehnt")

            self.verbunden = True
            self.letzter_fehler = None
            log.info("Mit Home Assistant verbunden")

            naechste_id = 1
            anmeldung_id = None
            # Der Empfang läuft mit Zeitgrenze, damit ein Wechsel der
            # Melderliste nicht bis zum nächsten Ereignis warten muss.
            ws.settimeout(1.0)

            if self.on_verbunden:
                self.on_verbunden()

            while not self._stop.is_set():
                if self._neu_anmelden.is_set() or anmeldung_id is None:
                    self._neu_anmelden.clear()
                    if anmeldung_id is not None:
                        ws.send(json.dumps({"id": naechste_id,
                                            "type": "unsubscribe_events",
                                            "subscription": anmeldung_id}))
                        naechste_id += 1
                    with self._lock:
                        liste = list(self._entitaeten)
                    if liste:
                        anmeldung_id = naechste_id
                        ws.send(json.dumps({
                            "id": anmeldung_id,
                            "type": "subscribe_trigger",
                            "trigger": {"platform": "state",
                                        "entity_id": liste},
                        }))
                        naechste_id += 1
                    else:
                        anmeldung_id = None

                try:
                    roh = ws.recv()
                except Exception as err:  # noqa: BLE001
                    if "timed out" in str(err).lower():
                        continue
                    raise

                if not roh:
                    continue
                try:
                    nachricht = json.loads(roh)
                except ValueError:
                    continue
                if nachricht.get("type") != "event":
                    continue
                ausloeser = (nachricht.get("event") or {}).get("variables", {}) \
                    .get("trigger", {})
                entity_id = ausloeser.get("entity_id")
                if not entity_id or not self.on_change:
                    continue
                try:
                    self.on_change(entity_id,
                                   ausloeser.get("from_state"),
                                   ausloeser.get("to_state"))
                except Exception as err:  # noqa: BLE001
                    log.exception("Fehler beim Verarbeiten von %s: %s",
                                  entity_id, err)
        finally:
            self.verbunden = False
            try:
                ws.close()
            except Exception:  # noqa: BLE001
                pass


strom = Ereignisstrom()
