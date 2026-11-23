import io
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from monitoring import services
from monitoring.ai import anomaly
from monitoring.models import Reading, ReadingAssessment

from .ai_helpers import START, clean_state, make_readings, steady


class AssessValueTests(SimpleTestCase):
    def test_too_little_history_gives_no_assessment(self):
        self.assertIsNone(anomaly.assess_value([10.0] * (anomaly.MIN_HISTORY - 1), 500.0, "turbidity"))

    def test_normal_noise_is_never_flagged(self):
        values = steady(12.0, count=80, wobble=0.4)
        findings = anomaly.analyse_series(values, "turbidity")
        self.assertEqual([f for f in findings if f], [])

    def test_slow_drift_is_not_flagged(self):
        values = [15 + i * 0.05 for i in range(60)]
        self.assertEqual([f for f in anomaly.analyse_series(values, "temperature") if f], [])

    def test_frozen_value_is_a_suspected_sensor_fault(self):
        history = steady(14.0, count=10) + [14.0] * 5
        finding = anomaly.assess_value(history, 14.0, "turbidity")
        self.assertEqual((finding.kind, finding.reason), ("sensor_fault", "flatline"))

    def test_constant_series_from_the_start_is_not_called_frozen(self):
        self.assertIsNone(anomaly.assess_value([5.0] * 20, 5.0, "turbidity"))

    def test_sudden_zero_after_normal_values_is_a_sensor_fault(self):
        finding = anomaly.assess_value(steady(12.0), 0.0, "turbidity")
        self.assertEqual((finding.kind, finding.reason), ("sensor_fault", "zero"))

    def test_zero_is_normal_when_the_sensor_usually_reads_near_zero(self):
        self.assertIsNone(anomaly.assess_value(steady(0.3, wobble=0.1), 0.0, "turbidity"))

    def test_implausible_jump_is_a_sensor_fault(self):
        finding = anomaly.assess_value(steady(20.0), 60.0, "temperature")
        self.assertEqual((finding.kind, finding.reason), ("sensor_fault", "jump"))

    def test_clear_but_plausible_change_is_a_statistical_deviation(self):
        finding = anomaly.assess_value(steady(10.0), 12.5, "turbidity")
        self.assertEqual((finding.kind, finding.reason), ("deviation", "outlier"))

    def test_series_analysis_does_not_look_ahead(self):
        values = steady(10.0, count=12) + [12.5]
        self.assertEqual(anomaly.analyse_series(values, "turbidity")[:12], [None] * 12)
        self.assertEqual(anomaly.analyse_series(values, "turbidity")[12].reason, "outlier")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   ANOMALY_THRESHOLDS={"turbidity": 30, "temperature": 25})
class IngestIntegrationTests(TestCase):
    def setUp(self):
        clean_state()
        make_readings("beach-a", "turbidity", steady(12.0, count=12))

    def ingest(self, value, **extra):
        payload = {"sensor_id": "beach-a", "metric": "turbidity", "value": value,
                   "timestamp": "2026-01-01T10:00:00Z", **extra}
        with self.captureOnCommitCallbacks(execute=True):
            return services.ingest_reading(payload)

    def test_sensor_fault_marks_quality_suspect_and_is_saved(self):
        reading = self.ingest(0.0)
        reading.refresh_from_db()
        self.assertEqual(reading.quality, Reading.Quality.SUSPECT)
        self.assertEqual(reading.assessment.reason, "zero")

    def test_deviation_is_saved_without_changing_quality(self):
        reading = self.ingest(14.5)
        reading.refresh_from_db()
        self.assertEqual(reading.quality, Reading.Quality.GOOD)
        self.assertEqual(reading.assessment.kind, "deviation")

    def test_normal_value_creates_no_assessment(self):
        reading = self.ingest(12.1)
        self.assertFalse(ReadingAssessment.objects.filter(reading=reading).exists())

    def test_threshold_status_is_independent_of_the_assessment(self):
        reading = self.ingest(60.0)
        self.assertEqual(reading.status, Reading.Status.ANOMALY)
        self.assertEqual(reading.assessment.kind, "sensor_fault")

    def test_detection_failure_never_blocks_ingestion(self):
        with patch("monitoring.ai.anomaly.assess_value", side_effect=RuntimeError("boom")):
            with self.assertLogs("monitoring.ai.anomaly", level="WARNING"):
                reading = self.ingest(0.0)
        self.assertTrue(Reading.objects.filter(pk=reading.pk, quality=Reading.Quality.GOOD).exists())

    def test_history_is_per_sensor_and_metric(self):
        make_readings("beach-a", "temperature", steady(20.0, count=12), start=START - timedelta(days=1))
        reading = self.ingest(21.0, metric="temperature", unit="°C")
        self.assertFalse(ReadingAssessment.objects.filter(reading=reading).exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AssessReadingsCommandTests(TestCase):
    def setUp(self):
        values = steady(12.0, count=12) + [0.0] + steady(12.0, count=3)
        make_readings("beach-b", "turbidity", values)

    def run_command(self, *args):
        out = io.StringIO()
        call_command("assess_readings", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_reports_but_saves_nothing(self):
        output = self.run_command("--dry-run")
        self.assertIn("sensor_fault/zero", output)
        self.assertFalse(ReadingAssessment.objects.exists())

    def test_backfill_saves_assessments_and_is_repeatable(self):
        self.run_command()
        self.run_command("--sensor", "beach-b")
        self.assertEqual(ReadingAssessment.objects.count(), 1)
        self.assertEqual(Reading.objects.filter(quality=Reading.Quality.SUSPECT).count(), 1)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AssessmentApiTests(TestCase):
    def setUp(self):
        make_readings("beach-c", "turbidity", steady(12.0, count=12) + [0.0, 14.5])
        call_command("assess_readings", stdout=io.StringIO())

    def test_lists_assessments_publicly_with_labels(self):
        response = self.client.get(reverse("ai-assessments"))
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual({r["reason"] for r in results}, {"zero", "outlier"})
        newest = results[0]
        self.assertEqual(newest["kind_label"], "Statistisk avvikelse")
        self.assertEqual(newest["metric_label"], "Turbiditet")

    def test_limit_and_sensor_filter(self):
        self.assertEqual(len(self.client.get(reverse("ai-assessments"), {"limit": 1}).json()["results"]), 1)
        self.assertEqual(self.client.get(reverse("ai-assessments"), {"limit": "abc"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("ai-assessments"), {"sensor_id": "other"}).json()["results"], [])

    def test_labels_follow_the_request_language(self):
        response = self.client.get(reverse("ai-assessments"), headers={"accept-language": "en"})
        self.assertIn("Statistical deviation", {r["kind_label"] for r in response.json()["results"]})
