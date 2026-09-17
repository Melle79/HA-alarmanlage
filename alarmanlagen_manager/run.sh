#!/usr/bin/with-contenv bashio
# with-contenv ist Pflicht: ohne sie fehlen SUPERVISOR_TOKEN und die
# Zeitzone. Bei einer Alarmanlage wiegt das doppelt – ein Nachtmodus auf
# UTC schaltet in Mitteleuropa zwei Stunden zu früh.

export ADDON_VERSION="$(bashio::addon.version)"
export LOG_LEVEL="$(bashio::config 'log_level')"
export PORT=8102
export DATA_DIR=/data
export WWW_DIR=/www
export HA_WWW_DIR=/config/www
export HA_CONFIG_DIR=/config

export MQTT_ENABLED="$(bashio::config 'mqtt_enabled')"
if bashio::services.available 'mqtt'; then
  AUTO_HOST=$(bashio::services 'mqtt' 'host')
  AUTO_PORT=$(bashio::services 'mqtt' 'port')
  AUTO_USER=$(bashio::services 'mqtt' 'username')
  AUTO_PASS=$(bashio::services 'mqtt' 'password')
else
  AUTO_HOST=""; AUTO_PORT=""; AUTO_USER=""; AUTO_PASS=""
fi

CFG_HOST=$(bashio::config 'mqtt_host')
CFG_PORT=$(bashio::config 'mqtt_port')
CFG_USER=$(bashio::config 'mqtt_user')
CFG_PASS=$(bashio::config 'mqtt_password')

export MQTT_HOST="${CFG_HOST:-$AUTO_HOST}"
export MQTT_PORT="${CFG_PORT:-${AUTO_PORT:-1883}}"
export MQTT_USER="${CFG_USER:-$AUTO_USER}"
export MQTT_PASSWORD="${CFG_PASS:-$AUTO_PASS}"
export ENTITY_PRAEFIX="$(bashio::config 'entity_praefix')"

if [ "$MQTT_ENABLED" = "true" ] && [ -n "$MQTT_HOST" ]; then
  bashio::log.info "MQTT: ${MQTT_HOST}:${MQTT_PORT}"
else
  bashio::log.warning "Kein MQTT-Broker – ohne ihn gibt es kein Bedienfeld in Home Assistant"
fi

bashio::log.info "Alarmanlagen-Manager ${ADDON_VERSION} startet auf Port ${PORT}"

cd /app
exec python3 server.py
