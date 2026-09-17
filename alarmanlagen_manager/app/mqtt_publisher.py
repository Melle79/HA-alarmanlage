"""Die Anlage als Gerät in Home Assistant – über MQTT-Discovery.

Das Add-on bringt seine Bedienelemente selbst mit, statt sich auf Helfer
zu verlassen, die jemand von Hand angelegt hat. Bei einer Neuinstallation
gibt es die nämlich nicht, und ein Bedienfeld, das auf eine fehlende
Entität zeigt, schaltet nie.

Eine Regel, die hier teuer erkauft wurde und überall gilt: **Die
entity_id wird nie aus einem Namen zurückgerechnet.** Sie entsteht einmal
beim Anlegen und folgt keiner Umbenennung. Deshalb steht in jeder
Ankündigung ein festes ``object_id``, und die Modusnamen tauchen nur als
Anzeigetext auf, nie in einer ID.

Am Bedienfeld hängen alle Angaben als Attribute (``json_attributes_topic``).
Das ist Absicht: Die Dashboard-Karte kommt an den Ingress-Zugang nicht
heran, wohl aber an die Entität – so braucht sie keine zweite Quelle.
"""

import json
import logging
import os
import threading
import time

import paho.mqtt.client as mqtt

from store import store

log = logging.getLogger("alarm.mqtt")

DISCOVERY_PREFIX = os.environ.get("MQTT_DISCOVERY_PREFIX", "homeassistant")
KEEPALIVE = 60

PANEL_BEFEHLE = {
    "DISARM": ("entschaerfen", None),
    "ARM_AWAY": ("scharf", "armed_away"),
    "ARM_HOME": ("scharf", "armed_home"),
    "ARM_NIGHT": ("scharf", "armed_night"),
    "ARM_VACATION": ("scharf", "armed_vacation"),
}


