from django.test import TestCase, override_settings
from django.urls import reverse

from monitoring.models import Reading


def make(sensor="a", ts="2026-01-01T10:00:00Z", value=5.0):
    return {"sensor_id": sensor, "timestamp": ts, "value": value}


class ApiTests(TestCase):
    def post(self, data, **extra):
        return self.client.post(reverse("readings"), data, content_type="application/json", **extra)

    def test_post_valid_returns_201(self):
        r = self.post(make())
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["status"], "OK")

    def test_post_invalid_returns_400(self):
        self.assertEqual(self.post({"sensor_id": "a"}).status_code, 400)
        self.assertEqual(self.post(make(value="abc")).status_code, 400)
        self.assertEqual(self.post(make(sensor="Bad ID!")).status_code, 400)

    def test_post_rejects_out_of_range_values_without_saving(self):
        for metric, value in (("turbidity", -0.1), ("temperature", -5.1), ("temperature", 50.1)):
            with self.subTest(metric=metric, value=value):
                response = self.post({**make(), "metric": metric, "value": value})
                self.assertEqual(response.status_code, 400)
                self.assertIn("value", response.json())
                self.assertEqual(Reading.objects.count(), 0)

    def test_post_accepts_range_boundaries(self):
        for index, (metric, value) in enumerate((("turbidity", 0), ("temperature", -5), ("temperature", 50))):
            with self.subTest(metric=metric, value=value):
                response = self.post({**make(sensor=f"boundary-{index}"), "metric": metric, "value": value})
                self.assertEqual(response.status_code, 201)
                self.assertEqual(Reading.objects.get(pk=response.json()["id"]).value, value)

    @override_settings(INGEST_API_KEY="secret")
    def test_api_key_enforced(self):
        self.assertEqual(self.post(make()).status_code, 401)
        self.assertEqual(self.post(make(), HTTP_X_API_KEY="secret").status_code, 201)

    def test_latest(self):
        self.post(make(ts="2026-01-01T10:00:00Z", value=1))
        self.post(make(ts="2026-01-01T11:00:00Z", value=2))
        r = self.client.get(reverse("readings-latest"), {"sensor_id": "a"})
        self.assertEqual(r.json()["value"], 2)
        self.assertEqual(self.client.get(reverse("readings-latest"), {"sensor_id": "x"}).status_code, 404)

    def test_history_filter_and_sort(self):
        for h in (10, 11, 12):
            self.post(make(ts=f"2026-01-01T{h}:00:00Z", value=h))
        r = self.client.get(reverse("readings"), {"sensor_id": "a", "start": "2026-01-01T10:30:00Z"}).json()
        self.assertEqual([x["value"] for x in r["results"]], [11, 12])
        d = self.client.get(reverse("readings"), {"order": "desc"}).json()
        self.assertEqual([x["value"] for x in d["results"]], [12, 11, 10])

    def test_history_bad_params(self):
        self.assertEqual(self.client.get(reverse("readings"), {"start": "nope"}).status_code, 400)
        self.assertEqual(self.client.get(reverse("readings"), {"limit": "x"}).status_code, 400)

    def test_history_returns_metric_unit_threshold(self):
        self.post({"sensor_id": "t1", "metric": "temperature", "timestamp": "2026-01-01T10:00:00Z", "value": 20})
        r = self.client.get(reverse("readings"), {"sensor_id": "t1"}).json()
        self.assertEqual((r["metric"], r["unit"], r["threshold"]), ("temperature", "°C", 25.0))
        self.assertEqual(r["results"][0]["threshold"], 25.0)

    def test_mixed_history_has_no_shared_metric_or_threshold(self):
        self.post({**make(sensor="a"), "metric": "temperature"})
        self.post({**make(sensor="b", value=30), "metric": "turbidity"})
        self.post({**make(sensor="a", ts="2026-01-01T11:00:00Z"), "metric": "turbidity"})
        for order in ("asc", "desc"):
            result = self.client.get(reverse("readings"), {"order": order}).json()
            self.assertEqual(result["count"], 3)
            self.assertIsNone(result["metric"])
            self.assertIsNone(result["unit"])
            self.assertIsNone(result["threshold"])

    def test_unit_must_match_metric(self):
        self.assertEqual(self.post({**make(), "unit": "<img src=x onerror=alert(1)>"}).status_code, 400)
        self.assertEqual(self.post({**make(sensor="t1"), "metric": "temperature", "unit": "NTU"}).status_code, 400)
        self.assertEqual(self.post({**make(sensor="t2"), "metric": "temperature", "unit": "°C"}).status_code, 201)
        self.assertEqual(self.post({**make(sensor="t3"), "unit": "NTU"}).status_code, 201)

    @override_settings(READING_STALE_SECONDS=42)
    def test_dashboard_includes_staleness_setting(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, 'data-reading-stale-seconds="42"')

    def test_health_and_dashboard(self):
        self.assertEqual(self.client.get(reverse("health")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_dashboard_explains_project_status(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "inte aktuella mätningar på plats")
        self.assertContains(response, "OK betyder att värdet inte överstiger den konfigurerade gränsen")
        self.assertContains(response, "ANOMALY betyder att gränsen har överskridits")
        self.assertContains(response, "Statusen bedömer inte om vattnet är säkert att bada i")
