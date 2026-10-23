from django.test import TestCase, override_settings
from django.urls import reverse


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

    def test_health_and_dashboard(self):
        self.assertEqual(self.client.get(reverse("health")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