class MqttPublisher:
    def __init__(self):
        self._lock = threading.Lock()
        self.client: mqtt.Client | None = None
        self.connected = False
        self.host = os.environ.get("MQTT_HOST", "")
        self.port = int(os.environ.get("MQTT_PORT") or 1883)
        self.user = os.environ.get("MQTT_USER", "")
        self.password = os.environ.get("MQTT_PASSWORD", "")
        self.enabled = os.environ.get("MQTT_ENABLED", "true").lower() == "true"
        self.letzter_fehler: str | None = None
        self._angekuendigt = False
        # Wird von außen gesetzt: nimmt (befehl, nutzlast).
        self.on_befehl = None

    # ---------------------------------------------------------- Verbindung

    def start(self) -> None:
        if not self.enabled or not self.host:
            log.warning("MQTT ist aus – es entsteht kein Bedienfeld")
            return
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                             client_id=f"alarmanlagen-manager-{int(time.time())}")
        if self.user:
            client.username_pw_set(self.user, self.password)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        # Stirbt das Add-on, sollen die Entitäten als nicht verfügbar
        # dastehen statt auf dem letzten Wert einzufrieren. Bei einer
        # Alarmanlage ist der Unterschied zwischen "scharf" und "weiß es
        # nicht mehr" der ganze Punkt.
        client.will_set(self._availability(), "offline", retain=True)
        self.client = client
        try:
            client.connect(self.host, self.port, KEEPALIVE)
            client.loop_start()
        except OSError as err:
            self.letzter_fehler = str(err)[:200]
            log.error("MQTT-Verbindung fehlgeschlagen: %s", err)

    def stop(self) -> None:
        if not self.client:
            return
        try:
            self.client.publish(self._availability(), "offline", retain=True)
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as err:  # noqa: BLE001
            log.warning("MQTT-Abmeldung unsauber: %s", err)

    def status(self) -> dict:
        return {"aktiv": self.enabled, "verbunden": self.connected,
                "host": self.host, "fehler": self.letzter_fehler}

    def _praefix(self) -> str:
        return store.get("betrieb", "entity_praefix", default="alarmanlage")

    def _availability(self) -> str:
        return f"{self._praefix()}/status"

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            log.error("MQTT-Verbindung abgelehnt: %s", reason_code)
            return
        self.connected = True
        self.letzter_fehler = None
        log.info("Mit dem MQTT-Broker verbunden")
        client.publish(self._availability(), "online", retain=True)
        client.subscribe(f"{self._praefix()}/+/set")
        # Nach einem Abriss erneut ankündigen – ein Broker ohne
        # Beständigkeit hat die Ankündigungen sonst vergessen.
        self._angekuendigt = False

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = False
        log.warning("MQTT-Verbindung verloren")

    def _on_message(self, client, userdata, msg):
        try:
            nutzlast = msg.payload.decode("utf-8", "replace")
            teile = msg.topic.split("/")
            if len(teile) != 3 or teile[2] != "set":
                return
            befehl = teile[1]
        except Exception as err:  # noqa: BLE001
            log.warning("Unlesbare MQTT-Nachricht: %s", err)
            return
        if self.on_befehl:
            try:
                self.on_befehl(befehl, nutzlast)
            except Exception as err:  # noqa: BLE001
                log.exception("Befehl %s fehlgeschlagen: %s", befehl, err)

    # ------------------------------------------------------- Ankündigung

    def _geraet(self) -> dict:
        return {
            "identifiers": [self._praefix()],
            "name": "Alarmanlage",
            "manufacturer": "Alarmanlagen-Manager",
            "model": "Einbruch- und Gefahrenmeldung",
            "sw_version": os.environ.get("ADDON_VERSION", ""),
        }

    def _config(self, komponente: str, object_id: str, inhalt: dict) -> None:
        if not self.client:
            return
        thema = f"{DISCOVERY_PREFIX}/{komponente}/{object_id}/config"
        self.client.publish(thema, json.dumps(inhalt, ensure_ascii=False),
                            retain=True)

    def ankuendigen(self, erzwingen: bool = False) -> None:
        """Alle Entitäten anmelden. Mehrfach aufrufen ist harmlos."""
        if not self.client or not self.connected:
            return
        if self._angekuendigt and not erzwingen:
            return
        p = self._praefix()
        geraet = self._geraet()
        verfuegbar = self._availability()

        modi = store.get("modi", default={}) or {}
        aktive = [(k, m) for k, m in modi.items() if m.get("aktiv", True)]
        aktive.sort(key=lambda kv: kv[1].get("reihenfolge", 99))
        merkmale = sorted({
            {"armed_away": "arm_away", "armed_home": "arm_home",
             "armed_night": "arm_night",
             "armed_vacation": "arm_vacation"}.get(m.get("panel_zustand"), "")
            for _, m in aktive
        } - {""})

        self._config("alarm_control_panel", f"{p}_panel", {
            "unique_id": f"{p}_panel",
            "object_id": p,
            "name": None,  # None = der Gerätename trägt die Entität
            "state_topic": f"{p}/panel",
            "command_topic": f"{p}/panel/set",
            "json_attributes_topic": f"{p}/attribute",
            "supported_features": merkmale,
            "code_arm_required": False,
            "code_disarm_required": False,
            "availability_topic": verfuegbar,
            "device": geraet,
        })

        optionen = ["Zuhause"] + [m.get("name", k) for k, m in aktive]
        self._config("select", f"{p}_hausmodus", {
            "unique_id": f"{p}_hausmodus",
            "object_id": f"{p}_hausmodus",
            "name": "Hausmodus",
            "state_topic": f"{p}/hausmodus",
            "command_topic": f"{p}/hausmodus/set",
            "options": optionen,
            "icon": "mdi:home-switch",
            "availability_topic": verfuegbar,
            "device": geraet,
        })

        for schluessel, name, symbol in (
            ("automatik", "Automatik", "mdi:auto-mode"),
            ("trockenlauf", "Trockenlauf", "mdi:test-tube"),
        ):
            self._config("switch", f"{p}_{schluessel}", {
                "unique_id": f"{p}_{schluessel}",
                "object_id": f"{p}_{schluessel}",
                "name": name,
                "state_topic": f"{p}/{schluessel}",
                "command_topic": f"{p}/{schluessel}/set",
                "payload_on": "ON", "payload_off": "OFF",
                # state_on/state_off ausdrücklich: ohne sie steht der
                # Schalter auf "unknown", sobald die Zustände klein
                # geschrieben ankommen.
                "state_on": "ON", "state_off": "OFF",
                "icon": symbol,
                "entity_category": "config",
                "availability_topic": verfuegbar,
                "device": geraet,
            })

        self._config("sensor", f"{p}_ausloeser", {
            "unique_id": f"{p}_ausloeser",
            "object_id": f"{p}_ausloeser",
            "name": "Letzter Auslöser",
            "state_topic": f"{p}/ausloeser",
            "icon": "mdi:alert-circle-outline",
            "availability_topic": verfuegbar,
            "device": geraet,
        })

        # Eigener Zeitstempel statt last_changed: Der springt bei jedem
        # Neustart von Home Assistant auf die Startzeit, und dann steht
        # "entschärft seit 16:37" auf der Karte, obwohl es seit vorgestern
        # so ist.
        self._config("sensor", f"{p}_seit", {
            "unique_id": f"{p}_seit",
            "object_id": f"{p}_seit",
            "name": "Zustand seit",
            "state_topic": f"{p}/seit",
            "device_class": "timestamp",
            "icon": "mdi:clock-outline",
            "availability_topic": verfuegbar,
            "device": geraet,
        })

        for schluessel, name, klasse, symbol in (
            ("rauch", "Rauch", "smoke", "mdi:smoke-detector-variant-alert"),
            ("wasser", "Wasser", "moisture", "mdi:water-alert"),
            ("offen", "Offene Kontakte", "opening", "mdi:door-open"),
        ):
            self._config("binary_sensor", f"{p}_{schluessel}", {
                "unique_id": f"{p}_{schluessel}",
                "object_id": f"{p}_{schluessel}",
                "name": name,
                "state_topic": f"{p}/{schluessel}",
                "payload_on": "ON", "payload_off": "OFF",
                "device_class": klasse,
                "icon": symbol,
                "availability_topic": verfuegbar,
                "device": geraet,
            })

        self._config("button", f"{p}_quittieren", {
            "unique_id": f"{p}_quittieren",
            "object_id": f"{p}_quittieren",
            "name": "Alarme quittieren",
            "command_topic": f"{p}/quittieren/set",
            "icon": "mdi:bell-check",
            "availability_topic": verfuegbar,
            "device": geraet,
        })

        self._angekuendigt = True
        log.info("Entitäten bei Home Assistant angemeldet")

    def erneut_ankuendigen(self) -> None:
        """Nach einer Änderung an den Modi: gleiche IDs, neue Auswahl."""
        self._angekuendigt = False
        self.ankuendigen()

    # ------------------------------------------------------------ Ausgabe

    def veroeffentlichen(self, zustand: dict) -> None:
        if not self.client or not self.connected:
            return
        self.ankuendigen()
        p = self._praefix()

        modi = store.get("modi", default={}) or {}
        hausmodus = zustand.get("hausmodus", "zuhause")
        anzeige = "Zuhause" if hausmodus == "zuhause" else \
            (modi.get(hausmodus, {}) or {}).get("name", hausmodus)

        offene_alarme = zustand.get("offene_alarme", {}) or {}
        rauch = any(a.get("linie") == "rauch" for a in offene_alarme.values())
        wasser = any(a.get("linie") == "wasser" for a in offene_alarme.values())

        werte = {
            "panel": zustand.get("panel", "disarmed"),
            "hausmodus": anzeige,
            "automatik": "ON" if zustand.get("automatik") else "OFF",
            "trockenlauf": "ON" if zustand.get("trockenlauf") else "OFF",
            "ausloeser": (zustand.get("ausloeser") or "—")[:255],
            "seit": _iso(zustand.get("seit")),
            "rauch": "ON" if rauch else "OFF",
            "wasser": "ON" if wasser else "OFF",
            "offen": "ON" if zustand.get("offene_kontakte") else "OFF",
        }
        for schluessel, wert in werte.items():
            self.client.publish(f"{p}/{schluessel}", wert, retain=True)

        attribute = {
            "modus": zustand.get("modus"),
            "modus_name": zustand.get("modus_name"),
            "hausmodus": hausmodus,
            "hausmodus_name": anzeige,
            "rest_sekunden": zustand.get("rest_sekunden"),
            "zustand_seit": _iso(zustand.get("seit")),
            "letzter_ausloeser": zustand.get("ausloeser"),
            "ausloeser_linie": zustand.get("ausloeser_linie"),
            "trockenlauf": zustand.get("trockenlauf"),
            "automatik": zustand.get("automatik"),
            "jemand_zuhause": zustand.get("jemand_da"),
            "nachlaufsperre": zustand.get("nachlaufsperre"),
            "offene_kontakte": [k.get("name") for k in
                                zustand.get("offene_kontakte", [])],
            "offene_alarme": [a.get("ort") for a in offene_alarme.values()],
            "ueberbrueckt": zustand.get("ueberbrueckt", []),
            "verbunden": zustand.get("verbunden"),
        }
        self.client.publish(f"{p}/attribute",
                            json.dumps(attribute, ensure_ascii=False),
                            retain=True)


def _iso(zeitstempel) -> str:
    """Zeitstempel als ISO mit Zeitzone – anders nimmt HA ihn nicht an."""
    if not zeitstempel:
        return ""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(zeitstempel, timezone.utc).astimezone() \
        .isoformat(timespec="seconds")


publisher = MqttPublisher()
