import io
import os
import runpy
import traceback
from pathlib import Path
from smtplib import SMTPException
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import SimpleTestCase, override_settings

from monitoring.emails import EmailDeliveryError, send_platform_email

SETTINGS = Path(__file__).resolve().parents[2] / "config" / "settings.py"


class EmailConfigurationTests(SimpleTestCase):
    def test_local_defaults_do_not_require_smtp_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            config = runpy.run_path(str(SETTINGS))
        self.assertEqual(config["EMAIL_BACKEND"], "django.core.mail.backends.console.EmailBackend")
        self.assertEqual(config["EMAIL_HOST_USER"], "")
        self.assertEqual(config["EMAIL_HOST_PASSWORD"], "")
        self.assertEqual(config["EMAIL_TIMEOUT"], 10)
        self.assertEqual(config["DEFAULT_FROM_EMAIL"], "no-reply@example.com")
        self.assertEqual(config["PLATFORM_BASE_URL"], "http://127.0.0.1:8000")
        self.assertFalse(config["EMAIL_USE_TLS"])
        self.assertFalse(config["EMAIL_USE_SSL"])

    def test_email_settings_are_read_from_environment(self):
        env = {
            "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "EMAIL_HOST": "smtp.example.test", "EMAIL_PORT": "587",
            "EMAIL_HOST_USER": "test-user", "EMAIL_HOST_PASSWORD": "test-only-password",
            "EMAIL_TIMEOUT": "15", "DEFAULT_FROM_EMAIL": "monitor@example.test",
            "PLATFORM_BASE_URL": "https://monitor.example.test/app",
        }
        for tls, ssl in (("1", "0"), ("0", "1")):
            with self.subTest(tls=tls, ssl=ssl):
                with patch.dict(os.environ, {**env, "EMAIL_USE_TLS": tls, "EMAIL_USE_SSL": ssl}, clear=True):
                    config = runpy.run_path(str(SETTINGS))
                for key, value in env.items():
                    self.assertEqual(config[key], int(value) if key in ("EMAIL_PORT", "EMAIL_TIMEOUT") else value)
                self.assertEqual(config["EMAIL_USE_TLS"], tls == "1")
                self.assertEqual(config["EMAIL_USE_SSL"], ssl == "1")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="monitor@example.test",
    PLATFORM_BASE_URL="https://monitor.example.test",
)
class PlatformEmailTests(SimpleTestCase):
    def test_invitation_recipient_subject_content_and_link(self):
        send_platform_email("user@example.test", "invitation", action_path="/activate/test-token/")
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["user@example.test"])
        self.assertEqual(message.from_email, "monitor@example.test")
        self.assertEqual(message.subject, "Din inbjudan till Smart Environmental Monitoring")
        self.assertEqual(message.content_subtype, "plain")
        self.assertIn("Välj ditt lösenord", message.body)
        self.assertIn("högst tre dagar", message.body)
        self.assertIn("https://monitor.example.test/activate/test-token/", message.body)

    @override_settings(PLATFORM_BASE_URL="https://monitor.example.test/app/")
    def test_password_reset_uses_base_prefix_and_preserves_query(self):
        send_platform_email(
            "reset@example.test", "password_reset", action_path="/reset/test-token/?a=1&b=2",
            context={"action_url": "https://untrusted.example.test/"},
        )
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["reset@example.test"])
        self.assertEqual(message.subject, "Återställ ditt lösenord")
        self.assertIn("Välj ett nytt lösenord", message.body)
        self.assertIn("Om du inte har begärt återställningen", message.body)
        self.assertIn("https://monitor.example.test/app/reset/test-token/?a=1&b=2", message.body)
        self.assertNotIn("&amp;", message.body)
        self.assertNotIn("untrusted.example.test", message.body)

    def test_data_alert_recipient_subject_fields_and_link(self):
        fields = {
            "sensor_id": "oak-temperature", "metric": "temperature",
            "timestamp": "2026-11-03T12:00:00Z", "value": 27, "unit": "°C",
            "threshold": 25, "status": "ANOMALY",
        }
        send_platform_email("alert@example.test", "data_alert", action_path="/messages/7/", context=fields)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["alert@example.test"])
        self.assertEqual(message.subject, "Datavarning från Smart Environmental Monitoring")
        for text in (
            "Sensor: oak-temperature", "Mätstorhet: temperature", "Tid: 2026-11-03T12:00:00Z",
            "Värde: 27 °C", "Gränsvärde: 25 °C", "Status: ANOMALY",
            "https://monitor.example.test/messages/7/", "inte en myndighetsbedömning",
        ):
            self.assertIn(text, message.body)

    def test_unknown_email_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            send_platform_email("user@example.test", "unknown", action_path="/")
        self.assertEqual(mail.outbox, [])

    def test_incomplete_alert_context_is_rejected(self):
        with self.assertRaises(ValueError):
            send_platform_email("user@example.test", "data_alert", action_path="/", context={"sensor_id": "a"})
        self.assertEqual(mail.outbox, [])

    def test_invalid_recipient_is_rejected_without_delivery(self):
        for recipient in ("", "invalid", "user@example.test\nBcc: other@example.test"):
            with self.subTest(recipient=recipient), self.assertRaises(ValidationError):
                send_platform_email(recipient, "invitation", action_path="/")
        self.assertEqual(mail.outbox, [])

    def test_action_path_cannot_point_outside_platform(self):
        for path in ("https://other.example.test/", "//other.example.test/", "/\\other.example.test/", "reset/token", "/reset/\n", ""):
            with self.subTest(path=path), self.assertRaises(ValueError):
                send_platform_email("user@example.test", "invitation", action_path=path)
        self.assertEqual(mail.outbox, [])

    def test_invalid_base_url_is_rejected(self):
        for base in (
            "", "ftp://monitor.example.test", "https://user:password@monitor.example.test",
            "https://monitor.example.test/?token=test-token", "https://monitor.example.test/#fragment",
        ):
            with self.subTest(base=base), override_settings(PLATFORM_BASE_URL=base):
                with self.assertRaises(ImproperlyConfigured):
                    send_platform_email("user@example.test", "invitation", action_path="/")
        self.assertEqual(mail.outbox, [])

    def test_delivery_errors_are_reported_without_sensitive_logging(self):
        sensitive = "user@example.test test-token test-only-password private-body"
        recipient, token, _, _ = sensitive.split()
        action_path = f"/activate/{token}/"
        for failure in (SMTPException(sensitive), OSError(sensitive)):
            with self.subTest(failure=type(failure).__name__):
                with patch("monitoring.emails.EmailMessage.send", side_effect=failure):
                    with self.assertLogs("monitoring.emails", level="ERROR") as logged:
                        try:
                            send_platform_email(recipient, "invitation", action_path=action_path)
                        except EmailDeliveryError:
                            rendered_error = traceback.format_exc()
                        else:
                            self.fail("Leveransfelet måste rapporteras till anroparen.")
                self.assertEqual(logged.output, ["ERROR:monitoring.emails:E-postleverans misslyckades (typ=invitation)."])
                for secret in sensitive.split():
                    self.assertNotIn(secret, rendered_error)
                self.assertIsNone(logged.records[0].exc_info)

    def test_zero_sent_messages_is_a_delivery_failure(self):
        with patch("monitoring.emails.EmailMessage.send", return_value=0):
            with self.assertLogs("monitoring.emails", level="ERROR"):
                with self.assertRaises(EmailDeliveryError):
                    send_platform_email("user@example.test", "invitation", action_path="/")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")
    def test_console_backend_displays_message_locally(self):
        output = io.StringIO()
        with patch("sys.stdout", output):
            send_platform_email("user@example.test", "invitation", action_path="/activate/test-token/")
        self.assertIn("To: user@example.test", output.getvalue())
        self.assertIn("https://monitor.example.test/activate/test-token/", output.getvalue())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.test", EMAIL_PORT=587, EMAIL_USE_TLS=True, EMAIL_USE_SSL=False,
        EMAIL_HOST_USER="test-user", EMAIL_HOST_PASSWORD="test-only-password", EMAIL_TIMEOUT=15,
    )
    def test_smtp_configuration_is_used_without_network_access(self):
        with patch("django.core.mail.backends.smtp.smtplib.SMTP", autospec=True) as smtp:
            send_platform_email("user@example.test", "invitation", action_path="/")
        smtp.assert_called_once()
        self.assertEqual(smtp.call_args.args, ("smtp.example.test", 587))
        self.assertEqual(smtp.call_args.kwargs["timeout"], 15)
        smtp.return_value.starttls.assert_called_once()
        smtp.return_value.login.assert_called_once_with("test-user", "test-only-password")
        args = smtp.return_value.sendmail.call_args.args
        self.assertEqual(args[:2], ("monitor@example.test", ["user@example.test"]))
