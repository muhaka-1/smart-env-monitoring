import itertools
import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from monitoring.emails import EmailDeliveryError
from monitoring.invitations import invitation_status, send_invitation
from monitoring.models import AccountInvitation

User = get_user_model()
PASSWORD = "Strand-Konto-2026!"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", PLATFORM_BASE_URL="https://platform.example.test")
class InvitationStatusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.test", PASSWORD)

    def invitee(self, name="anna"):
        user = User(username=name, email=f"{name}@example.test", is_active=False)
        user.set_unusable_password()
        user.save()
        return user

    def link(self):
        return re.search(r"https://platform.example.test(/accounts/invite/[^\s]+/)", mail.outbox[-1].body).group(1)

    def status(self, user):
        return invitation_status(User.objects.select_related("accountinvitation").get(pk=user.pk))

    def test_no_invitation(self):
        self.assertEqual(self.status(self.invitee()), "Ingen inbjudan")

    def test_confirmed_send_records_sent_at_and_status(self):
        user = self.invitee()
        send_invitation(user.pk)
        invitation = AccountInvitation.objects.get(user=user)
        self.assertIsNotNone(invitation.sent_at)
        self.assertEqual(invitation.sent_at, invitation.issued_at)
        self.assertTrue(self.status(user).startswith("Skickad, giltig till "))

    def test_validity_counts_from_confirmed_send(self):
        user = self.invitee()
        start = timezone.now()
        confirmed = start + timedelta(hours=1)
        # Första anropet (skapa inbjudan) får start, alla följande bekräftelsetiden.
        times = itertools.chain([start], itertools.repeat(confirmed))
        with patch("monitoring.invitations.timezone.now", side_effect=lambda: next(times)):
            send_invitation(user.pk)
        invitation = AccountInvitation.objects.get(user=user)
        self.assertEqual(invitation.sent_at, confirmed)
        self.assertEqual(invitation.issued_at, confirmed)
        link = self.link()
        for elapsed, ok in ((timedelta(hours=71, minutes=59), True), (timedelta(hours=72), False)):
            with self.subTest(elapsed=elapsed), patch("monitoring.invitations.timezone.now", return_value=confirmed + elapsed):
                self.assertEqual(self.client.get(link).status_code, 302 if ok else 200)

    def test_delivery_failure_marks_not_sent_and_makes_link_unusable(self):
        user = self.invitee()
        with patch("monitoring.invitations.send_platform_email", side_effect=EmailDeliveryError("fel")):
            with self.assertRaises(EmailDeliveryError):
                send_invitation(user.pk)
        invitation = AccountInvitation.objects.get(user=user)
        self.assertIsNone(invitation.sent_at)
        self.assertEqual(invitation.token_digest, "")
        self.assertEqual(self.status(user), "Ej skickad (leveransfel)")

    def test_resend_after_failure_gives_sent_status(self):
        user = self.invitee()
        with patch("monitoring.invitations.send_platform_email", side_effect=EmailDeliveryError("fel")):
            with self.assertRaises(EmailDeliveryError):
                send_invitation(user.pk)
        send_invitation(user.pk)
        self.assertTrue(self.status(user).startswith("Skickad"))
        self.assertEqual(len(mail.outbox), 1)

    def test_failed_resend_invalidates_previous_link(self):
        user = self.invitee()
        send_invitation(user.pk)
        old = self.link()
        with patch("monitoring.invitations.send_platform_email", side_effect=EmailDeliveryError("fel")):
            with self.assertRaises(EmailDeliveryError):
                send_invitation(user.pk)
        self.assertEqual(self.status(user), "Ej skickad (leveransfel)")
        self.assertEqual(self.client.get(old).status_code, 200)  # ogiltig länk visar felsida

    def test_expired_and_activated(self):
        user = self.invitee()
        send_invitation(user.pk)
        AccountInvitation.objects.filter(user=user).update(issued_at=timezone.now() - timedelta(days=4))
        self.assertEqual(self.status(user), "Utgången")
        send_invitation(user.pk)
        self.client.get(self.link())  # token flyttas till sessionen
        form_url = self.client.get(self.link())["Location"]
        self.client.post(form_url, {"new_password1": PASSWORD, "new_password2": PASSWORD})
        self.assertEqual(self.status(user), "Aktiverad")

    def test_regular_active_account_shows_dash(self):
        self.assertEqual(self.status(self.admin), "–")

    def test_admin_list_shows_status_column(self):
        sent, failed, plain = self.invitee("sand"), self.invitee("miss"), self.invitee("ingen")
        send_invitation(sent.pk)
        with patch("monitoring.invitations.send_platform_email", side_effect=EmailDeliveryError("fel")):
            with self.assertRaises(EmailDeliveryError):
                send_invitation(failed.pk)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertContains(response, "Inbjudan")
        self.assertContains(response, "Skickad, giltig till")
        self.assertContains(response, "Ej skickad (leveransfel)")
        self.assertContains(response, "Ingen inbjudan")
