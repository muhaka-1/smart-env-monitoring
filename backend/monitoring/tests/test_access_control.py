from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from monitoring.models import Reading


class DashboardAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="pat", password="test-password")

    def test_public_dashboard_only_shows_latest_view(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-can-view-history="false"')
        self.assertContains(response, "Logga in")
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

    @override_settings(INGEST_API_KEY="test-ingest-key")
    def test_ingest_with_api_key_does_not_require_session_csrf(self):
        for logged_in in (False, True):
            with self.subTest(logged_in=logged_in):
                client = Client(enforce_csrf_checks=True)
                if logged_in:
                    client.force_login(self.user)
                response = client.post(
                    reverse("readings"),
                    {"sensor_id": f"ingest-{int(logged_in)}", "timestamp": "2026-01-01T10:00:00Z", "value": 5},
                    content_type="application/json",
                    HTTP_X_API_KEY="test-ingest-key",
                )
                self.assertEqual(response.status_code, 201)
        self.assertEqual(Reading.objects.count(), 2)

    @override_settings(INGEST_API_KEY="test-ingest-key")
    def test_session_does_not_replace_required_ingest_api_key(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for headers in ({}, {"HTTP_X_API_KEY": "wrong-key"}):
            with self.subTest(headers=headers):
                response = client.post(
                    reverse("readings"),
                    {"sensor_id": "invalid-key", "timestamp": "2026-01-01T10:00:00Z", "value": 5},
                    content_type="application/json",
                    **headers,
                )
                self.assertEqual(response.status_code, 401)
        self.assertEqual(Reading.objects.count(), 0)

    @override_settings(INGEST_API_KEY="test-ingest-key")
    def test_ingest_api_key_does_not_grant_history_access(self):
        for method in (self.client.get, self.client.head):
            with self.subTest(method=method.__name__):
                response = method(reverse("readings"), HTTP_X_API_KEY="test-ingest-key")
                self.assertIn(response.status_code, (401, 403))
