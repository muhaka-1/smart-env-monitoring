from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from monitoring.invitations import invitation_status
from monitoring.models import AccountInvitation


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdminLocalizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(
            "locale-admin", is_staff=True, is_superuser=True,
        )
        cls.invitee = get_user_model().objects.create_user(
            "pending", email="pending@example.test", is_active=False,
        )

    def select_language(self, language):
        self.client.cookies["django_language"] = language

    def test_login_and_custom_admin_navigation_follow_language(self):
        for language, heading, account, platform in (
            ("sv", "Logga in som administratör", "Mitt konto", "Till plattformen"),
            ("en", "Sign in as administrator", "My account", "To the platform"),
            ("de", "Als Administrator anmelden", "Mein Konto", "Zur Plattform"),
        ):
            with self.subTest(language=language):
                self.client.logout()
                self.select_language(language)
                self.assertContains(self.client.get(reverse("admin:login")), heading)
                self.client.force_login(self.admin)
                response = self.client.get(reverse("admin:index"))
                self.assertContains(response, account)
                self.assertContains(response, platform)

    def test_import_preview_and_validation_are_translated_without_creating_accounts(self):
        self.client.force_login(self.admin)
        for language, title, invalid, confirm in (
            ("en", "Import accounts", "The email address is invalid.", "Confirm import of 1 accounts"),
            ("de", "Konten importieren", "Die E-Mail-Adresse ist ungültig.", "Import von 1 Konten bestätigen"),
        ):
            with self.subTest(language=language):
                self.select_language(language)
                upload = SimpleUploadedFile("accounts.csv", b"username,email\nnew,new@example.test\ninvalid,bad\n")
                response = self.client.post(reverse("admin:auth_user_import"), {"file": upload})
                self.assertContains(response, title)
                self.assertContains(response, invalid)
                self.assertContains(response, confirm)
                self.assertContains(response, 'name="preview_token"')
                self.assertFalse(get_user_model().objects.filter(username="new").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_import_file_errors_use_request_language(self):
        self.client.force_login(self.admin)
        for language, expected in (("en", "Choose a CSV file."), ("de", "Wähle eine CSV-Datei.")):
            with self.subTest(language=language):
                self.select_language(language)
                self.assertContains(self.client.post(reverse("admin:auth_user_import"), {}), expected)

    def test_invitation_status_uses_active_language_for_each_state(self):
        invitation = AccountInvitation.objects.create(
            user=self.invitee, token_digest="digest", issued_at=timezone.now(),
        )
        for language, failed, sent, expired, activated in (
            ("sv", "Ej skickad (leveransfel)", "Skickad, giltig till", "Utgången", "Aktiverad"),
            ("en", "Not sent (delivery failed)", "Sent, valid until", "Expired", "Activated"),
            ("de", "Nicht gesendet (Zustellfehler)", "Gesendet, gültig bis", "Abgelaufen", "Aktiviert"),
        ):
            with self.subTest(language=language), translation.override(language):
                self.invitee.is_active = False
                invitation.issued_at = timezone.now()
                invitation.sent_at = None
                self.assertEqual(str(invitation_status(self.invitee)), failed)
                invitation.sent_at = timezone.now()
                self.assertIn(sent, str(invitation_status(self.invitee)))
                invitation.issued_at -= timedelta(days=4)
                self.assertEqual(str(invitation_status(self.invitee)), expired)
                self.invitee.is_active = True
                self.assertEqual(str(invitation_status(self.invitee)), activated)
