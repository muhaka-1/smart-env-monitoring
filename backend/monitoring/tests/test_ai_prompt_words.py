"""Modellen får ord på målspråket i stället för koder, och svar med råa koder avvisas."""
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from monitoring.ai import facts, summary
from monitoring.models import Reading

from .ai_helpers import clean_state, make_readings, ollama_response, steady

SETTINGS = dict(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                ANOMALY_THRESHOLDS={"turbidity": 30, "temperature": 25}, AI_COOLDOWN_SECONDS="0", AI_ENABLED="1")


@override_settings(**SETTINGS)
class PromptWordTests(TestCase):
    def setUp(self):
        clean_state()
        self.addCleanup(clean_state)
        from django.utils import timezone
        start = timezone.now() - timezone.timedelta(minutes=12)
        make_readings("beach-temp", "temperature", steady(20.0, count=10) + [26.3], unit="°C", start=start)
        make_readings("beach-turb", "turbidity", steady(8.0, count=10), start=start)
        Reading.objects.filter(value=26.3).update(status=Reading.Status.ANOMALY)

    def prompt(self, language):
        with patch("monitoring.ai.client.requests.post", return_value=ollama_response({"summary": "Lugnt."})) as post:
            summary.get_summary(language)
        messages = post.call_args.kwargs["json"]["messages"]
        return messages[0]["content"], json.loads(messages[1]["content"].split("\n", 1)[1])

    def test_status_and_trend_are_words_in_the_target_language(self):
        expected = {"sv": ("över gränsen", "inom gränsen"), "en": ("above the limit", "within the limit"),
                    "de": ("über dem Grenzwert", "innerhalb des Grenzwerts")}
        for language, (over, inside) in expected.items():
            with self.subTest(language):
                clean_state()
                _, payload = self.prompt(language)
                status = {i["sensor"]: i["status"] for i in payload["items"]}
                self.assertEqual(status, {"beach-temp": over, "beach-turb": inside})

    def test_prompt_never_contains_raw_status_or_trend_codes(self):
        system, payload = self.prompt("sv")
        text = json.dumps(payload, ensure_ascii=False)
        for code in ("ANOMALY", '"rising"', '"falling"', '"steady"', '"sensor_fault"', '"timestamp"', '"stale"'):
            self.assertNotIn(code, text)
        self.assertIn("aldrig koder", system)

    def test_only_over_limit_sentences_are_offered_for_copying(self):
        system, _ = self.prompt("sv")
        self.assertIn("beach-temp (temperatur) 26.3 °C, gräns 25.0.", system)
        self.assertNotIn("beach-turb (turbiditet)", system)
        self.assertIn("2 mätpunkter har ett senaste mätvärde.", system)

    def test_trend_and_quality_words(self):
        self.assertEqual(facts.trend_word("rising"), "stigande")
        self.assertEqual(facts.trend_word("nonsense"), "okänd trend")
        self.assertIsNone(facts.quality_word(None))
        self.assertEqual(facts.quality_word("sensor_fault"), "misstänkt sensorfel")

    def test_summaries_with_raw_codes_fall_back_to_plain_text(self):
        for text in ("Beach-temp har status ANOMALY.", "Fältet over_limit är 1."):
            with self.subTest(text=text), patch("monitoring.ai.client.requests.post",
                                                return_value=ollama_response({"summary": text})):
                clean_state()
                data = summary.get_summary("sv")
                self.assertEqual(data["source"], "fallback")
                self.assertNotIn("ANOMALY", data["text"])

    def test_words_summary_without_codes_is_accepted(self):
        text = "En mätpunkt ligger över gränsen. Övriga ligger inom gränsen."
        with patch("monitoring.ai.client.requests.post", return_value=ollama_response({"summary": text})):
            self.assertEqual(summary.get_summary("sv")["source"], "ai")

    def test_raw_code_detector(self):
        self.assertTrue(facts.contains_raw_codes("Status: ANOMALY"))
        self.assertFalse(facts.contains_raw_codes("The reading is rising and above the limit."))
