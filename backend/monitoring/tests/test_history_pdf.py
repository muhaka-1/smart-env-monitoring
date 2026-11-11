from datetime import datetime, timezone
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader

from monitoring.models import Reading


class HistoryPdfTests(TestCase):
    sensor_id = "test-beach-turbidity"

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="pdf-user",
            password="test-password",
        )
        self.url = reverse("history-pdf")

        Reading.objects.create(
            sensor_id=self.sensor_id,
            metric=Reading.Metric.TURBIDITY,
            timestamp=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
            value=11.0,
            unit="NTU",
            status=Reading.Status.OK,
        )
        Reading.objects.create(
            sensor_id=self.sensor_id,
            metric=Reading.Metric.TURBIDITY,
            timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            value=22.0,
            unit="NTU",
            status=Reading.Status.OK,
        )
        Reading.objects.create(
            sensor_id="other-beach-turbidity",
            metric=Reading.Metric.TURBIDITY,
            timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            value=99.0,
            unit="NTU",
            status=Reading.Status.ANOMALY,
        )

    @staticmethod
    def pdf_text(response):
        reader = PdfReader(BytesIO(response.content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(
            self.url,
            {"sensor_id": self.sensor_id},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_authenticated_user_receives_pdf(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {"sensor_id": self.sensor_id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(
            'filename="historik-test-beach-turbidity.pdf"',
            response["Content-Disposition"],
        )
        self.assertTrue(response.content.startswith(b"%PDF"))

        text = self.pdf_text(response)
        self.assertIn("Historiska mätvärden", text)
        self.assertIn(self.sensor_id, text)
        self.assertIn("Turbiditet", text)
        self.assertIn("11.0", text)
        self.assertIn("22.0", text)
        self.assertNotIn("99.0", text)

    def test_time_filter_is_applied(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "sensor_id": self.sensor_id,
                "start": "2026-01-01T11:00:00Z",
                "end": "2026-01-01T13:00:00Z",
            },
        )

        self.assertEqual(response.status_code, 200)
        text = self.pdf_text(response)
        self.assertNotIn("11.0", text)
        self.assertIn("22.0", text)

    def test_empty_result_is_explained(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {"sensor_id": "missing-sensor"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Inga mätvärden finns",
            self.pdf_text(response),
        )

    def test_invalid_sensor_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {"sensor_id": "<invalid>"},
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_time_range_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "sensor_id": self.sensor_id,
                "start": "2026-01-02T12:00:00Z",
                "end": "2026-01-01T12:00:00Z",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_dates_outside_utc_range_are_rejected(self):
        self.client.force_login(self.user)
        for field in ("start", "end"):
            for value in ("0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-14:00"):
                with self.subTest(field=field, value=value):
                    response = self.client.get(self.url, {"sensor_id": self.sensor_id, field: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertNotEqual(response.get("Content-Type"), "application/pdf")

    def test_pdf_button_only_visible_after_login(self):
        public_response = self.client.get(reverse("dashboard"))
        self.assertNotContains(public_response, 'id="download-pdf"')

        self.client.force_login(self.user)
        authenticated_response = self.client.get(reverse("dashboard"))
        self.assertContains(authenticated_response, 'id="download-pdf"')

    def test_admin_link_only_visible_to_staff(self):
        self.client.force_login(self.user)

        regular_response = self.client.get(reverse("dashboard"))
        self.assertNotContains(regular_response, 'href="/admin/"')

        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])

        staff_response = self.client.get(reverse("dashboard"))
        self.assertContains(staff_response, 'href="/admin/"')
        self.assertContains(staff_response, "Admin")
