import json
from datetime import datetime, timedelta, timezone
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from monitoring import services
from monitoring.models import Alert, Notification, Reading
from monitoring.mqtt_consumer import MqttIngestor


def pdf_text(response):
    return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", INGEST_API_KEY="")
class MeasurementTypeTests(TestCase):
    def payload(self, metric, value):
        return {"sensor_id": "type-" + metric, "metric": metric,
                "timestamp": "2026-01-01T10:00:00Z", "value": value}

    def test_http_rejects_booleans_without_reading_alert_or_notification(self):
        for metric in ("temperature", "turbidity"):
            for value in (True, False):
                with self.subTest(metric=metric, value=value):
                    response = self.client.post(reverse("readings"), json.dumps(self.payload(metric, value)),
                                                content_type="application/json")
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("value", response.json())
                    self.assertFalse(Reading.objects.exists())
                    self.assertFalse(Alert.objects.exists())
                    self.assertFalse(Notification.objects.exists())

    def test_mqtt_rejects_booleans_without_side_effects(self):
        consumer = MqttIngestor("localhost", 1883, "beach/+/readings")
        for metric in ("temperature", "turbidity"):
            for value in (True, False):
                with self.subTest(metric=metric, value=value):
                    self.assertIsNone(consumer.handle_message("beach/type/readings",
                                      json.dumps(self.payload(metric, value)).encode()))
                    self.assertFalse(Reading.objects.exists())
                    self.assertFalse(Alert.objects.exists())
                    self.assertFalse(Notification.objects.exists())

    def test_numeric_zero_and_numbers_still_work_in_both_transports(self):
        consumer = MqttIngestor("localhost", 1883, "beach/+/readings")
        for metric in ("temperature", "turbidity"):
            for index, value in enumerate((0, 0.0, 12.5)):
                payload = self.payload(metric, value)
                payload["sensor_id"] += "-" + str(index)
                response = self.client.post(reverse("readings"), json.dumps(payload), content_type="application/json")
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["value"], value)
                payload["sensor_id"] += "-mqtt"
                self.assertEqual(consumer.handle_message("beach/type/readings", json.dumps(payload).encode()).value, value)
        self.assertEqual(Reading.objects.count(), 12)
        self.assertFalse(Alert.objects.exists())
        self.assertFalse(Notification.objects.exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class InternalNotificationEligibilityTests(TestCase):
    def test_login_without_deliverable_email_keeps_message_and_both_reports(self):
        User = get_user_model()
        blank = User.objects.create_user("blank-reader", "", "test-access-password")
        invalid = User.objects.create_user("invalid-reader", "not-an-address", "test-access-password")
        valid = User.objects.create_user("valid-reader", "valid@example.test", "test-access-password")
        inactive = User.objects.create_user("inactive-reader", "inactive@example.test", is_active=False)
        with self.captureOnCommitCallbacks(execute=True):
            reading = services.ingest_reading({"sensor_id": "rainbow-beach-turbidity", "metric": "turbidity",
                                              "timestamp": "2026-01-01T10:00:00Z", "value": 58.1})
        self.assertEqual(Notification.objects.filter(alert__reading=reading).count(), 3)
        self.assertFalse(Notification.objects.filter(user=inactive).exists())
        self.assertEqual([m.to for m in mail.outbox], [[valid.email]])
        self.assertEqual(Notification.objects.get(user=valid).delivery_status, "sent")
        for user in (blank, invalid):
            self.client.logout()
            self.assertTrue(self.client.login(username=user.username, password="test-access-password"))
            own = Notification.objects.get(user=user)
            self.assertEqual(own.delivery_status, "failed")
            self.assertTrue(own.delivery_error)
            self.assertIsNone(own.email_sent_at)
            page = self.client.get(reverse("message-list"))
            self.assertContains(page, "rainbow-beach-turbidity")
            self.assertContains(page, own.delivery_error)
            data = self.client.get(reverse("messages-api"), {"user_id": valid.pk}).json()
            self.assertEqual([x["id"] for x in data["results"]], [own.pk])
            self.assertNotIn(valid.email, json.dumps(data))
            self.assertContains(self.client.get(reverse("error-report")), "rainbow-beach-turbidity")
            response = self.client.get(reverse("error-report-pdf"))
            self.assertEqual(response.status_code, 200)
            text = pdf_text(response)
            self.assertIn("rainbow-beach-turbidity", text)
            self.assertIn("58.1", text)
