from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from monitoring.ai import client, facts, summary
from monitoring.ai.grounding import numeric_statements, response_schema, selected_text

from .ai_helpers import ollama_response


@override_settings(AI_ENABLED="1")
class OutputContractTests(SimpleTestCase):
    FACTS = {"sensor_points": 2, "items": [
        {"sensor": "ohio-temperature", "metric": "temperature", "value": -2.0,
         "threshold": 25.0, "unit": "°C", "status": "OK", "trend": "steady", "data_quality": None},
        {"sensor": "rainbow-turbidity", "metric": "turbidity", "value": 41.7,
         "threshold": 30.0, "unit": "NTU", "status": "ANOMALY", "trend": "rising", "data_quality": "deviation"},
    ]}

    def test_schema_constrains_each_candidate_to_grounded_numeric_text(self):
        for language in ("sv", "en", "de"):
            schema = response_schema("summary", self.FACTS, language, 700)
            options = schema["properties"]["summary"]["enum"]
            self.assertFalse(schema["additionalProperties"])
            self.assertTrue(options)
            for text in options:
                with self.subTest(language=language, text=text):
                    self.assertTrue(facts.numbers_are_grounded(text, self.FACTS))
                    self.assertLessEqual(len(text), 700)
                    self.assertEqual(selected_text({"summary": text}, "summary", schema), text)

    def test_prompt_and_format_share_the_same_language_specific_enum(self):
        for language in ("sv", "en", "de"):
            option = numeric_statements(self.FACTS, language)[-1]
            with patch("monitoring.ai.client.requests.post", return_value=ollama_response({"summary": option})) as post:
                self.assertEqual(summary.generate(self.FACTS, language), option)
            request = post.call_args.kwargs["json"]
            self.assertIn(option, request["format"]["properties"]["summary"]["enum"])
            self.assertIn(option, request["messages"][0]["content"])

    def test_server_revalidates_even_if_ollama_ignores_schema(self):
        schema = response_schema("summary", self.FACTS, "en", 700)
        correct = numeric_statements(self.FACTS, "en")[-1]
        for result in (
            {"summary": correct.replace("41.7", "30.0").replace("30.0.", "41.7.")},
            {"summary": correct.replace("rainbow", "ohio")},
            {"summary": correct.replace("NTU", "°C")},
            {"summary": "Everything is safe."},
            {"summary": ""}, {"summary": None}, {"summary": []}, {},
            {"summary": correct, "extra": "untrusted"},
        ):
            with self.subTest(result=result):
                self.assertIsNone(selected_text(result, "summary", schema))
                with patch("monitoring.ai.client.requests.post", return_value=ollama_response(result)):
                    with self.assertRaises(client.AIUnavailable):
                        summary.generate(self.FACTS, "en")

    def test_wrong_language_and_sign_changes_are_not_accepted(self):
        schema = response_schema("summary", self.FACTS, "en", 700)
        swedish = numeric_statements(self.FACTS, "sv")[-1]
        self.assertIsNone(selected_text({"summary": swedish}, "summary", schema))
        negative = numeric_statements(self.FACTS, "en")[1]
        self.assertIsNone(selected_text({"summary": negative.replace("-2.0", "2.0")}, "summary", schema))

    def test_explanation_schema_contains_only_its_own_alert(self):
        alert = self.FACTS["items"][1]
        schema = response_schema("explanation", alert, "de", 400)
        self.assertEqual(schema["properties"]["explanation"]["enum"], numeric_statements(alert, "de"))
        self.assertNotIn("ohio", str(schema))

    def test_length_limit_is_enforced_before_generation(self):
        with self.assertRaises(ValueError):
            response_schema("summary", self.FACTS, "sv", 1)
