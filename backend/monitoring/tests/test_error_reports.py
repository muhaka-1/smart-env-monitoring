from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from monitoring.models import Alert, Notification, Reading

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ErrorReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("report-reader", "reader@example.test", "Test-Strand-2026!")
        cls.other = User.objects.create_user("other-reader", "other@example.test", "Test-Strand-2026!")
        cls.start = datetime(2026, 1, 1, 10, tzinfo=timezone.utc)
        cls.first = cls.make_alert(cls.user, "oak-temperature", cls.start, 27.1, "temperature", "°C", 25)
        cls.second = cls.make_alert(cls.user, "oak-temperature", cls.start+timedelta(hours=2), 28.2, "temperature", "°C", 25)
        cls.turbidity = cls.make_alert(cls.user, "oak-turbidity", cls.start+timedelta(hours=1), 31.3, "turbidity", "NTU", 30)
        cls.hidden = cls.make_alert(cls.other, "hidden-temperature", cls.start, 49.9, "temperature", "°C", 25)

    @staticmethod
    def make_alert(user, sensor, timestamp, value, metric="temperature", unit="°C", threshold=25):
        reading = Reading.objects.create(sensor_id=sensor, timestamp=timestamp, value=value, metric=metric, unit=unit, status="ANOMALY")
        alert = Alert.objects.create(reading=reading, sensor_id=sensor, timestamp=timestamp, value=value,
                                     metric=metric, unit=unit, threshold=threshold, status="ANOMALY")
        Notification.objects.create(user=user, alert=alert)
        return alert

    def setUp(self):
        self.page_url = reverse("error-report")
        self.pdf_url = reverse("error-report-pdf")

    def login(self):
        self.client.force_login(self.user)

    def text(self, response):
        self.assertEqual(response.status_code, 200)
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages)

    def test_anonymous_page_and_pdf_require_login_even_with_direct_urls(self):
        for url in (self.page_url, self.pdf_url):
            response = self.client.get(url, {"sensor_id": "oak-temperature"})
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response["Location"])
            self.assertNotIn(b"oak-temperature", response.content)

    def test_only_current_users_alerts_and_sensor_choices_are_available(self):
        self.login()
        response = self.client.get(self.page_url, {"user_id": self.other.pk})
        self.assertEqual(response.context["total"], 3)
        self.assertEqual(list(response.context["page_obj"]), [self.second, self.turbidity, self.first])
        self.assertNotContains(response, "hidden-temperature")
        self.assertNotContains(response, self.other.email)
        self.assertNotIn("hidden-temperature", self.text(self.client.get(self.pdf_url)))

    def test_shared_alert_is_not_duplicated_for_multiple_recipients(self):
        Notification.objects.create(user=self.other, alert=self.first)
        self.login()
        self.assertEqual(self.client.get(self.page_url).context["total"], 3)

    def test_report_contains_all_snapshot_fields(self):
        self.login()
        response = self.client.get(self.page_url)
        text = self.text(self.client.get(self.pdf_url))
        for expected in ("oak-temperature", "oak-turbidity", "Temperatur", "Turbiditet", "2026-01-01 10:00:00", "°C", "NTU", "Gränsvärde", "Status"):
            self.assertContains(response, expected)
            self.assertIn(expected, text)
        self.assertContains(response, "Avvikelse")
        self.assertIn("Avvikelse", text)
        self.assertIn("27,1", text)
        self.assertIn("25,0", text)

    def test_sensor_and_inclusive_time_filters_match_on_screen_and_pdf(self):
        self.login()
        params = {"sensor_id": "oak-temperature", "start": self.start.isoformat(), "end": self.start.isoformat()}
        response = self.client.get(self.page_url, params)
        self.assertEqual(list(response.context["page_obj"]), [self.first])
        text = self.text(self.client.get(self.pdf_url, params))
        self.assertIn("27,1", text)
        self.assertNotIn("28,2", text)
        self.assertNotIn("oak-turbidity", text)
        self.assertNotIn("hidden-temperature", text)

    def test_each_optional_time_boundary_works_independently(self):
        self.login()
        for params, expected in (({"start": "2026-01-01T11:00:00Z"}, [self.second, self.turbidity]),
                                 ({"end": "2026-01-01T10:00:00Z"}, [self.first])):
            response = self.client.get(self.page_url, params)
            self.assertEqual(list(response.context["page_obj"]), expected)

    @override_settings(TIME_ZONE="Europe/Stockholm")
    def test_utc_filter_semantics_display_and_offset_conversion(self):
        self.login()
        for start in ("2026-01-01T10:00:00", "2026-01-01T12:00:00+02:00"):
            params = {"start": start, "end": "2026-01-01T10:00:00Z"}
            response = self.client.get(self.page_url, params)
            self.assertEqual(list(response.context["page_obj"]), [self.first])
            self.assertContains(response, "2026-01-01 10:00:00")
            self.assertIn("2026-01-01 10:00:00", self.text(self.client.get(self.pdf_url, params)))
            self.assertEqual(response.context["form"].initial["start"], datetime(2026, 1, 1, 10))

    def test_filter_uses_reading_time_instead_of_message_creation_time(self):
        self.login()
        Notification.objects.filter(user=self.user).update(created_at=self.start+timedelta(days=100))
        response = self.client.get(self.page_url, {"end": self.start.isoformat()})
        self.assertEqual(list(response.context["page_obj"]), [self.first])

    def test_stored_threshold_and_status_are_not_recalculated(self):
        self.login()
        Reading.objects.filter(pk=self.first.reading_id).update(value=1, status="OK")
        with override_settings(ANOMALY_THRESHOLDS={"temperature": 99}):
            response = self.client.get(self.page_url, {"end": self.start.isoformat()})
            saved = list(response.context["page_obj"])[0]
            self.assertEqual((saved.value, saved.threshold, saved.status), (27.1, 25, "ANOMALY"))
            text = self.text(self.client.get(self.pdf_url, {"end": self.start.isoformat()}))
        self.assertIn("27,1", text)
        self.assertIn("25,0", text)

    def test_invalid_filters_return_400_on_both_routes(self):
        self.login()
        for params in ({"sensor_id": "<bad>"}, {"sensor_id": "a"*101}, {"sensor_id": "bad\n"},
                       {"start": "bad"}, {"end": "2026-99-01T00:00:00"},
                       {"start": "2026-01-02T00:00:00", "end": "2026-01-01T00:00:00"},
                       {"start": "0001-01-01T00:00:00+14:00"}):
            for url in (self.page_url, self.pdf_url):
                with self.subTest(params=params, url=url):
                    response = self.client.get(url, params)
                    self.assertEqual(response.status_code, 400)
                    self.assertTrue(response.context["form"].errors)

    def test_unknown_sensor_and_empty_interval_show_clear_empty_result(self):
        self.login()
        for params in ({"sensor_id": "missing"}, {"start": "2027-01-01T00:00:00"}, {"sensor_id": "hidden-temperature"}):
            self.assertContains(self.client.get(self.page_url, params), "Inga sparade avvikelser finns")
            self.assertIn("Inga sparade avvikelser finns", self.text(self.client.get(self.pdf_url, params)))

    def test_user_without_notifications_has_empty_report(self):
        user = User.objects.create_user("new-reader", password="Test-Strand-2026!")
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.page_url).context["total"], 0)
        self.assertNotIn("oak-temperature", self.text(self.client.get(self.pdf_url)))

    def test_pdf_type_filename_and_creation_metadata(self):
        self.login()
        response = self.client.get(self.pdf_url)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="felrapport.pdf"')
        self.assertTrue(response.content.startswith(b"%PDF"))
        text = self.text(response)
        for expected in ("Felrapport", "Rapport skapad (UTC):", "Tidsintervall (UTC):", "Ingen startgräns", "Ingen slutgräns", "Sida 1"):
            self.assertIn(expected, text)

    def test_pagination_keeps_filters_and_pdf_exports_all_matching_pages(self):
        self.login()
        for index in range(24):
            self.make_alert(self.user, "oak-temperature", self.start+timedelta(days=1, minutes=index), 30+index/10)
        params = {"sensor_id": "oak-temperature", "start": self.start.isoformat()}
        first = self.client.get(self.page_url, params)
        second = self.client.get(self.page_url, {**params, "page": 2})
        expected = list(first.context["page_obj"])+list(second.context["page_obj"])
        self.assertEqual((first.context["total"], len(first.context["page_obj"]), len(second.context["page_obj"])), (26, 20, 6))
        query = parse_qs(urlsplit(second.context["pdf_url"]).query)
        self.assertEqual(query["sensor_id"], ["oak-temperature"])
        self.assertNotIn("page", query)
        text = self.text(self.client.get(second.context["pdf_url"]))
        table_text = text.split("Sensor-ID", 1)[1]
        positions = [table_text.index(alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")) for alert in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Antal händelser: 26", text)

    def test_report_navigation_is_available_only_after_login(self):
        self.assertNotContains(self.client.get(reverse("dashboard")), f'href="{self.page_url}"')
        self.login()
        self.assertContains(self.client.get(reverse("dashboard")), f'href="{reverse("report-list")}"')
        self.assertContains(self.client.get(reverse("report-list")), f'href="{self.page_url}"')
        self.assertContains(self.client.get(reverse("message-list")), f'href="{self.page_url}"')

    def test_new_events_do_not_change_export_of_already_displayed_selection(self):
        self.login()
        response = self.client.get(self.page_url)
        export_url = response.context["pdf_url"]
        cutoff_query = response.context["filter_query"]
        self.make_alert(self.user, "new-arrival", self.start, 26)
        text = self.text(self.client.get(export_url))
        self.assertNotIn("new-arrival", text)
        self.assertEqual(self.client.get(self.page_url+"?"+cutoff_query).context["total"], 3)
        self.assertEqual(self.client.get(self.page_url).context["total"], 4)

    def test_invalid_selection_time_returns_validation_error(self):
        self.login()
        for url in (self.page_url, self.pdf_url):
            self.assertEqual(self.client.get(url, {"as_of": "invalid"}).status_code, 400)

    def test_reports_are_read_only_private_and_reject_inactive_users(self):
        self.login()
        for url in (self.page_url, self.pdf_url):
            self.assertEqual(self.client.post(url, {}).status_code, 405)
            self.assertIn("no-store", self.client.get(url)["Cache-Control"])
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        for url in (self.page_url, self.pdf_url):
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_reporting_does_not_write_events_or_send_email(self):
        self.login()
        before = (Reading.objects.count(), Alert.objects.count(), Notification.objects.count())
        with patch("monitoring.emails.send_platform_email") as send:
            self.client.get(self.page_url)
            self.client.get(self.pdf_url)
        send.assert_not_called()
        self.assertEqual(before, (Reading.objects.count(), Alert.objects.count(), Notification.objects.count()))

    def test_long_sensor_identifiers_wrap_in_multipage_pdf(self):
        self.login()
        sensor = "sensor-"+"a"*93
        for index in range(50):
            self.make_alert(self.user, sensor, self.start+timedelta(minutes=index), 26)
        response = self.client.get(self.pdf_url, {"sensor_id": sensor})
        pdf = PdfReader(BytesIO(response.content))
        self.assertGreater(len(pdf.pages), 1)
        for page in pdf.pages:
            self.assertIn("Sensor-ID", page.extract_text())
            self.assertIn("Status", page.extract_text())

    def test_pdf_has_no_inherited_200_row_history_limit(self):
        self.login()
        readings = Reading.objects.bulk_create([
            Reading(sensor_id="many-temperature", timestamp=self.start+timedelta(minutes=index),
                    metric="temperature", value=26, unit="°C", status="ANOMALY")
            for index in range(205)
        ])
        alerts = Alert.objects.bulk_create([
            Alert(reading=r, sensor_id=r.sensor_id, timestamp=r.timestamp, metric=r.metric,
                  value=r.value, unit=r.unit, status=r.status, threshold=25) for r in readings
        ])
        Notification.objects.bulk_create([Notification(user=self.user, alert=alert) for alert in alerts])
        response = self.client.get(self.page_url, {"sensor_id": "many-temperature"})
        self.assertEqual(response.context["total"], 205)
        text = self.text(self.client.get(response.context["pdf_url"]))
        self.assertIn("Antal händelser: 205", text)
        self.assertEqual(text.count("many-temperature"), 206)

    def test_stored_text_is_escaped_in_html_and_pdf(self):
        self.login()
        Alert.objects.filter(pk=self.first.pk).update(sensor_id="<script>bad</script>")
        response = self.client.get(self.page_url)
        self.assertNotContains(response, "<script>bad</script>")
        self.assertContains(response, "&lt;script&gt;bad&lt;/script&gt;")
        self.assertIn("<script>bad</script>", self.text(self.client.get(self.pdf_url)))
