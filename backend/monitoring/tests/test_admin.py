from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from monitoring.models import Reading


class ReadingAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(
            "reading-admin", is_staff=True, is_superuser=True,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def data(self, **changes):
        return {
            "sensor_id": "admin-reading", "metric": "turbidity",
            "timestamp_0": "2026-01-01", "timestamp_1": "10:00:00",
            "value": "-1", "unit": "NTU", "quality": "good", "status": "OK",
            "_save": "Spara", **changes,
        }

    def test_add_rejects_negative_turbidity_without_saving(self):
        response = self.client.post(reverse("admin:monitoring_reading_add"), self.data())
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["adminform"].form, "value", "Turbiditet får inte vara negativ.")
        self.assertFalse(Reading.objects.exists())

    def test_change_rejects_negative_turbidity_and_preserves_saved_value(self):
        reading = Reading.objects.create(
            sensor_id="admin-reading", metric="turbidity", value=8, unit="NTU",
            timestamp=datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
        )
        response = self.client.post(reverse("admin:monitoring_reading_change", args=[reading.pk]), self.data())
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["adminform"].form, "value", "Turbiditet får inte vara negativ.")
        reading.refresh_from_db()
        self.assertEqual(reading.value, 8)
        self.assertEqual(Reading.objects.count(), 1)

    def test_zero_turbidity_is_accepted(self):
        response = self.client.post(reverse("admin:monitoring_reading_add"), self.data(value="0"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reading.objects.get().value, 0)

    def test_negative_temperature_remains_accepted(self):
        response = self.client.post(
            reverse("admin:monitoring_reading_add"),
            self.data(metric="temperature", value="-5", unit="°C"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reading.objects.get().value, -5)
