import json
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from monitoring import services
from monitoring.models import Alert, Notification, Reading
from monitoring.mqtt_consumer import MqttIngestor
from monitoring.notifications import create_alert, deliver_alert, deliver_notification

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PLATFORM_BASE_URL="https://monitor.example.test",
    ANOMALY_THRESHOLDS={"turbidity": 30, "temperature": 25},
)
class NotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.anna = User.objects.create_user("anna", "anna@example.test", "Test-Strand-2026!")
        cls.erik = User.objects.create_user("erik", "erik@example.test", "Test-Strand-2026!")
        User.objects.create_user("inactive", "inactive@example.test", is_active=False)
        User.objects.create_user("invalid", "not-an-address")
        User.objects.create_user("blank", "")
        User.objects.create_user("invited", "invited@example.test", is_active=False)

    def payload(self, **changes):
        return {"sensor_id": "oak-temperature", "metric": "temperature", "timestamp": "2026-01-01T10:00:00Z", "value": 27, **changes}

    def ingest(self, **changes):
        with self.captureOnCommitCallbacks(execute=True):
            reading = services.ingest_reading(self.payload(**changes))
        return reading

    def test_normal_and_threshold_values_have_no_alert_or_email(self):
        for metric, threshold in (("turbidity", 30), ("temperature", 25)):
            for value in (threshold-0.1, threshold):
                self.ingest(sensor_id=f"sensor-{metric}-{str(value).replace('.', '-')}", metric=metric, value=value)
        self.assertEqual(Reading.objects.count(), 4)
        self.assertFalse(Alert.objects.exists())
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_each_anomaly_snapshots_the_reading_and_current_threshold(self):
        for metric, threshold in (("turbidity", 30), ("temperature", 25)):
            reading = self.ingest(sensor_id=f"sensor-{metric}", metric=metric, value=threshold+1)
            alert = Alert.objects.get(reading=reading)
            for field in ("sensor_id", "metric", "timestamp", "value", "unit", "status"):
                self.assertEqual(getattr(alert, field), getattr(reading, field))
            self.assertEqual(alert.threshold, threshold)
            self.assertEqual(alert.status, Reading.Status.ANOMALY)
        self.assertEqual(len(mail.outbox), 4)

    def test_alert_uses_backend_status_without_its_own_comparison(self):
        with patch("monitoring.services.evaluate_status", return_value=Reading.Status.ANOMALY):
            reading = self.ingest(value=1)
        self.assertTrue(Alert.objects.filter(reading=reading).exists())

    def test_snapshot_survives_later_configuration_and_reading_changes(self):
        reading = self.ingest()
        Reading.objects.filter(pk=reading.pk).update(value=10, status=Reading.Status.OK)
        with override_settings(ANOMALY_THRESHOLDS={"temperature": 100}):
            self.client.force_login(self.anna)
            alert = self.client.get(reverse("messages-api")).json()["results"][0]["alert"]
        self.assertEqual((alert["value"], alert["threshold"], alert["status"]), (27, 25, "ANOMALY"))

    def test_only_active_users_with_valid_email_get_messages_and_email(self):
        reading = self.ingest()
        self.assertEqual(set(Notification.objects.filter(alert__reading=reading).values_list("user_id", flat=True)), {self.anna.pk, self.erik.pk})
        self.assertEqual({tuple(m.to) for m in mail.outbox}, {("anna@example.test",), ("erik@example.test",)})

    def test_alert_is_saved_when_no_recipients_exist(self):
        User.objects.update(is_active=False)
        reading = self.ingest()
        self.assertTrue(Alert.objects.filter(reading=reading).exists())
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_email_explains_sensor_value_threshold_and_protected_link(self):
        self.ingest()
        for message in mail.outbox:
            for expected in ("oak-temperature", "temperature", "27", "25", "°C", "ANOMALY", "https://monitor.example.test/messages/", "inte en myndighetsbedömning"):
                self.assertIn(expected, message.body)
            self.assertEqual(message.subject, "Datavarning från Smart Environmental Monitoring")

    def test_http_and_mqtt_create_the_same_kind_of_alert(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("readings"), data=json.dumps(self.payload()), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        consumer = MqttIngestor("localhost", 1883, "beach/+/readings")
        payload = self.payload(sensor_id="oak-turbidity", metric="turbidity", value=31)
        with self.captureOnCommitCallbacks(execute=True):
            reading = consumer.handle_message("beach/oak-turbidity/readings", json.dumps(payload).encode())
        self.assertIsNotNone(reading)
        self.assertEqual(Alert.objects.count(), 2)
        self.assertEqual(Notification.objects.count(), 4)
        self.assertEqual(len(mail.outbox), 4)

    def test_invalid_measurement_creates_no_reading_alert_or_email(self):
        with self.assertRaises(ValidationError):
            self.ingest(value=51)
        self.assertFalse(Reading.objects.exists())
        self.assertFalse(Alert.objects.exists())
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_duplicate_ingestion_and_repeated_delivery_do_not_duplicate_email(self):
        reading = self.ingest()
        with self.assertRaises(ValidationError):
            self.ingest()
        with self.captureOnCommitCallbacks(execute=True):
            create_alert(reading, 25)
        deliver_alert(Alert.objects.get().pk)
        for notification in Notification.objects.all():
            deliver_notification(notification.pk)
        self.assertEqual(Alert.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_http_and_mqtt_duplicate_payloads_cannot_send_again(self):
        self.ingest()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("readings"), data=json.dumps(self.payload()), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        consumer = MqttIngestor("localhost", 1883, "beach/+/readings")
        with self.assertLogs("monitoring.mqtt_consumer", level="ERROR"):
            self.assertIsNone(consumer.handle_message("beach/oak-temperature/readings", json.dumps(self.payload()).encode()))
        self.assertEqual(len(mail.outbox), 2)

    def test_database_enforces_one_alert_per_reading_and_message_per_user(self):
        self.ingest()
        alert = Alert.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Alert.objects.create(reading=alert.reading, **{field: getattr(alert, field) for field in (
                "sensor_id", "metric", "timestamp", "value", "unit", "threshold", "status",
            )})
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notification.objects.create(alert=alert, user=self.anna)

    def test_delivery_waits_until_commit_and_records_acceptance(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            services.ingest_reading(self.payload())
            self.assertEqual(mail.outbox, [])
            self.assertEqual(set(Notification.objects.values_list("delivery_status", flat=True)), {"pending"})
        self.assertEqual(len(callbacks), 1)
        for message in Notification.objects.all():
            self.assertEqual(message.delivery_status, "sent")
            self.assertIsNotNone(message.email_sent_at)
            self.assertEqual(message.delivery_error, "")

    def test_rollback_does_not_leave_alerts_messages_or_send_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError), transaction.atomic():
                services.ingest_reading(self.payload())
                raise RuntimeError("cancel transaction")
        self.assertFalse(Reading.objects.exists())
        self.assertFalse(Alert.objects.exists())
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_smtp_failure_preserves_data_and_records_only_safe_error(self):
        sensitive = "private-smtp-detail recipient@example.test password-token"
        with patch("monitoring.emails.EmailMessage.send", side_effect=SMTPException(sensitive)), self.assertLogs("monitoring", level="ERROR") as logs:
            reading = self.ingest()
        self.assertTrue(Reading.objects.filter(pk=reading.pk).exists())
        self.assertEqual(Alert.objects.count(), 1)
        for message in Notification.objects.all():
            self.assertEqual(message.delivery_status, "failed")
            self.assertTrue(message.delivery_error)
            self.assertIsNone(message.email_sent_at)
            self.assertNotIn(sensitive, message.delivery_error)
        self.assertNotIn(sensitive, "\n".join(logs.output))

    def test_one_failed_recipient_does_not_block_the_next(self):
        original_send = mail.EmailMessage.send
        def selective_send(message, *args, **kwargs):
            if message.to == [self.anna.email]:
                raise SMTPException("provider failure")
            return original_send(message, *args, **kwargs)
        with patch("monitoring.emails.EmailMessage.send", selective_send), self.assertLogs("monitoring.emails", level="ERROR"):
            self.ingest()
        self.assertEqual(Notification.objects.get(user=self.anna).delivery_status, "failed")
        self.assertEqual(Notification.objects.get(user=self.erik).delivery_status, "sent")
        self.assertEqual(len(mail.outbox), 1)

    def test_http_still_returns_created_when_smtp_fails(self):
        with patch("monitoring.emails.EmailMessage.send", side_effect=SMTPException("provider failure")), self.assertLogs("monitoring.emails", level="ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("readings"), data=json.dumps(self.payload()), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Reading.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(delivery_status="failed").count(), 2)

    def test_mqtt_still_accepts_reading_when_smtp_fails(self):
        consumer = MqttIngestor("localhost", 1883, "beach/+/readings")
        with patch("monitoring.emails.EmailMessage.send", side_effect=SMTPException("provider failure")), self.assertLogs("monitoring.emails", level="ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                reading = consumer.handle_message("beach/oak-temperature/readings", json.dumps(self.payload()).encode())
        self.assertIsNotNone(reading)
        self.assertEqual(Notification.objects.filter(delivery_status="failed").count(), 2)

    def test_alert_save_failure_rolls_back_the_whole_measurement_transaction(self):
        with patch("monitoring.notifications.Alert.objects.get_or_create", side_effect=IntegrityError("unavailable")):
            with self.assertRaises(IntegrityError), self.captureOnCommitCallbacks(execute=True):
                services.ingest_reading(self.payload())
        self.assertFalse(Reading.objects.exists())
        self.assertFalse(Notification.objects.exists())
        self.assertEqual(mail.outbox, [])

    @override_settings(PLATFORM_BASE_URL="invalid")
    def test_configuration_failure_is_saved_without_losing_the_message(self):
        with self.assertLogs("monitoring.notifications", level="WARNING"):
            self.ingest()
        self.assertEqual(Reading.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(delivery_status="failed").count(), 2)
        self.assertEqual(mail.outbox, [])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.test", EMAIL_PORT=587, EMAIL_USE_TLS=True, EMAIL_USE_SSL=False,
        EMAIL_HOST_USER="test-user", EMAIL_HOST_PASSWORD="test-only-password", EMAIL_TIMEOUT=10,
    )
    def test_alert_uses_shared_smtp_starttls_and_authentication(self):
        with patch("django.core.mail.backends.smtp.smtplib.SMTP", autospec=True) as smtp:
            self.ingest()
        self.assertEqual(smtp.return_value.starttls.call_count, 2)
        self.assertEqual(smtp.return_value.login.call_count, 2)
        smtp.return_value.login.assert_called_with("test-user", "test-only-password")
        self.assertEqual(smtp.return_value.sendmail.call_count, 2)
        self.assertEqual(Notification.objects.filter(delivery_status="sent").count(), 2)

    def test_no_send_if_recipient_becomes_inactive_before_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            services.ingest_reading(self.payload())
            User.objects.filter(pk=self.anna.pk).update(is_active=False)
        self.assertEqual(Notification.objects.get(user=self.anna).delivery_status, "failed")
        self.assertEqual([m.to for m in mail.outbox], [[self.erik.email]])

    def test_page_and_api_are_protected_and_show_only_current_users_messages(self):
        self.ingest()
        self.assertRedirects(self.client.get(reverse("message-list")), reverse("login") + "?next=/messages/", fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("messages-api")).status_code, 403)
        self.client.force_login(self.anna)
        own = Notification.objects.get(user=self.anna)
        other = Notification.objects.get(user=self.erik)
        response = self.client.get(reverse("messages-api"), {"user_id": self.erik.pk})
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], own.pk)
        self.assertNotIn(other.pk, [m["id"] for m in data["results"]])
        self.assertNotIn(self.erik.email, response.content.decode())
        self.assertContains(self.client.get(reverse("message-list")), "oak-temperature")
        self.assertContains(self.client.get(reverse("dashboard")), reverse("message-list"))

    def test_empty_state_and_invalid_pages(self):
        self.client.force_login(self.anna)
        self.assertContains(self.client.get(reverse("message-list")), "Du har inga sparade meddelanden")
        self.assertEqual(self.client.get(reverse("messages-api")).json()["results"], [])
        for page in ("0", "-1", "abc", "2", "1.5"):
            self.assertEqual(self.client.get(reverse("messages-api"), {"page": page}).status_code, 400)

    def test_pagination_limits_results_and_does_not_leak_other_users(self):
        self.ingest()
        alert = Alert.objects.get()
        Notification.objects.filter(user=self.anna).delete()
        alerts = []
        for index in range(21):
            reading = Reading.objects.create(sensor_id=f"sensor-{index}", timestamp=alert.timestamp, value=31, status="ANOMALY")
            alerts.append(Alert.objects.create(reading=reading, sensor_id=reading.sensor_id, metric="turbidity", timestamp=reading.timestamp, value=31, unit="NTU", threshold=30, status="ANOMALY"))
        Notification.objects.bulk_create([Notification(alert=a, user=self.anna) for a in alerts])
        self.client.force_login(self.anna)
        data = self.client.get(reverse("messages-api")).json()
        self.assertEqual((data["count"], data["pages"], len(data["results"])), (21, 2, 20))
        second = self.client.get(reverse("messages-api"), {"page": 2}).json()
        self.assertEqual(len(second["results"]), 1)
        self.assertContains(self.client.get(reverse("message-list")), 'href="?page=2"')

    def test_message_api_is_read_only_and_inactive_users_are_denied(self):
        self.client.force_login(self.anna)
        self.assertEqual(self.client.post(reverse("messages-api"), {}).status_code, 405)
        User.objects.filter(pk=self.anna.pk).update(is_active=False)
        self.assertEqual(self.client.get(reverse("messages-api")).status_code, 403)
