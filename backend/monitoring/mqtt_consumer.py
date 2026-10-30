"""MQTT-konsument: prenumererar på sensortopics och sparar giltiga mätningar."""
import json
import logging

import paho.mqtt.client as mqtt
from rest_framework.exceptions import ValidationError

from . import services

log = logging.getLogger(__name__)


class MqttIngestor:
    def __init__(self, host, port, topic):
        self.host, self.port, self.topic = host, port, topic
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="django-ingestor")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def handle_message(self, topic: str, raw: bytes):
        """Testbar kärnlogik: returnerar Reading, eller None om meddelandet avvisas."""
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("payload måste vara ett JSON-objekt")
        except (ValueError, UnicodeDecodeError) as exc:
            log.error("Ogiltig JSON på %s: %s", topic, exc)
            return None
        try:
            reading = services.ingest_reading(payload)
        except ValidationError as exc:
            log.error("Avvisade data på %s: %s", topic, exc.detail)
            return None
        log.info("Sparade %s", reading)
        return reading

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        log.info("Ansluten till broker (%s). Prenumererar på %s", reason_code, self.topic)
        client.subscribe(self.topic, qos=1)  # körs även vid reconnect

    def _on_message(self, client, userdata, msg):
        self.handle_message(msg.topic, msg.payload)

    def run(self):
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.connect(self.host, self.port, keepalive=60)
        self.client.loop_forever(retry_first_connection=True)
