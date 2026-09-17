ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip py3-yaml \
    && pip3 install --no-cache-dir --break-system-packages \
        flask \
        requests \
        paho-mqtt \
        websocket-client

# py3-yaml als Alpine-Paket statt per pip: PyYAML baut sonst eine
# C-Erweiterung und braucht dafür Compiler, die im Basisbild fehlen.
#
# websocket-client wird für zwei Dinge gebraucht: die Melder kommen über
# subscribe_trigger statt über Abfragen (eine Alarmanlage, die alle zwei
# Sekunden nachschaut, ist keine), und die Dashboard-Karte lässt sich nur
# über die WebSocket-API als Ressource anmelden.

COPY app /app
COPY www /www
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
