from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from monitoring.models import Alert, Notification, Reading


class InterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reader = get_user_model().objects.create_user("reader")
        cls.other = get_user_model().objects.create_user("other")
        for owner, sensor in ((cls.reader, "own-sensor"), (cls.other, "private-sensor")):
            reading = Reading.objects.create(sensor_id=sensor, timestamp=timezone.now(), value=31, status="ANOMALY")
            alert = Alert.objects.create(reading=reading, sensor_id=sensor, metric="turbidity", timestamp=reading.timestamp, value=31, unit="NTU", threshold=30, status="ANOMALY")
            Notification.objects.create(user=owner, alert=alert)

    def test_new_workspaces_require_login_for_get_and_head(self):
        for route in ("history", "report-list"):
            for method in (self.client.get, self.client.head):
                with self.subTest(route=route, method=method):
                    response = method(reverse(route))
                    self.assertRedirects(response, reverse("login") + "?next=" + reverse(route), fetch_redirect_response=False)

    def test_overview_shows_only_own_messages_and_history_is_separate(self):
        self.client.force_login(self.reader)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Min översikt")
        self.assertContains(response, "own-sensor")
        self.assertNotContains(response, "private-sensor")
        self.assertContains(response, 'id="summary-total"')
        self.assertNotContains(response, 'id="history-panel"')
        self.assertIn("no-store", response["Cache-Control"])

    def test_public_html_has_no_user_messages(self):
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, "own-sensor")
        self.assertNotContains(response, "private-sensor")

    def test_shared_navigation_has_active_page_and_post_logout(self):
        self.client.force_login(self.reader)
        for route in ("history", "message-list", "report-list", "password_change"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="app-navigation"')
                self.assertContains(response, 'aria-current="page"')
                self.assertContains(response, 'method="post" action="/accounts/logout/"')
                self.assertNotContains(response, 'href="/admin/"')

    @override_settings(DEBUG=False)
    def test_missing_page_uses_safe_shared_error_view(self):
        response = self.client.get("/missing-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Sidan kunde inte hittas", status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)

    def test_administration_keeps_native_tools_with_platform_branding(self):
        self.reader.is_staff = True
        self.reader.is_superuser = True
        self.reader.save()
        self.client.force_login(self.reader)
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "Badvattenkvalitet · Administration")
        self.assertContains(response, "Till plattformen")
        self.assertContains(response, "administration.css")

    def test_error_templates_do_not_expose_exception_details(self):
        from django.template.loader import render_to_string
        for code in (400, 403, 404, 500):
            with self.subTest(code=code):
                html = render_to_string(f"{code}.html", {"exception": "private-detail"})
                self.assertIn("Till startsidan", html)
                self.assertNotIn("private-detail", html)

    def test_admin_overview_respects_model_permissions(self):
        from django.contrib.auth.models import Permission
        self.reader.is_staff = True
        self.reader.save()
        self.reader.user_permissions.add(Permission.objects.get(codename="view_reading"))
        self.client.force_login(self.reader)
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, 'class="administration-model"')
        self.assertContains(response, reverse("admin:monitoring_reading_changelist"))
        self.assertNotContains(response, reverse("admin:monitoring_reading_add"))
        self.assertNotContains(response, reverse("admin:auth_user_changelist"))
        self.assertNotContains(response, reverse("admin:auth_group_changelist"))

    def test_admin_login_keeps_csrf_form_and_rejects_nonstaff(self):
        response = self.client.get(reverse("admin:login"))
        self.assertContains(response, 'id="login-form"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, "Logga in som administratör")
        self.client.force_login(self.reader)
        response = self.client.get(reverse("admin:index"))
        self.assertRedirects(response, reverse("admin:login") + "?next=" + reverse("admin:index"), fetch_redirect_response=False)
