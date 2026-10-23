"""Transportlager. En publisher gör ETT försök; retry hanteras av simulatorn."""
import json
import logging
from abc import ABC, abstractmethod

import paho.mqtt.client as mqtt
import requests

from .config import Config

log = logging.getLogger(__name__)


class TransientError(Exception):
    """Tillfälligt fel (nätverk, 5xx) - värt att försöka igen."""


class PermanentError(Exception):
    """Servern avvisade datan (4xx) - retry hjälper inte."""


class Publisher(ABC):
    @abstractmethod
    def send(self, message: dict) -> None: ...

    def close(self) -> None:
        pass


class HttpPublisher(Publisher):
    def __init__(self, cfg: Config, session: requests.Session | None = None):
        self.cfg = cfg
        self.session = session or requests.Session()
        if cfg.api_key:
            self.session.headers["X-API-Key"] = cfg.api_key

    def send(self, message: dict) -> None:
        try:
            resp = self.session.post(self.cfg.api_url, json=message, timeout=self.cfg.request_timeout)
        except requests.RequestException as exc:
            raise TransientError(str(exc)) from exc
        if resp.status_code >= 500 or resp.status_code in (408, 429):
            raise TransientError(f"HTTP {resp.status_code}")
        if resp.status_code >= 400:
            raise PermanentError(f"HTTP {resp.status_code}: {resp.text[:200]}")


class MqttPublisher(Publisher):
    def __init__(self, cfg: Config, client: mqtt.Client | None = None):
        self.cfg = cfg
        self.client = client or mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="beach-sensor-sim")
        self._connected = False

    def _ensure_connected(self):
        if self._connected:
            return
        try:
            self.client.connect(self.cfg.mqtt_host, self.cfg.mqtt_port, keepalive=60)
        except OSError as exc:
            raise TransientError(f"Kan inte ansluta till broker: {exc}") from exc
        self.client.loop_start()
        self._connected = True

    def send(self, message: dict) -> None:
        self._ensure_connected()
        topic = self.cfg.mqtt_topic_template.format(sensor_id=message["sensor_id"])
        try:
            info = self.client.publish(topic, json.dumps(message), qos=1)
            info.wait_for_publish(timeout=self.cfg.request_timeout)
        except (RuntimeError, ValueError) as exc:
            raise TransientError(str(exc)) from exc
        if not info.is_published():
            raise TransientError("Publicering bekräftades inte i tid")

    def close(self) -> None:
        if self._connected:
            self.client.loop_stop()
            self.client.disconnect()


def create_publisher(cfg: Config) -> Publisher:
    if cfg.transport == "http":
        return HttpPublisher(cfg)
    if cfg.transport == "mqtt":
        return MqttPublisher(cfg)
    raise ValueError(f"Okänd transport: {cfg.transport!r} (använd 'mqtt' eller 'http')")
