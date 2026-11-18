"""Tester för glömt lösenord och lösenordsbyte (issue #63)."""
import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.template.loader import render_to_string
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()
OLD_PASSWORD = "gammalt-losen-123"
NEW_PASSWORD = "Nytt-Strandlosen-2026"
BASE_URL = "https://monitor.example.test"
LINK_RE = re.compile(re.escape(BASE_URL) + r"(/accounts/reset/[^/\s]+/[^/\s]+/)")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PLATFORM_BASE_URL=BASE_URL,
    PASSWORD_RESET_TIMEOUT=3600,
)
class PasswordResetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("anna", "anna@example.test", OLD_PASSWORD)
        User.objects.create_user("inaktiv", "inaktiv@example.test", OLD_PASSWORD, is_active=False)
        utan = User.objects.create_user("utan", "utan@example.test")
        utan.set_unusable_password()
        utan.save()

    def request_reset(self, email="anna@example.test"):
        return self.client.post(reverse("password_reset"), {"email": email})

    def reset_link(self):
        self.request_reset()
        self.assertEqual(len(mail.outbox), 1)
        match = LINK_RE.search(mail.outbox[0].body)
        self.assertIsNotNone(match, "Mejlet saknar återställningslänk.")
        return match.group(1)

    def set_new_password(self, link, password=NEW_PASSWORD, password2=None):
        form_url = self.client.get(link)["Location"]
        return self.client.post(form_url, {"new_password1": password, "new_password2": password2 or password})

    # --- Begäran och neutral bekräftelse ---

    def test_reset_form_is_reachable_from_login_page(self):
        self.assertContains(self.client.get(reverse("login")), f'href="{reverse("password_reset")}"')
        r = self.client.get(reverse("password_reset"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "csrfmiddlewaretoken")

    def test_registered_user_receives_reset_link(self):
        r = self.request_reset()
        self.assertRedirects(r, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["anna@example.test"])
        self.assertEqual(message.subject, "Återställ ditt lösenord")
        self.assertRegex(message.body, LINK_RE)
        self.assertIn("kan bara användas en gång", message.body)

    def test_email_matching_is_case_insensitive(self):
        self.request_reset("ANNA@Example.TEST")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["anna@example.test"])

    def test_same_neutral_confirmation_whether_or_not_account_exists(self):
        pages = []
        for email in ("anna@example.test", "finnsinte@example.test", "inaktiv@example.test", "utan@example.test"):
            with self.subTest(email=email):
                r = self.client.post(reverse("password_reset"), {"email": email}, follow=True)
                self.assertRedirects(r, reverse("password_reset_done"))
                self.assertContains(r, "Om e-postadressen hör till ett aktivt konto")
                pages.append(r.content)
        self.assertEqual(len(set(pages)), 1)
        # Endast det aktiva kontot med användbart lösenord får ett mejl.
        self.assertEqual([m.to for m in mail.outbox], [["anna@example.test"]])

    def test_delivery_failure_still_gives_neutral_confirmation(self):
        with patch("monitoring.emails.EmailMessage.send", return_value=0), \
                self.assertLogs("monitoring", level="WARNING") as logged:
            r = self.request_reset()
        self.assertRedirects(r, reverse("password_reset_done"))
        self.assertNotIn("anna@example.test", "\n".join(logged.output))

    @override_settings(PLATFORM_BASE_URL="invalid-base-url")
    def test_configuration_failure_still_gives_neutral_confirmation(self):
        with self.assertLogs("monitoring.accounts", level="WARNING") as logged:
            registered = self.client.post(reverse("password_reset"), {"email": "anna@example.test"}, follow=True)
        unknown = self.client.post(reverse("password_reset"), {"email": "unknown@example.test"}, follow=True)
        self.assertRedirects(registered, reverse("password_reset_done"))
        self.assertRedirects(unknown, reverse("password_reset_done"))
        self.assertEqual(registered.content, unknown.content)
        self.assertEqual(mail.outbox, [])
        output = "\n".join(logged.output)
        for private in ("anna@example.test", "invalid-base-url", OLD_PASSWORD):
            self.assertNotIn(private, output)

    def test_reset_request_requires_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(reverse("password_reset"), {"email": "anna@example.test"}).status_code, 403)
        self.assertEqual(mail.outbox, [])

    # --- Token: giltig, ogiltig, använd, utgången ---

    def test_valid_token_allows_new_password(self):
        link = self.reset_link()
        r = self.client.get(link)
        # Django flyttar token till sessionen så att den inte läcker via Referer.
        self.assertEqual(r.status_code, 302)
        self.assertIn("/set-password/", r["Location"])
        self.assertContains(self.client.get(r["Location"]), "Välj nytt lösenord")

        r = self.client.post(r["Location"], {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD})
        self.assertRedirects(r, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertFalse(self.user.check_password(OLD_PASSWORD))
        self.assertTrue(self.client.login(username="anna", password=NEW_PASSWORD))

    def test_token_is_time_limited_and_signed(self):
        link = self.reset_link()
        token = link.rstrip("/").split("/")[-1]
        self.assertTrue(PasswordResetTokenGenerator().check_token(self.user, token))
        self.assertNotIn(OLD_PASSWORD, link)

    def test_invalid_token_shows_understandable_error(self):
        link = self.reset_link()
        uid = link.split("/")[3]
        for bad in (f"/accounts/reset/{uid}/fel-token/", "/accounts/reset/ogiltig/abc-123/"):
            with self.subTest(link=bad):
                r = self.client.get(bad)
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, "Återställningslänken är ogiltig, har gått ut eller har redan använts.")
                self.assertContains(r, f'href="{reverse("password_reset")}"')
                self.assertNotContains(r, "new_password1")

    def test_used_token_cannot_be_reused(self):
        link = self.reset_link()
        self.assertRedirects(self.set_new_password(link), reverse("password_reset_complete"))

        r = self.client.get(link, follow=True)
        self.assertContains(r, "Återställningslänken är ogiltig")
        self.assertNotContains(r, "new_password1")
        # Även ett direkt POST-försök med samma token avvisas.
        uid = link.split("/")[3]
        self.client.post(f"/accounts/reset/{uid}/set-password/",
                         {"new_password1": "Annat-Losen-4711", "new_password2": "Annat-Losen-4711"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_expired_token_is_rejected(self):
        link = self.reset_link()
        later = PasswordResetTokenGenerator()._now() + timedelta(seconds=3601)
        with patch.object(PasswordResetTokenGenerator, "_now", return_value=later):
            r = self.client.get(link, follow=True)
        self.assertContains(r, "Återställningslänken är ogiltig, har gått ut eller har redan använts.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

    def test_token_from_old_password_is_invalid_after_change(self):
        link = self.reset_link()
        self.user.set_password("Helt-Annat-Losen-99")
        self.user.save()
        self.assertContains(self.client.get(link, follow=True), "Återställningslänken är ogiltig")

    # --- Lösenordsvalidering och lagring ---

    def test_reset_uses_django_password_validation(self):
        link = self.reset_link()
        for weak in ("kort1", "1234567890123", "password1234", "anna@example.test"):
            with self.subTest(password=weak):
                r = self.set_new_password(link, weak)
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.context["form"].errors.get("new_password2"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

    def test_reset_rejects_mismatched_passwords(self):
        r = self.set_new_password(self.reset_link(), NEW_PASSWORD, NEW_PASSWORD + "x")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors.get("new_password2"))

    def test_password_is_stored_hashed_and_never_emailed(self):
        link = self.reset_link()
        self.set_new_password(link)
        self.user.refresh_from_db()
        self.assertNotIn(NEW_PASSWORD, self.user.password)
        self.assertTrue(self.user.password.startswith(("pbkdf2_", "argon2", "bcrypt", "scrypt")))
        for message in mail.outbox:
            self.assertNotIn(OLD_PASSWORD, message.body)
            self.assertNotIn(NEW_PASSWORD, message.body)
            self.assertNotIn(self.user.password, message.body)


class PasswordChangeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("anna", "anna@example.test", OLD_PASSWORD)

    def change(self, old=OLD_PASSWORD, new=NEW_PASSWORD, new2=None):
        return self.client.post(reverse("password_change"), {
            "old_password": old, "new_password1": new, "new_password2": new2 or new,
        })

    def test_requires_login(self):
        for name in ("password_change", "password_change_done"):
            with self.subTest(view=name):
                r = self.client.get(reverse(name))
                self.assertRedirects(r, f'{reverse("login")}?next={reverse(name)}', fetch_redirect_response=False)

    def test_dashboard_links_to_password_change_when_logged_in(self):
        self.assertNotContains(self.client.get(reverse("dashboard")), f'href="{reverse("password_change")}"')
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("dashboard")), f'href="{reverse("password_change")}"')

    def test_logged_in_user_can_change_password(self):
        self.client.login(username="anna", password=OLD_PASSWORD)
        r = self.change()
        self.assertRedirects(r, reverse("password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertNotIn(NEW_PASSWORD, self.user.password)
        # Sessionen behålls på aktuell enhet.
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
        self.assertEqual(self.client.get(reverse("password_change_done")).status_code, 200)

    def test_other_sessions_are_logged_out_after_change(self):
        other = Client()
        other.login(username="anna", password=OLD_PASSWORD)
        self.client.login(username="anna", password=OLD_PASSWORD)
        self.change()
        r = other.get(reverse("password_change"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(reverse("login")))

    def test_wrong_old_password_is_rejected(self):
        self.client.force_login(self.user)
        r = self.change(old="fel-losenord")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors.get("old_password"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

    def test_change_uses_django_password_validation(self):
        self.client.force_login(self.user)
        for weak in ("kort1", "1234567890123", "password1234"):
            with self.subTest(password=weak):
                r = self.change(new=weak)
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.context["form"].errors.get("new_password2"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

    def test_change_rejects_mismatched_passwords(self):
        self.client.force_login(self.user)
        r = self.change(new2=NEW_PASSWORD + "x")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors.get("new_password2"))

    def test_change_requires_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        r = strict.post(reverse("password_change"), {
            "old_password": OLD_PASSWORD, "new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD,
        })
        self.assertEqual(r.status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))


class PasswordFieldRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("anna", "anna@example.test", OLD_PASSWORD)

    def assert_field_descriptions_resolve(self, form):
        markup = "".join(render_to_string("accounts/_field.html", {"field": field}) for field in form)
        ids = re.findall(r'\sid="([^"]+)"', markup)
        descriptions = re.findall(r'\saria-describedby="([^"]+)"', markup)
        self.assertTrue(descriptions)
        self.assertEqual(len(ids), len(set(ids)), "Fältgrupper får inte skapa dubbla HTML-id:n.")
        for description in descriptions:
            for target in description.split():
                self.assertIn(target, ids, f"aria-describedby saknar målelement: {target}")

    def test_help_text_is_connected_to_password_fields(self):
        for form_class in (SetPasswordForm, PasswordChangeForm):
            with self.subTest(form=form_class.__name__):
                self.assert_field_descriptions_resolve(form_class(self.user))

    def test_multiple_errors_are_connected_without_duplicate_ids(self):
        for form_class in (SetPasswordForm, PasswordChangeForm):
            with self.subTest(form=form_class.__name__):
                form = form_class(self.user, {
                    "old_password": "fel-losenord", "new_password1": "1", "new_password2": "1",
                })
                self.assertFalse(form.is_valid())
                self.assertGreater(len(form.errors["new_password2"]), 1)
                self.assert_field_descriptions_resolve(form)


class ReferrerPolicyTests(TestCase):
    def test_account_pages_use_same_origin_referrer_policy(self):
        # Med "no-referrer" skickar webbläsare "Origin: null" vid formulär-POST och Djangos
        # CSRF-kontroll svarar 403. Testklienten skickar inget Origin-huvud, så policyn kontrolleras här.
        r = self.client.get(reverse("password_reset"))
        self.assertContains(r, '<meta name="referrer" content="same-origin">')
        self.assertNotContains(r, "no-referrer")
