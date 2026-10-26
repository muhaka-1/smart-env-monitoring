from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.exceptions import ValidationError

from monitoring import services
from monitoring.models import Reading


class EvaluateStatusTests(SimpleTestCase):
    @override_settings(ANOMALY_THRESHOLD=30)
    def test_ok_at_threshold_and_anomaly_above(self):
        self.assertEqual(services.evaluate_status(30), "OK")
        self.assertEqual(services.evaluate_status(30.1), "ANOMALY")


class IngestTests(TestCase):
    def payload(self, **kw):
        base = {"sensor_id": "oak-street-beach", "timestamp": "2026-01-01T10:00:00Z", "value": 12.5}
        return {**base, **kw}

    def test_valid_is_saved_with_status(self):
        r = services.ingest_reading(self.payload(value=99))
        self.assertEqual(r.status, "ANOMALY")
        self.assertEqual(Reading.objects.count(), 1)

    def test_missing_field_rejected(self):
        p = self.payload()
        del p["value"]
        with self.assertRaises(ValidationError):
            services.ingest_reading(p)

    def test_duplicate_rejected(self):
        services.ingest_reading(self.payload())
        with self.assertRaises(ValidationError):
            services.ingest_reading(self.payload())
