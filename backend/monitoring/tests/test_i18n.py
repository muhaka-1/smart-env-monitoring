from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class InternationalisationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("reader", password="test-password")

    def select_language(self, language, next_url=None):
        return self.client.post(
            reverse("set_language"),
            {"language": language, "next": next_url or reverse("dashboard")},
        )

    def test_swedish_is_the_default_language(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="sv">')
        self.assertContains(response, "Badvattenkvalitet")
        self.assertContains(response, "Senaste mätvärden")
        self.assertContains(response, 'action="/i18n/setlang/"')
        self.assertContains(response, '<option value="sv" selected>')

    def test_english_selection_is_saved_and_follows_navigation_to_login(self):
        response = self.select_language("en")

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.assertEqual(response.cookies["django_language"].value, "en")

        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, '<html lang="en">')
        self.assertContains(dashboard, "Bathing water quality")
        self.assertContains(dashboard, "Latest readings")
        self.assertContains(dashboard, "Turbidity")
        self.assertNotContains(dashboard, "Senaste mätvärden")

        login = self.client.get(reverse("login"))
        self.assertContains(login, '<html lang="en">')
        self.assertContains(login, '<option value="en" selected>')

    def test_german_selection_translates_dashboard_and_dynamic_strings(self):
        self.select_language("de")

        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, '<html lang="de">')
        self.assertContains(response, "Badegewässerqualität")
        self.assertContains(response, "Neueste Messwerte")
        self.assertContains(response, "Trübung")
        self.assertNotContains(response, "Senaste mätvärden")

    def test_authenticated_workspaces_use_the_selected_language(self):
        self.client.force_login(self.user)
        self.select_language("en", reverse("history"))

        history = self.client.get(reverse("history"))
        messages = self.client.get(reverse("message-list"))
        reports = self.client.get(reverse("report-list"))

        self.assertContains(history, '<html lang="en">')
        self.assertContains(history, "Explore previous readings")
        self.assertContains(messages, "You have no saved messages.")
        self.assertContains(reports, "Reports")

