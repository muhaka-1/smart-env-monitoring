from datetime import timedelta
from types import SimpleNamespace

from django.test import TestCase

from monitoring.ai.explain import alert_facts
from monitoring.ai.grounding import numeric_statements, numeric_text_is_grounded, response_schema, selected_text

from .ai_helpers import START, make_readings


class AlertTrendTests(TestCase):
    def alert(self, value=34):
        return SimpleNamespace(sensor_id="ohio-turbidity", metric="turbidity", value=value,
                               unit="NTU", threshold=30, timestamp=START + timedelta(hours=3), reading=None)

    def test_window_includes_start_and_excludes_current_future_and_other_streams(self):
        make_readings("ohio-turbidity", "turbidity", [29, 29, 29], start=START)
        for start in (START - timedelta(seconds=1), START + timedelta(hours=3)):
            make_readings("ohio-turbidity", "turbidity", [999], start=start)
        make_readings("rainbow-turbidity", "turbidity", [999] * 3)
        make_readings("ohio-turbidity", "temperature", [50] * 3, start=START + timedelta(seconds=30))
        result = alert_facts(self.alert())
        self.assertEqual(result["trend_sample_count"], 3)
        self.assertEqual(result["trend"], "rising")

    def test_insufficient_recent_history_does_not_reuse_older_readings(self):
        make_readings("ohio-turbidity", "turbidity", [29] * 8, start=START - timedelta(hours=1))
        for count in (0, 1, 2):
            if count:
                make_readings("ohio-turbidity", "turbidity", [29], start=START + timedelta(minutes=count))
            with self.subTest(count=count):
                self.assertEqual(alert_facts(self.alert())["trend"], "unknown")

    def test_all_recent_readings_contribute_to_baseline(self):
        make_readings("ohio-turbidity", "turbidity", [10] * 6 + [40] * 6)
        self.assertEqual(alert_facts(self.alert())["trend"], "rising")

    def test_directions_use_existing_tolerance(self):
        make_readings("ohio-turbidity", "turbidity", [40] * 3)
        for value, expected in ((34, "falling"), (40, "steady"), (46, "rising")):
            with self.subTest(value=value):
                self.assertEqual(alert_facts(self.alert(value))["trend"], expected)

    def test_translated_explanations_bind_measurement_and_recent_trend(self):
        make_readings("ohio-turbidity", "turbidity", [29] * 3)
        facts = alert_facts(self.alert())
        for language, phrase in (("sv", "senaste 3 timmarna"), ("en", "last 3 hours"), ("de", "letzten 3 Stunden")):
            with self.subTest(language=language):
                schema = response_schema("explanation", facts, language, 400)
                text = numeric_statements(facts, language)[0]
                self.assertIn(phrase, text)
                self.assertTrue(numeric_text_is_grounded(text, facts))
                for bad in (text.replace("34.0", "43.0"), text.replace("3 ", "6 "), text.split(". ")[0] + "."):
                    self.assertIsNone(selected_text({"explanation": bad}, "explanation", schema))

    def test_unknown_history_is_explicit_in_all_languages(self):
        facts = alert_facts(self.alert())
        for language, phrase in (("sv", "För få"), ("en", "Too few"), ("de", "Zu wenige")):
            self.assertIn(phrase, numeric_statements(facts, language)[0])
