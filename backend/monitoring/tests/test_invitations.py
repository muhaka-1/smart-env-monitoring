import re
from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import ANY, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from monitoring.invitations import InvitationTokens, send_invitation
from monitoring.models import AccountInvitation

User = get_user_model()
PASSWORD = "Strand-Konto-2026!"


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PLATFORM_BASE_URL="https://platform.example.test",
)
class InvitationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.test", PASSWORD)

    def create_invited_user(self):
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("admin:auth_user_add"), {
                "username": "invited", "email": "invited@example.test", "_save": "Spara",
                # Servern måste ignorera försök att kringgå inbjudan.
                "is_active": "on", "is_superuser": "on", "password1": PASSWORD,
            })
        self.assertEqual(response.status_code, 302)
        self.client.logout()
        return User.objects.get(username="invited")

    def link(self):
        return re.search(r"https://platform.example.test(/accounts/invite/[^\s]+/)", mail.outbox[-1].body).group(1)

    def activate(self, link, client=None, password=PASSWORD, password2=None):
        client = client or self.client
        response = client.get(link)
        self.assertEqual(response.status_code, 302)
        return client.post(response["Location"], {"new_password1": password, "new_password2": password2 or password})

    def test_admin_creates_inactive_passwordless_account_and_sends_invitation(self):
        user = self.create_invited_user()
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertFalse(self.client.login(username=user.username, password=PASSWORD))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])
        self.assertIn("tre dagar", mail.outbox[0].body)
        self.assertIn(f"Ditt användarnamn är: {user.username}", mail.outbox[0].body)
        raw_token = self.link().strip("/").split("/")[-1]
        self.assertNotEqual(AccountInvitation.objects.get(user=user).token_digest, raw_token)

    def test_only_authorized_admin_can_create_accounts(self):
        url = reverse("admin:auth_user_add")
        self.assertEqual(self.client.post(url, {"username": "intruder"}).status_code, 302)
        for staff in (False, True):
            user = User.objects.create_user(f"ordinary-{staff}", password=PASSWORD, is_staff=staff)
            self.client.force_login(user)
            self.assertIn(self.client.post(url, {"username": "intruder"}).status_code, (302, 403))
        self.assertFalse(User.objects.filter(username="intruder").exists())

    def test_email_is_required_valid_and_not_already_used(self):
        self.client.force_login(self.admin)
        for email in ("", "bad", "ADMIN@EXAMPLE.TEST"):
            with self.subTest(email=email):
                response = self.client.post(reverse("admin:auth_user_add"), {"username": "new", "email": email})
                self.assertEqual(response.status_code, 200)
                self.assertIn("email", response.context["adminform"].form.errors)
        self.assertFalse(User.objects.filter(username="new").exists())

    def test_valid_link_activates_account_and_allows_login_without_automatic_session(self):
        user = self.create_invited_user()
        self.assertRedirects(self.activate(self.link()), reverse("invitation_complete"))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(self.client.login(username=user.username, password=PASSWORD))

    def test_used_link_and_already_open_form_cannot_change_password_again(self):
        user = self.create_invited_user()
        link = self.link()
        other = Client()
        form_url = other.get(link)["Location"]
        self.activate(link)
        self.assertContains(self.client.get(link), "har redan använts")
        self.assertContains(other.post(form_url, {"new_password1": "Other-Password-2026!", "new_password2": "Other-Password-2026!"}), "har redan använts")
        user.refresh_from_db()
        self.assertTrue(user.check_password(PASSWORD))

    def test_expiry_is_72_hours_independent_of_password_reset_timeout(self):
        user = self.create_invited_user()
        invitation = AccountInvitation.objects.get(user=user)
        link = self.link()
        with override_settings(PASSWORD_RESET_TIMEOUT=1):
            for elapsed, valid in ((timedelta(hours=71, minutes=59), True), (timedelta(hours=72), False), (timedelta(hours=73), False)):
                with self.subTest(elapsed=elapsed), patch("monitoring.invitations.timezone.now", return_value=invitation.issued_at + elapsed):
                    self.assertEqual(self.client.get(link).status_code, 302 if valid else 200)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_expired_open_form_is_rejected_at_submission(self):
        user = self.create_invited_user()
        form_url = self.client.get(self.link())["Location"]
        issued = AccountInvitation.objects.get(user=user).issued_at
        with patch("monitoring.invitations.timezone.now", return_value=issued + timedelta(hours=72)):
            self.assertContains(self.client.post(form_url, {"new_password1": PASSWORD, "new_password2": PASSWORD}), "har gått ut")
        user.refresh_from_db()
        self.assertFalse(user.has_usable_password())

    def test_resending_rotates_link_even_in_same_second_and_invalidates_open_form(self):
        user = self.create_invited_user()
        old_link = self.link()
        form_url = self.client.get(old_link)["Location"]
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("admin:auth_user_changelist"), {
                "action": "resend_invitations", "_selected_action": [user.pk],
            })
        self.assertEqual(response.status_code, 302)
        self.client.logout()
        self.assertEqual(len(mail.outbox), 2)
        new_link = self.link()
        self.assertNotEqual(old_link, new_link)
        self.assertContains(self.client.get(old_link), "Länken fungerar inte")
        self.assertContains(self.client.post(form_url, {"new_password1": PASSWORD, "new_password2": PASSWORD}), "Länken fungerar inte")
        self.assertRedirects(self.activate(new_link), reverse("invitation_complete"))

    def test_expired_invitation_can_be_resent(self):
        user = self.create_invited_user()
        AccountInvitation.objects.filter(user=user).update(issued_at=timezone.now() - timedelta(days=4))
        send_invitation(user.pk)
        self.assertRedirects(self.activate(self.link()), reverse("invitation_complete"))

    def test_invalid_token_or_unknown_user_is_rejected(self):
        self.create_invited_user()
        link = self.link()
        for bad in (link + "tampered/", link.rsplit("/", 2)[0] + "/invalid/", "/accounts/invite/not-a-user/invalid/"):
            self.assertIn(self.client.get(bad).status_code, (200, 404))
        self.assertContains(self.client.get(link.rsplit("/", 2)[0] + "/invalid/"), "Inbjudningslänken är ogiltig")

    def test_password_validation_keeps_account_inactive(self):
        user = self.create_invited_user()
        link = self.link()
        for first, second in (("short", "short"), (PASSWORD, "Different-2026!")):
            self.assertContains(self.activate(link, password=first, password2=second), "Aktivera konto")
            user.refresh_from_db()
            self.assertFalse(user.is_active)
            self.assertFalse(user.has_usable_password())

    def test_activation_and_admin_creation_require_csrf(self):
        user = self.create_invited_user()
        strict = Client(enforce_csrf_checks=True)
        form_url = strict.get(self.link())["Location"]
        self.assertEqual(strict.post(form_url, {"new_password1": PASSWORD, "new_password2": PASSWORD}).status_code, 403)
        strict.force_login(self.admin)
        self.assertEqual(strict.post(reverse("admin:auth_user_add"), {"username": "bad", "email": "bad@example.test"}).status_code, 403)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_email_change_invalidates_old_recipient_link(self):
        user = self.create_invited_user()
        old_link = self.link()
        user.email = "changed@example.test"
        user.save(update_fields=["email"])
        self.assertContains(self.client.get(old_link), "Länken fungerar inte")

    def test_pending_account_cannot_bypass_activation_via_admin_or_reset(self):
        user = self.create_invited_user()
        self.client.post(reverse("password_reset"), {"email": user.email})
        self.assertEqual(len(mail.outbox), 1)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("admin:auth_user_password_change", args=[user.pk])).status_code, 403)
        response = self.client.get(reverse("admin:auth_user_change", args=[user.pk]))
        self.assertNotContains(response, 'name="is_active"')

    def test_smtp_failure_keeps_account_inactive_and_reports_safe_error(self):
        with patch("monitoring.emails.EmailMessage.send", side_effect=SMTPException("sensitive-provider-detail")), self.assertLogs("monitoring.emails", level="ERROR") as logs, patch("monitoring.admin.InvitedUserAdmin.message_user") as report:
            user = self.create_invited_user()
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertNotIn("sensitive-provider-detail", "\n".join(logs.output))
        self.assertTrue(any("Inbjudan kunde inte skickas" in str(call) for call in report.call_args_list))

    def test_active_accounts_cannot_be_reinvited(self):
        with self.assertRaisesMessage(ValidationError, "Endast inaktiva"):
            send_invitation(self.admin.pk)

    @override_settings(PLATFORM_BASE_URL="invalid")
    def test_invalid_email_configuration_keeps_account_and_reports_safe_error(self):
        with patch("monitoring.admin.InvitedUserAdmin.message_user") as report:
            user = self.create_invited_user()
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(mail.outbox, [])
        self.assertTrue(any("Inbjudan kunde inte skickas" in str(call) for call in report.call_args_list))

    def test_failed_delivery_can_be_retried_with_admin_action(self):
        with patch("monitoring.emails.EmailMessage.send", return_value=0), self.assertLogs("monitoring.emails", level="ERROR"):
            user = self.create_invited_user()
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("admin:auth_user_changelist"), {
                "action": "resend_invitations", "_selected_action": [user.pk],
            })
        self.client.logout()
        self.assertEqual(len(mail.outbox), 1)
        self.assertRedirects(self.activate(self.link()), reverse("invitation_complete"))

    def test_token_claim_lost_to_another_submission_does_not_activate(self):
        user = self.create_invited_user()
        form_url = self.client.get(self.link())["Location"]
        with patch("django.db.models.query.QuerySet.update", return_value=0):
            self.assertContains(self.client.post(form_url, {"new_password1": PASSWORD, "new_password2": PASSWORD}), "Länken fungerar inte")
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())

    def test_activation_rechecks_token_after_form_validation(self):
        user = self.create_invited_user()
        form_url = self.client.get(self.link())["Location"]
        with patch.object(InvitationTokens, "check_token", side_effect=[True, False]):
            self.assertContains(self.client.post(form_url, {"new_password1": PASSWORD, "new_password2": PASSWORD}), "Länken fungerar inte")
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())

    def test_password_save_failure_rolls_back_token_consumption(self):
        user = self.create_invited_user()
        link = self.link()
        form_url = self.client.get(link)["Location"]
        digest = AccountInvitation.objects.get(user=user).token_digest
        with patch.object(User, "save", side_effect=RuntimeError("database unavailable")), self.assertLogs("django.request", level="ERROR"):
            with self.assertRaises(RuntimeError):
                self.client.post(form_url, {"new_password1": PASSWORD, "new_password2": PASSWORD})
        self.assertEqual(AccountInvitation.objects.get(user=user).token_digest, digest)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_staff_without_change_permission_cannot_resend(self):
        user = self.create_invited_user()
        staff = User.objects.create_user("viewer", password=PASSWORD, is_staff=True)
        self.client.force_login(staff)
        response = self.client.post(reverse("admin:auth_user_changelist"), {
            "action": "resend_invitations", "_selected_action": [user.pk],
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.test", EMAIL_PORT=587,
        EMAIL_HOST_USER="smtp-user", EMAIL_HOST_PASSWORD="test-only-smtp-password",
        EMAIL_USE_TLS=True, EMAIL_USE_SSL=False, EMAIL_TIMEOUT=10,
        DEFAULT_FROM_EMAIL="sender@example.test",
    )
    def test_invitation_uses_configured_smtp_with_starttls_and_authentication(self):
        with patch("django.core.mail.backends.smtp.smtplib.SMTP", autospec=True) as smtp:
            user = self.create_invited_user()
        smtp.assert_called_once_with("smtp.example.test", 587, local_hostname=ANY, timeout=10)
        smtp.return_value.starttls.assert_called_once()
        smtp.return_value.login.assert_called_once_with("smtp-user", "test-only-smtp-password")
        args = smtp.return_value.sendmail.call_args.args
        self.assertEqual(args[:2], ("sender@example.test", [user.email]))
        self.assertIn(b"/accounts/invite/", args[2])
