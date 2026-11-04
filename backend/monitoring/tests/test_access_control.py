from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class DashboardAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="pat", password="test-password")

    def test_public_dashboard_only_shows_latest_view(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-can-view-history="false"')
        self.assertContains(response, "Publik vy")
        self.assertContains(response, "de senaste mätvärdena")
        self.assertNotContains(response, 'id="history-panel"')
        self.assertNotContains(response, 'id="sensor"')

    def test_authenticated_dashboard_shows_history_controls(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-can-view-history="true"')
        self.assertContains(response, "Inloggad som pat")
        self.assertContains(response, 'id="history-panel"')
        self.assertContains(response, 'id="sensor"')

    def test_latest_readings_remain_public(self):
        response = self.client.get(reverse("readings-latest"))

        self.assertEqual(response.status_code, 200)

    def test_anonymous_user_cannot_read_history_api(self):
        response = self.client.get(reverse("readings"))

        self.assertIn(response.status_code, (401, 403))

    def test_anonymous_user_cannot_probe_history_with_head(self):
        response = self.client.head(reverse("readings"))

        self.assertIn(response.status_code, (401, 403))

    def test_authenticated_user_can_read_history_api(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("readings"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_anonymous_ingest_still_uses_api_key_flow(self):
        response = self.client.post(
            reverse("readings"),
            {
                "sensor_id": "public-ingest",
                "timestamp": "2026-01-01T10:00:00Z",
                "value": 5,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
