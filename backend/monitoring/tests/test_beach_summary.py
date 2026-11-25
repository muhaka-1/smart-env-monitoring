from datetime import timedelta
from unittest.mock import patch

from django.db.models import F
from django.test import TestCase, override_settings
from django.utils import timezone

from monitoring.ai import config, facts, summary
from monitoring.ai.grounding import numeric_statements, response_schema
from monitoring.models import Reading

from .ai_helpers import clean_state, make_readings, ollama_response


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   AI_ENABLED="1", AI_COOLDOWN_SECONDS="0", READING_STALE_SECONDS=300,
                   ANOMALY_THRESHOLDS={"temperature": 25, "turbidity": 30})
class BeachSummaryTests(TestCase):
    def setUp(self):
        clean_state()
        self.addCleanup(clean_state)
        for beach in ("ohio-street-beach", "63rd-street-beach", "rainbow-beach"):
            for metric, values in (("temperature", [20, 20, 20, 22]), ("turbidity", [40, 40, 40, 34])):
                make_readings(beach + "-" + metric, metric, values,
                              start=timezone.now() - timedelta(minutes=3))
        Reading.objects.filter(metric="turbidity").update(status="ANOMALY")

    def answer(self, url, **kwargs):
        text = kwargs["json"]["format"]["properties"]["summary"]["enum"][0]
        return ollama_response({"summary": text})

    def assert_all_beaches(self, text):
        blocks = text.split("\n\n")[1:]
        self.assertEqual(len(blocks), 3)
        for block in blocks:
            self.assertIn("22.0 °C", block)
            self.assertIn("34.0 NTU", block)
            self.assertIn("25.0", block)
            self.assertIn("30.0", block)
            self.assertIn("Status: OK", block)
        for name in ("Ohio Street Beach", "63rd Street Beach", "Rainbow Beach"):
            self.assertTrue(any(block.startswith(name + ": ") for block in blocks))

    def test_model_candidates_cannot_omit_beaches_metrics_status_or_trends(self):
        payload = facts.latest_facts()
        for text in response_schema("summary", payload, "sv", summary.MAX_LENGTH)["properties"]["summary"]["enum"]:
            self.assert_all_beaches(text)
            self.assertIn("Trend: Högre", text)
            self.assertIn("Trend: Lägre", text)
            self.assertTrue(facts.numbers_are_grounded(text, payload))

    def test_live_summary_uses_complete_verified_blocks_in_three_languages(self):
        with patch("monitoring.ai.client.requests.post", side_effect=self.answer):
            for language, trend in (("sv", "Högre"), ("en", "Higher"), ("de", "Höher")):
                with self.subTest(language=language):
                    result = summary.get_summary(language)
                    self.assertEqual(result["source"], "ai")
                    self.assert_all_beaches(result["text"])
                    self.assertIn(trend, result["text"])

    def test_partial_or_changed_status_and_trend_are_rejected(self):
        payload = facts.latest_facts()
        correct = response_schema("summary", payload, "sv", summary.MAX_LENGTH)["properties"]["summary"]["enum"][0]
        answers = (numeric_statements(payload, "sv")[0], correct.split("\n\n")[1],
                   correct.replace("Avvikelse", "OK"), correct.replace("Högre", "Lägre"))
        for text in answers:
            with self.subTest(text=text), patch("monitoring.ai.client.requests.post", return_value=ollama_response({"summary": text})):
                result = summary.get_summary("sv")
                self.assertEqual(result["source"], "fallback")
                self.assert_all_beaches(result["text"])

    @override_settings(AI_ENABLED="0")
    def test_disabled_uses_all_beaches_without_network(self):
        with patch("monitoring.ai.client.requests.post") as post:
            result = summary.get_summary("sv")
        post.assert_not_called()
        self.assertEqual(result["source"], "fallback")
        self.assert_all_beaches(result["text"])

    def test_unknown_trend_is_explicit_for_insufficient_history(self):
        Reading.objects.filter(timestamp__lt=timezone.now() - timedelta(minutes=1)).delete()
        self.assertIn("Otillräckligt underlag", summary.fallback_text(facts.latest_facts(), "sv"))

    @override_settings(ANOMALY_THRESHOLDS={"temperature": 25})
    def test_missing_threshold_is_explicit_without_omitting_metric(self):
        result = summary.get_summary("sv")
        self.assert_all_beaches_with_missing_limit(result["text"])

    def assert_all_beaches_with_missing_limit(self, text):
        self.assertEqual(text.count("gräns saknas"), 3)
        self.assertEqual(text.count("34.0 NTU"), 3)

    def test_stale_readings_do_not_describe_a_current_trend(self):
        Reading.objects.update(timestamp=F("timestamp") - timedelta(hours=1))
        with patch("monitoring.ai.client.requests.post") as post:
            result = summary.get_summary("sv")
        post.assert_not_called()
        self.assertEqual(result["source"], "fallback")
        self.assertEqual(result["text"].count("inaktuell"), 6)
        self.assertNotIn("Trend:", result["text"])

    @override_settings(AI_SUMMARY_CACHE_SECONDS="3600")
    def test_cache_is_limited_to_five_minutes(self):
        self.assertEqual(config.summary_cache_seconds(), 300)
        with patch("monitoring.ai.client.requests.post", side_effect=self.answer), patch("monitoring.ai.summary.cache.set", wraps=summary.cache.set) as cache_set:
            summary.get_summary("sv")
        summary_writes = [call for call in cache_set.call_args_list if call.args[0].startswith("ai-summary:v4:")]
        self.assertEqual(len(summary_writes), 1)
        self.assertLessEqual(summary_writes[0].kwargs["timeout"], 300)

    def test_oversized_input_returns_complete_fallback_without_network(self):
        with patch("monitoring.ai.summary.MAX_LENGTH", 10), patch("monitoring.ai.client.requests.post") as post:
            result = summary.get_summary("sv")
        post.assert_not_called()
        self.assertEqual(result["source"], "fallback")
        self.assert_all_beaches(result["text"])
