from datetime import datetime, timezone
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from monitoring.emails import send_platform_email
from monitoring.models import Alert, Notification, Reading


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="monitor@example.test",
    PLATFORM_BASE_URL="https://monitor.example.test",
)
class AccountEmailPdfLanguageTests(TestCase):
    sensor_id = "language-beach-temperature"

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            "language-reader",
            "reader@example.test",
            "Test-Strand-2026!",
        )
        cls.timestamp = datetime(2026, 11, 10, 14, 30, tzinfo=timezone.utc)
        reading = Reading.objects.create(
            sensor_id=cls.sensor_id,
            metric=Reading.Metric.TEMPERATURE,
            timestamp=cls.timestamp,
            value=27.5,
            unit="°C",
            status=Reading.Status.ANOMALY,
        )
        alert = Alert.objects.create(
            reading=reading,
            sensor_id=cls.sensor_id,
            metric=Reading.Metric.TEMPERATURE,
            timestamp=cls.timestamp,
            value=27.5,
            unit="°C",
            threshold=25,
            status=Reading.Status.ANOMALY,
        )
        Notification.objects.create(user=cls.user, alert=alert)

    def select_language(self, language):
        self.client.post(
            reverse("set_language"),
            {"language": language, "next": reverse("dashboard")},
        )

    @staticmethod
    def pdf_text(response):
        return "\n".join(
            page.extract_text() or ""
            for page in PdfReader(BytesIO(response.content)).pages
        )

    def test_account_pages_follow_selected_english_and_german(self):
        self.select_language("en")
        login = self.client.get(reverse("login"))
        self.assertContains(login, "YOUR ACCOUNT")
        self.assertContains(login, "Username")
        self.assertContains(login, "Forgot password?")

        self.select_language("de")
        reset = self.client.get(reverse("password_reset"))
        complete = self.client.get(reverse("invitation_complete"))
        self.assertContains(reset, "Passwort vergessen")
        self.assertContains(reset, "Link zum Zurücksetzen senden")
        self.assertContains(complete, "Das Konto ist aktiviert")

    def test_invitation_email_can_be_rendered_in_english(self):
        send_platform_email(
            "invitee@example.test",
            "invitation",
            action_path="/accounts/invite/test/",
            context={"username": "invitee"},
            language="en",
        )

        message = mail.outbox[-1]
        self.assertEqual(message.subject, "Your invitation to Smart Environmental Monitoring")
        self.assertIn("Your username is: invitee", message.body)
        self.assertIn("Choose your password using this link:", message.body)
        self.assertIn("https://monitor.example.test/accounts/invite/test/", message.body)

    def test_data_alert_email_translates_labels_but_preserves_values(self):
        send_platform_email(
            "reader@example.test",
            "data_alert",
            action_path="/messages/",
            context={
                "sensor_id": self.sensor_id,
                "metric": "temperature",
                "timestamp": "2026-11-10T14:30:00Z",
                "value": 27.5,
                "unit": "°C",
                "threshold": 25,
                "status": "ANOMALY",
            },
            language="de",
        )

        message = mail.outbox[-1]
        self.assertEqual(message.subject, "Datenwarnung von Smart Environmental Monitoring")
        self.assertIn("Messgröße: Temperatur", message.body)
        self.assertIn("Status: Abweichung", message.body)
        self.assertIn("2026-11-10T14:30:00Z", message.body)
        self.assertIn("27,5 °C", message.body)

    def test_history_pdf_uses_english_and_preserves_reading_data(self):
        self.client.force_login(self.user)
        self.select_language("en")

        response = self.client.get(
            reverse("history-pdf"),
            {"sensor_id": self.sensor_id},
        )
        text = self.pdf_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Historical readings - Latest 200", text)
        self.assertIn("Metric: Temperature", text)
        self.assertIn(self.sensor_id, text)
        self.assertIn("2026-11-10 14:30:00", text)
        self.assertIn("27.5", text)

    def test_error_report_pdf_uses_german_and_preserves_alert_data(self):
        self.client.force_login(self.user)
        self.select_language("de")

        response = self.client.get(reverse("error-report-pdf"))
        text = self.pdf_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Fehlerbericht", text)
        self.assertIn("Messgröße", text)
        self.assertIn("Abweichung", text)
        self.assertIn(self.sensor_id, text)
        self.assertIn("2026-11-10 14:30:00", text)
        self.assertIn("27,5", text)
