import json
import os
from unittest.mock import MagicMock, patch

from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase

from monitoring.models import Reading
from monitoring.mqtt_consumer import MqttIngestor, default_client_id


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

    def test_unexpected_error_does_not_crash_consumer(self):
        msg = json.dumps({"sensor_id": "a", "timestamp": "2026-01-01T10:00:00Z", "value": 3})
        with patch("monitoring.mqtt_consumer.services.ingest_reading", side_effect=DatabaseError("NOT NULL constraint failed")):
            self.assertIsNone(self.ing.handle_message("beach/a/readings", msg.encode()))   # kastar inte vidare
        # nästa meddelande hanteras som vanligt
        self.assertIsNotNone(self.ing.handle_message("beach/a/readings", msg.encode()))


class ClientIdTests(SimpleTestCase):
    def test_default_id_is_unique_per_process_and_overridable(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MQTT_CLIENT_ID", None)
            cid = default_client_id()
            self.assertTrue(cid.startswith("django-ingestor-"))
            self.assertIn(str(os.getpid()), cid)
        with patch.dict(os.environ, {"MQTT_CLIENT_ID": "min-mottagare"}):
            self.assertEqual(default_client_id(), "min-mottagare")


class StartupTests(SimpleTestCase):
    def test_run_retries_first_connection_instead_of_crashing(self):
        with patch("monitoring.mqtt_consumer.mqtt.Client") as client_cls:
            client = client_cls.return_value = MagicMock()
            MqttIngestor("localhost", 1883, "beach/+/readings").run()
        client.connect_async.assert_called_once()          # ingen blockerande connect() som kastar om brokern är nere
        client.connect.assert_not_called()
        client.loop_forever.assert_called_once_with(retry_first_connection=True)
        client.reconnect_delay_set.assert_called_once()
