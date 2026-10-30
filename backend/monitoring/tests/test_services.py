from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.exceptions import ValidationError

from monitoring import services
from monitoring.models import Reading


class EvaluateStatusTests(SimpleTestCase):
    @override_settings(ANOMALY_THRESHOLDS={"turbidity": 30, "temperature": 25})
    def test_ok_at_threshold_and_anomaly_above(self):
        for metric, threshold in (("turbidity", 30), ("temperature", 25)):
            for value, expected in ((threshold - 0.1, "OK"), (threshold, "OK"), (threshold + 0.1, "ANOMALY")):
                with self.subTest(metric=metric, value=value):
                    self.assertEqual(services.evaluate_status(value, metric), expected)

    @override_settings(ANOMALY_THRESHOLDS={"turbidity": 30, "temperature": 25})
    def test_threshold_is_per_metric(self):
        self.assertEqual(services.evaluate_status(26, "temperature"), "ANOMALY")
        self.assertEqual(services.evaluate_status(26, "turbidity"), "OK")


class IngestTests(TestCase):
    def payload(self, **kw):
        base = {"sensor_id": "oak-street-beach", "timestamp": "2026-01-01T10:00:00Z", "value": 12.5}
        return {**base, **kw}

    def test_valid_is_saved_with_status(self):
        r = services.ingest_reading(self.payload(value=99))
        self.assertEqual(r.status, "ANOMALY")
        self.assertEqual(Reading.objects.count(), 1)

    def test_temperature_gets_default_unit_and_own_threshold(self):
        r = services.ingest_reading(self.payload(sensor_id="oak-temperature", metric="temperature", value=27))
        self.assertEqual((r.unit, r.status), ("°C", "ANOMALY"))

    def test_unknown_metric_rejected(self):
        with self.assertRaises(ValidationError):
            services.ingest_reading(self.payload(metric="ph"))

    def test_missing_field_rejected(self):
        p = self.payload()
        del p["value"]
        with self.assertRaises(ValidationError):
            services.ingest_reading(p)

    def test_duplicate_rejected(self):
        services.ingest_reading(self.payload())
        with self.assertRaises(ValidationError):
            services.ingest_reading(self.payload())
