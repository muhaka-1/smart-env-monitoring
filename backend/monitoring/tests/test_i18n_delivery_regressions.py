import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.translation import gettext, override

from monitoring import services
from monitoring.emails import EmailDeliveryError
from monitoring.models import Notification
from monitoring.mqtt_consumer import MqttIngestor


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DeliveryLanguageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("reader", "reader@example.test", "Review-language-2026!")

    def select_language(self, user, language):
        client = Client()
        client.force_login(user)
        response = client.post(reverse("set_language"), {"language": language, "next": "/"})
        self.assertEqual(response.status_code, 302)
        return client

    def ingest(self):
        with override("sv"), self.captureOnCommitCallbacks(execute=True):
            services.ingest_reading({"sensor_id": "rainbow-beach-turbidity", "metric": "turbidity",
                                     "timestamp": "2026-11-15T10:00:00Z", "value": 38.27})

    def test_background_mqtt_uses_each_recipients_saved_language(self):
        other = get_user_model().objects.create_user("other", "other@example.test", "Review-language-2026!")
        self.select_language(self.user, "en")
        self.select_language(other, "de")
        with override("sv"), self.captureOnCommitCallbacks(execute=True):
            reading = MqttIngestor("localhost", 1883, "beach/+/readings").handle_message(
                "beach/rainbow/readings", json.dumps({"sensor_id": "rainbow-beach-turbidity",
                "metric": "turbidity", "timestamp": "2026-11-15T10:00:00Z", "value": 38.27}).encode())
        self.assertIsNotNone(reading)
        messages = {m.to[0]: m for m in mail.outbox}
        for user, language in [(self.user, "en"), (other, "de")]:
            with override(language):
                expected = gettext("Datavarning från Smart Environmental Monitoring")
            self.assertEqual(messages[user.email].subject, expected)
        self.assertNotEqual(messages[self.user.email].subject, messages[other.email].subject)

    def test_login_saves_anonymous_language_choice(self):
        client = Client()
        client.post(reverse("set_language"), {"language": "de", "next": "/"})
        response = client.post(reverse("login"), {"username": self.user.username, "password": "Review-language-2026!"})
        self.assertEqual(response.status_code, 302)
        self.ingest()
        self.assertEqual(mail.outbox[-1].subject, "Datenwarnung von Smart Environmental Monitoring")

    def test_new_browser_login_does_not_overwrite_saved_preference(self):
        self.select_language(self.user, "de")
        client = Client()
        client.post(reverse("login"), {"username": self.user.username, "password": "Review-language-2026!"})
        self.ingest()
        self.assertEqual(mail.outbox[-1].subject, "Datenwarnung von Smart Environmental Monitoring")

    def test_invalid_selection_and_get_do_not_change_preference(self):
        client = self.select_language(self.user, "de")
        client.post(reverse("set_language"), {"language": "unsupported", "next": "/"})
        client.get(reverse("set_language"), {"language": "en", "next": "/"})
        self.ingest()
        self.assertEqual(mail.outbox[-1].subject, "Datenwarnung von Smart Environmental Monitoring")

    def test_language_selection_changes_only_the_authenticated_account(self):
        from monitoring.models import UserLanguagePreference
        other = get_user_model().objects.create_user("other", "other@example.test")
        self.select_language(other, "de")
        client = self.select_language(self.user, "en")
        client.post(reverse("set_language"), {"language": "sv", "next": "/", "user_id": other.pk})
        self.assertEqual(UserLanguagePreference.objects.get(user=self.user).language, "sv")
        self.assertEqual(UserLanguagePreference.objects.get(user=other).language, "de")

    def test_language_selection_requires_csrf(self):
        from monitoring.models import UserLanguagePreference
        self.select_language(self.user, "de")
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(reverse("set_language"), {"language": "en", "next": "/"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(UserLanguagePreference.objects.get(user=self.user).language, "de")

    def test_failed_delivery_is_translated_in_html_and_api_without_rewriting_data(self):
        self.user.email = ""
        self.user.save(update_fields=["email"])
        self.ingest()
        notification = Notification.objects.get(user=self.user)
        stored = notification.delivery_error
        for language, expected in [("en", "Email could not be sent:"), ("de", "E-Mail konnte nicht gesendet werden:")]:
            client = self.select_language(self.user, language)
            self.assertContains(client.get(reverse("message-list")), expected)
            self.assertNotContains(client.get(reverse("message-list")), stored)
            data = client.get(reverse("messages-api")).json()["results"][0]
            self.assertTrue(data["delivery_error"].startswith(expected))
            notification.refresh_from_db()
            self.assertEqual(notification.delivery_error, stored)

    def test_legacy_delivery_error_is_translated_without_rewriting_data(self):
        self.ingest()
        notification = Notification.objects.get(user=self.user)
        legacy = "Mottagaren är inte längre aktiv eller saknar giltig e-postadress."
        notification.delivery_error = legacy
        notification.save(update_fields=["delivery_error"])
        client = self.select_language(self.user, "en")
        self.assertContains(client.get(reverse("message-list")), "Email could not be sent:")
        notification.refresh_from_db()
        self.assertEqual(notification.delivery_error, legacy)

    def test_smtp_error_is_translated_without_dropping_internal_message(self):
        with patch("monitoring.notifications.send_platform_email", side_effect=EmailDeliveryError("unavailable")):
            self.ingest()
        notification = Notification.objects.get(user=self.user)
        self.assertEqual(notification.delivery_status, "failed")
        client = self.select_language(self.user, "en")
        self.assertContains(client.get(reverse("message-list")), "The email attempt failed.")


class PdfValidationLanguageTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("pdf-reader")
        self.client.force_login(user)

    def test_pdf_validation_errors_follow_language(self):
        cases = [({"sensor_id": "invalid!"}, "Choose a valid sensor ID.", "Wähle eine gültige Sensor-ID."),
                 ({"sensor_id": "rainbow-beach-turbidity", "start": "invalid"},
                  "The start or end time has an invalid format.", "Die Start- oder Endzeit hat ein ungültiges Format."),
                 ({"sensor_id": "rainbow-beach-turbidity", "start": "2026-11-15T10:00:00Z", "end": "2026-11-14T10:00:00Z"},
                  "The start time must be before the end time.", "Die Startzeit muss vor der Endzeit liegen.")]
        for language, position in [("en", 1), ("de", 2)]:
            self.client.post(reverse("set_language"), {"language": language, "next": "/"})
            for case in cases:
                with self.subTest(language=language, params=case[0]):
                    response = self.client.get(reverse("history-pdf"), case[0])
                    self.assertEqual(response.status_code, 400)
                    self.assertContains(response, case[position], status_code=400)
