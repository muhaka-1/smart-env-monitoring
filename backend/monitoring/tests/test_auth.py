from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()
PASSWORD = "hemligt-losen-123"


class LoginLogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("anna", password=PASSWORD)
        User.objects.create_user("inaktiv", password=PASSWORD, is_active=False)

    def login(self, username="anna", password=PASSWORD, next_url=None):
        data = {"username": username, "password": password}
        if next_url:
            data["next"] = next_url
        return self.client.post(reverse("login"), data)

    def test_login_page_has_csrf_token(self):
        r = self.client.get(reverse("login"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "csrfmiddlewaretoken")

    def test_successful_login_creates_session(self):
        r = self.login()
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_wrong_password_shows_error_and_no_session(self):
        r = self.login(password="fel")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Fel användarnamn eller lösenord")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_error_is_same_for_unknown_wrong_and_inactive(self):
        errors = {
            tuple(self.login(u, p).context["form"].non_field_errors())
            for u, p in [("anna", "fel"), ("finnsinte", PASSWORD), ("inaktiv", PASSWORD)]
        }
        self.assertEqual(len(errors), 1)

    def test_redirects_to_safe_next(self):
        r = self.login(next_url="/api/readings/")
        self.assertRedirects(r, "/api/readings/", fetch_redirect_response=False)

    def test_rejects_external_next(self):
        r = self.login(next_url="https://evil.example/")
        self.assertRedirects(r, "/", fetch_redirect_response=False)

    def test_logout_ends_session(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("logout"))
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)

    def test_login_form_rejects_missing_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        r = strict.post(reverse("login"), {"username": "anna", "password": PASSWORD})
        self.assertEqual(r.status_code, 403)

    def test_public_dashboard_works_without_login(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '<h1 class="navbar-brand mb-0 h1">🌊 Badvattenkvalitet</h1>', html=True)

    def test_public_dashboard_shows_login_link(self):
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, f'href="{reverse("login")}"')
        self.assertNotContains(r, f'action="{reverse("logout")}"')

    def test_authenticated_dashboard_shows_logout_form(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "Inloggad som anna")
        self.assertContains(r, f'action="{reverse("logout")}"')
        self.assertContains(r, "csrfmiddlewaretoken")
        self.assertNotContains(r, f'href="{reverse("login")}"')

    def test_dashboard_logout_requires_csrf_and_ends_session(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        dashboard = strict.get(reverse("dashboard"))
        csrf_token = dashboard.cookies["csrftoken"].value

        self.assertEqual(strict.post(reverse("logout")).status_code, 403)
        self.assertIn("_auth_user_id", strict.session)

        r = strict.post(reverse("logout"), {"csrfmiddlewaretoken": csrf_token})
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", strict.session)
        self.assertContains(strict.get(reverse("dashboard")), f'href="{reverse("login")}"')
