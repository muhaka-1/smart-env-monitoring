"""Hela kedjan i ett test: riktig simulator -> HTTP -> riktig Django-server -> databas -> REST-API.

LiveServerTestCase startar en verklig webbserver med en tom testdatabas, så testet utgår alltid från ren start.
MQTT-vägen testas utan broker genom att mata mottagaren med exakt de meddelanden simulatorn bygger.
Manuell körning mot en lokal server: sensor/tools/verify_flow.py (se docs/end-to-end.md).
"""
import json
import re
import sys
import unittest
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase, TestCase, override_settings

from monitoring.mqtt_consumer import MqttIngestor

SENSOR_DIR = Path(settings.BASE_DIR).parent / "sensor"
HAS_SENSOR = (SENSOR_DIR / "sensor_sim").is_dir() and (SENSOR_DIR / "tools" / "verify_flow.py").is_file()


class SensorPathMixin:
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SENSOR_DIR))
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        sys.path.remove(str(SENSOR_DIR))


@unittest.skipUnless(HAS_SENSOR, "sensor/ saknas i checkouten")
class HttpChainTests(SensorPathMixin, LiveServerTestCase):
    @override_settings(INGEST_API_KEY="test-ingest-key")
    def test_simulator_to_api_over_http(self):
        from tools.verify_flow import format_report, run_flow

        user = get_user_model().objects.create_user(username="flow-reader", password="test-flow-password")
        checks = run_flow(
            self.live_server_url,
            count=4,
            interval=0.05,
            api_key="test-ingest-key",
            username=user.get_username(),
            password="test-flow-password",
        )
        self.assertTrue(all(c.ok for c in checks), "\n" + format_report(checks))
        self.assertGreaterEqual(len(checks), 4)   # backend, leverans, fält + minst en latest/history


@unittest.skipUnless(HAS_SENSOR, "sensor/ saknas i checkouten")
class MqttFormatChainTests(SensorPathMixin, TestCase):
    def test_simulator_messages_accepted_by_mqtt_consumer(self):
        from sensor_sim.config import Config
        from sensor_sim.data_source import load_measurements
        from sensor_sim.message import build_message

        cfg = Config()
        ingestor = MqttIngestor("localhost", 1883, "beach/+/readings")
        last = {}
        for measurement in load_measurements(cfg, offline=True)[:4]:
            message = build_message(measurement)
            topic = cfg.mqtt_topic_template.format(sensor_id=message["sensor_id"])
            self.assertRegex(topic, r"^beach/[^/]+/readings$")        # matchar mottagarens prenumeration beach/+/readings
            self.assertIsNotNone(ingestor.handle_message(topic, json.dumps(message).encode()), message)
            last[message["sensor_id"]] = message

        for sensor_id, message in last.items():
            response = self.client.get("/api/readings/latest/", {"sensor_id": sensor_id})
            self.assertEqual(response.status_code, 200)
            self.assertAlmostEqual(response.json()["value"], message["value"])
            self.assertEqual(response.json()["unit"], message["unit"])
        self.assertTrue(re.match(r"^beach/\+/readings$", ingestor.topic))
