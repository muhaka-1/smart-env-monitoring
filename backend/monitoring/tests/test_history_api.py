from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from monitoring.models import Reading


class HistoryApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="history-reader", password="test-password")
        for sensor in ("a", "b"):
            for hour in (12, 10, 11):
                Reading.objects.create(
                    sensor_id=sensor,
                    timestamp=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
                    value=hour,
                )

    def setUp(self):
        self.client.force_login(self.user)

    def test_sensor_and_inclusive_time_range(self):
        response = self.client.get(reverse("readings"), {
            "sensor_id": "a", "start": "2026-01-01T10:00:00Z", "end": "2026-01-01T11:00:00Z",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual([r["value"] for r in data["results"]], [10, 11])
        self.assertEqual({r["sensor_id"] for r in data["results"]}, {"a"})

    def test_single_time_bounds(self):
        for params, expected in (
            ({"start": "2026-01-01T11:00:00Z"}, [11, 12]),
            ({"end": "2026-01-01T11:00:00Z"}, [10, 11]),
        ):
            with self.subTest(params=params):
                response = self.client.get(reverse("readings"), {"sensor_id": "a", **params})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([r["value"] for r in response.json()["results"]], expected)

    def test_timezone_offsets_and_equal_bounds(self):
        response = self.client.get(reverse("readings"), {
            "sensor_id": "a", "start": "2026-01-01T12:00:00+02:00", "end": "2026-01-01T10:00:00Z",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r["value"] for r in response.json()["results"]], [10])

    def test_limit_returns_latest_rows_in_requested_order(self):
        for order, expected in (("asc", [11, 12]), ("desc", [12, 11])):
            with self.subTest(order=order):
                response = self.client.get(reverse("readings"), {"sensor_id": "a", "order": order, "limit": 2})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["count"], 2)
                self.assertEqual([r["value"] for r in response.json()["results"]], expected)

    @override_settings(HISTORY_DEFAULT_LIMIT=1, HISTORY_MAX_LIMIT=2)
    def test_default_limit_and_maximum_cap(self):
        for params, expected in (({}, [12]), ({"limit": 999999}, [11, 12])):
            with self.subTest(params=params):
                response = self.client.get(reverse("readings"), {"sensor_id": "a", **params})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([r["value"] for r in response.json()["results"]], expected)
                self.assertEqual(response.json()["count"], len(expected))

    def test_invalid_filters_return_field_errors(self):
        for field, value in (
            ("start", "nope"), ("end", "nope"), ("start", "2026-02-30T10:00:00Z"),
            ("end", "2026-13-01T10:00:00Z"), ("start", ""), ("end", ""),
            ("limit", "abc"), ("limit", "1.5"), ("limit", "0"), ("limit", "-1"),
            ("order", "invalid"), ("order", ""), ("sensor_id", "Bad ID!"), ("sensor_id", ""),
        ):
            with self.subTest(field=field, value=value):
                response = self.client.get(reverse("readings"), {field: value})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

    def test_reversed_range_returns_field_error(self):
        response = self.client.get(reverse("readings"), {
            "start": "2026-01-01T12:00:00Z", "end": "2026-01-01T10:00:00Z",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("end", response.json())

    def test_dates_outside_utc_range_return_field_errors(self):
        for field in ("start", "end"):
            for value in ("0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-14:00"):
                with self.subTest(field=field, value=value):
                    response = self.client.get(reverse("readings"), {field: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(field, response.json())

    def test_no_matches_returns_empty_history(self):
        for params in (
            {"sensor_id": "missing"},
            {"start": "2026-02-01T00:00:00Z"},
        ):
            with self.subTest(params=params):
                response = self.client.get(reverse("readings"), params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {
                    "metric": None, "unit": None, "threshold": None, "count": 0, "results": [],
                })
