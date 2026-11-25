from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from monitoring.ai import client, facts, summary
from monitoring.ai.explain import explain_alert
from monitoring.ai.grounding import numeric_statements
from monitoring.models import Alert, Reading, ReadingAssessment

from .ai_helpers import clean_state, ollama_response


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", AI_ENABLED="1",
                   READING_STALE_SECONDS=300, AI_COOLDOWN_SECONDS="0")
class ReviewRegressionsTests(TestCase):
    def setUp(self):
        clean_state()
        self.addCleanup(clean_state)
        self.reading = Reading.objects.create(
            sensor_id="beach-63-temperature", metric="temperature", timestamp=timezone.now(),
            value=-2, unit="°C", status="OK",
        )
        self.assessment = ReadingAssessment.objects.create(
            reading=self.reading, kind="sensor_fault", reason="jump", score=15,
        )

    def test_assessment_history_requires_login_for_get_and_head(self):
        for method in (self.client.get, self.client.head):
            with self.subTest(method=method):
                response = method(reverse("ai-assessments"))
                self.assertEqual(response.status_code, 403)
                self.assertNotIn(self.reading.sensor_id.encode(), response.content)
        user = get_user_model().objects.create_user("review-reader")
        self.client.force_login(user)
        response = self.client.get(reverse("ai-assessments"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["reading_id"], self.reading.pk)
        self.assertIn("no-store", response["Cache-Control"])

    def test_public_dashboard_does_not_fetch_protected_assessments(self):
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, "data-assessments-url")
        self.assertNotContains(response, 'id="ai-quality-list"')
        self.assertContains(response, 'id="ai-status"')

    def test_cached_summary_is_invalidated_by_new_reading(self):
        with patch("monitoring.ai.client.requests.post", return_value=ollama_response({"summary": "1 mätpunkt har ett senaste mätvärde."})) as post:
            first = summary.get_summary("sv")
            self.assertEqual(summary.get_summary("sv"), first)
            self.assertEqual(post.call_count, 1)
            Reading.objects.create(sensor_id=self.reading.sensor_id, metric="temperature",
                                   timestamp=timezone.now(), value=28, unit="°C", status="ANOMALY")
            summary.get_summary("sv")
            self.assertEqual(post.call_count, 2)

    def test_old_readings_never_produce_current_ai_summary(self):
        self.reading.timestamp = timezone.now() - timedelta(minutes=6)
        self.reading.save(update_fields=["timestamp"])
        with patch("monitoring.ai.client.requests.post") as post:
            data = summary.get_summary("sv")
        post.assert_not_called()
        self.assertEqual(data["source"], "fallback")
        self.assertIn("inaktuell", data["text"])
        self.assertNotIn("Inget mätvärde överskrider", data["text"])

    def test_lock_and_cooldown_cannot_return_expired_summary(self):
        with patch("monitoring.ai.client.requests.post", return_value=ollama_response({"summary": "1 mätpunkt har ett senaste mätvärde."})):
            summary.get_summary("sv")
        with override_settings(AI_SUMMARY_CACHE_SECONDS=0), patch("monitoring.ai.client.available", return_value=False):
            self.assertEqual(summary.get_summary("sv")["source"], "fallback")

    def test_facts_include_observation_time_and_freshness(self):
        item = facts.latest_facts()["items"][0]
        self.assertEqual(item["timestamp"], self.reading.timestamp.isoformat())
        self.assertFalse(item["stale"])

    def test_numeric_text_preserves_sensor_metric_sign_value_and_threshold(self):
        payload = facts.latest_facts()
        for language in ("sv", "en", "de"):
            good = numeric_statements(payload, language)[-1]
            self.assertTrue(facts.numbers_are_grounded(good, payload))
            for bad in (
                good.replace("-2.0", "2.0"),
                good.replace("-2.0", "25.0").replace("25.0.", "-2.0."),
                good.replace("beach-63", "beach-64"),
                good.replace("°C", "NTU"),
                good.replace("-2.0", "-2.04"),
                "Inte " + good,
            ):
                with self.subTest(language=language, text=bad):
                    self.assertFalse(facts.numbers_are_grounded(bad, payload))

    def test_swapped_numbers_rejected_in_summary_and_mail(self):
        bad = "beach-63-temperature (temperatur) 25.0 °C, gräns -2.0."
        with patch("monitoring.ai.client.requests.post", return_value=ollama_response({"summary": bad})):
            with self.assertRaises(client.AIUnavailable):
                summary.generate(facts.latest_facts(), "sv")
        alert = Alert.objects.create(reading=self.reading, sensor_id=self.reading.sensor_id,
            metric="temperature", timestamp=self.reading.timestamp, value=-2, unit="°C", threshold=25, status="ANOMALY")
        with patch("monitoring.ai.client.requests.post", return_value=ollama_response({"explanation": bad})):
            self.assertIsNone(explain_alert(alert, "sv"))

    def test_reading_expiring_during_generation_returns_stale_fallback(self):
        def answer(*args, **kwargs):
            Reading.objects.filter(pk=self.reading.pk).update(timestamp=timezone.now() - timedelta(minutes=6))
            return ollama_response({"summary": "1 mätpunkt har ett senaste mätvärde."})
        with patch("monitoring.ai.client.requests.post", side_effect=answer):
            result = summary.get_summary("sv")
        self.assertEqual(result["source"], "fallback")
        self.assertIn("inaktuell", result["text"])

    def test_values_cannot_be_reassigned_between_sensors_or_metrics(self):
        payload = {"items": [
            {"sensor": "ohio", "metric": "temperature", "value": 19.4, "threshold": 25, "unit": "°C"},
            {"sensor": "rainbow", "metric": "turbidity", "value": 41.7, "threshold": 30, "unit": "NTU"},
        ]}
        good = numeric_statements(payload, "en")[0]
        for bad in (good.replace("ohio", "rainbow"), good.replace("19.4", "41.7"),
                    good.replace("temperature", "turbidity"), good.replace("25.0", "30.0")):
            with self.subTest(text=bad):
                self.assertFalse(facts.numbers_are_grounded(bad, payload))

    def test_readings_are_rechecked_after_model_failure(self):
        def fail(*args, **kwargs):
            Reading.objects.filter(pk=self.reading.pk).update(timestamp=timezone.now() - timedelta(minutes=6))
            raise client.AIUnavailable("offline")
        with patch("monitoring.ai.summary.generate", side_effect=fail):
            result = summary.get_summary("sv")
        self.assertEqual(result["source"], "fallback")
        self.assertIn("inaktuell", result["text"])
