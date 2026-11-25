from django.core.checks import run_checks
from django.test import SimpleTestCase, override_settings


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
    EMAIL_HOST="smtp.example.test", EMAIL_PORT=587,
    EMAIL_HOST_USER="test-user", EMAIL_HOST_PASSWORD="test-only-password",
    EMAIL_USE_TLS=True, EMAIL_USE_SSL=False, EMAIL_TIMEOUT=10,
    DEFAULT_FROM_EMAIL="sender@example.test",
)
class SmtpCheckTests(SimpleTestCase):
    def check_email(self):
        return run_checks(tags=["email"])

    def test_starttls_and_implicit_tls_pass(self):
        self.assertEqual(self.check_email(), [])
        with override_settings(EMAIL_USE_TLS=False, EMAIL_USE_SSL=True, EMAIL_PORT=465):
            self.assertEqual(self.check_email(), [])

    def test_missing_fields_report_names_without_secrets(self):
        for field in ("EMAIL_HOST", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD"):
            with self.subTest(field=field), override_settings(**{field: ""}):
                errors = self.check_email()
                self.assertTrue(any(field in error.msg for error in errors))
                self.assertNotIn("test-only-password", str(errors))
                self.assertNotIn("test-user", str(errors))

    def test_unconfigured_local_defaults_fail(self):
        with override_settings(
            EMAIL_HOST="localhost", EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="",
            EMAIL_PORT=25, EMAIL_USE_TLS=False, DEFAULT_FROM_EMAIL="no-reply@example.com",
        ):
            ids = {error.id for error in self.check_email()}
        self.assertTrue({"monitoring.E001", "monitoring.E002", "monitoring.E003", "monitoring.E006"}.issubset(ids))

    def test_invalid_transport_sender_and_numeric_settings_fail(self):
        for values, expected in (
            ({"EMAIL_USE_SSL": True}, "monitoring.E003"),
            ({"EMAIL_USE_TLS": False}, "monitoring.E003"),
            ({"EMAIL_PORT": 0}, "monitoring.E004"),
            ({"EMAIL_PORT": 65536}, "monitoring.E004"),
            ({"EMAIL_TIMEOUT": 0}, "monitoring.E005"),
            ({"DEFAULT_FROM_EMAIL": "invalid"}, "monitoring.E006"),
        ):
            with self.subTest(values=values), override_settings(**values):
                self.assertIn(expected, {error.id for error in self.check_email()})

    def test_memory_backend_needs_no_smtp(self):
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="", EMAIL_USE_TLS=False,
        ):
            self.assertEqual(self.check_email(), [])
