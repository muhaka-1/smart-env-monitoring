import json

from django.test import TestCase

from monitoring.models import Reading
from monitoring.mqtt_consumer import MqttIngestor


class MqttHandlerTests(TestCase):
    def setUp(self):
        self.ing = MqttIngestor("localhost", 1883, "beach/+/readings")

    def test_valid_message_saved(self):
        msg = json.dumps({"sensor_id": "a", "timestamp": "2026-01-01T10:00:00Z", "value": 3})
        self.assertIsNotNone(self.ing.handle_message("beach/a/readings", msg.encode()))
        self.assertEqual(Reading.objects.count(), 1)

    def test_invalid_json_and_data_rejected(self):
        self.assertIsNone(self.ing.handle_message("t", b"{not json"))
        self.assertIsNone(self.ing.handle_message("t", b'{"sensor_id": "a"}'))
        self.assertIsNone(self.ing.handle_message("t", b"[1,2]"))
        self.assertEqual(Reading.objects.count(), 0)
