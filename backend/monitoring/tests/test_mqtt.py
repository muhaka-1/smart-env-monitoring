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

    def test_out_of_range_values_rejected_without_saving(self):
        for metric, value in (("turbidity", -0.1), ("temperature", -5.1), ("temperature", 50.1)):
            with self.subTest(metric=metric, value=value):
                payload = json.dumps({"sensor_id": "a", "timestamp": "2026-01-01T10:00:00Z", "metric": metric, "value": value})
                with self.assertLogs("monitoring.mqtt_consumer", level="ERROR"):
                    result = self.ing.handle_message("beach/a/readings", payload.encode())
                self.assertIsNone(result)
                self.assertEqual(Reading.objects.count(), 0)

    def test_range_boundaries_saved(self):
        for index, (metric, value) in enumerate((("turbidity", 0), ("temperature", -5), ("temperature", 50))):
            with self.subTest(metric=metric, value=value):
                sensor = f"boundary-{index}"
                payload = json.dumps({"sensor_id": sensor, "timestamp": "2026-01-01T10:00:00Z", "metric": metric, "value": value})
                result = self.ing.handle_message(f"beach/{sensor}/readings", payload.encode())
                self.assertIsNotNone(result)
                self.assertEqual(Reading.objects.get(pk=result.pk).value, value)
