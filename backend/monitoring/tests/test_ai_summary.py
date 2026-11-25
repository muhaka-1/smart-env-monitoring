import json
from datetime import timedelta

from django.utils import timezone
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from monitoring.ai import facts, summary
from monitoring.models import Reading
from monitoring.ai.grounding import numeric_statements

from .ai_helpers import clean_state, make_readings, ollama_response, raw_response, steady

SETTINGS = dict(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                ANOMALY_THRESHOLDS={"turbidity": 30, "temperature": 25}, AI_COOLDOWN_SECONDS="0")


class GroundingTests(SimpleTestCase):
    FACTS = {"sensor_points": 2, "items": [{"sensor": "beach-7", "value": 19.4, "threshold": 25.0, "metric": "temperature", "unit": "°C"}]}

    def test_numbers_from_the_facts_and_their_rounding_are_allowed(self):
        for text in numeric_statements(self.FACTS, "sv"):
            self.assertTrue(facts.numbers_are_grounded(text, self.FACTS), text)

    def test_invented_numbers_are_rejected(self):
        for text in ("Värdet är 99,9.", "Temperaturen steg med 3 grader.", "Gränsen är 30."):
            self.assertFalse(facts.numbers_are_grounded(text, self.FACTS), text)

    def test_text_without_numbers_is_fine(self):
        self.assertTrue(facts.numbers_are_grounded("Läget är lugnt.", self.FACTS))

    def test_bathing_advice_is_detected_in_three_languages(self):
        for text in ("Det är säkert att bada.", "It is safe to swim here.", "Es ist sicher zu baden.", "Du kan bada nu."):
            self.assertTrue(facts.contains_bathing_advice(text), text)
        self.assertFalse(facts.contains_bathing_advice("Badvattenkvalitet följs upp enligt projektets gräns."))


@override_settings(**SETTINGS)
class SummaryTests(TestCase):
    def setUp(self):
        clean_state()
        self.addCleanup(clean_state)
        make_readings("beach-temp", "temperature", steady(20.0, count=10) + [26.3], unit="°C", start=timezone.now() - timedelta(minutes=10))
        make_readings("beach-turb", "turbidity", steady(8.0, count=10), start=timezone.now() - timedelta(minutes=10))
        Reading.objects.filter(value=26.3).update(status=Reading.Status.ANOMALY)

    def good(self, text="beach-temp (temperatur) 26.3 °C, gräns 25.0."):
        return ollama_response({"summary": text})

    def test_disabled_returns_a_plain_text_from_the_data(self):
        with patch("monitoring.ai.client.requests.post") as post:
            data = summary.get_summary("sv")
        post.assert_not_called()
        self.assertEqual(data["source"], "fallback")
        self.assertIn("2 mätpunkter har ett senaste mätvärde.", data["text"])
        self.assertIn("beach-temp (temperatur) 26.3 °C, gräns 25.0.", data["text"])

    def test_fallback_is_translated_and_uses_plural_forms(self):
        self.assertIn("2 measuring points have a latest reading.", summary.get_summary("en")["text"])
        self.assertIn("2 Messpunkte haben einen neuesten Messwert.", summary.get_summary("de")["text"])

    def test_empty_database_says_so(self):
        Reading.objects.all().delete()
        self.assertEqual(summary.get_summary("sv")["text"], "Inga mätvärden ännu.")

    @override_settings(AI_ENABLED="1")
    def test_verified_ai_text_is_used_and_cached(self):
        with patch("monitoring.ai.client.requests.post", return_value=self.good()) as post:
            first = summary.get_summary("sv")
            second = summary.get_summary("sv")
        self.assertEqual(first["source"], "ai")
        self.assertEqual(first["model"], "llama3.2:3b")
        self.assertEqual(second, first)
        self.assertEqual(post.call_count, 1)

    @override_settings(AI_ENABLED="1", AI_SUMMARY_CACHE_SECONDS="0")
    def test_zero_cache_time_asks_the_model_every_time(self):
        with patch("monitoring.ai.client.requests.post", return_value=self.good()) as post:
            summary.get_summary("sv")
            summary.get_summary("sv")
        self.assertEqual(post.call_count, 2)

    @override_settings(AI_ENABLED="1")
    def test_untrusted_answers_fall_back_to_plain_text(self):
        answers = {
            "påhittat tal": self.good("Temperaturen är 31,5 °C."),
            "badråd": self.good("Det är säkert att bada."),
            "tom": self.good("   "),
            "för lång": self.good("a" * 800),
            "ingen json": raw_response("hej"),
            "fel fält": ollama_response({"annat": "x"}),
        }
        for name, answer in answers.items():
            with self.subTest(name), patch("monitoring.ai.client.requests.post", return_value=answer):
                cache.clear()
                data = summary.get_summary("sv")
                self.assertEqual(data["source"], "fallback")
                self.assertIn("mätpunkter", data["text"])

    @override_settings(AI_ENABLED="1")
    def test_prompt_contains_language_and_facts_but_no_personal_data(self):
        with patch("monitoring.ai.client.requests.post", return_value=self.good()) as post:
            summary.get_summary("en")
        messages = post.call_args.kwargs["json"]["messages"]
        self.assertIn("English", messages[0]["content"])
        payload = json.loads(messages[1]["content"].split("\n", 1)[1])
        self.assertEqual(payload["sensor_points"], 2)
        self.assertEqual(payload["over_threshold"], 1)
        self.assertEqual({i["sensor"] for i in payload["items"]}, {"beach-temp", "beach-turb"})

    @override_settings(AI_ENABLED="1")
    def test_concurrent_generation_is_not_started_twice(self):
        signature = summary.hashlib.sha256(json.dumps(facts.latest_facts(), sort_keys=True).encode()).hexdigest()
        cache.set(f"ai-summary:v3:sv:{signature}:lock", 1, 30)
        with patch("monitoring.ai.client.requests.post") as post:
            data = summary.get_summary("sv")
        post.assert_not_called()
        self.assertEqual(data["source"], "fallback")

    @override_settings(AI_ENABLED="1", AI_SUMMARY_CACHE_SECONDS="0")
    def test_expired_ai_text_is_not_served_when_model_is_unavailable(self):
        with patch("monitoring.ai.client.requests.post", return_value=self.good()):
            fresh = summary.get_summary("sv")
        with patch("monitoring.ai.client.requests.post", return_value=raw_response("fel")):
            again = summary.get_summary("sv")
        self.assertEqual(again["source"], "fallback")
        self.assertNotEqual(again["text"], fresh["text"])

    def test_trend_labels(self):
        self.assertEqual(facts.trend([10, 10, 10, 10], 14, "turbidity"), "rising")
        self.assertEqual(facts.trend([10, 10, 10, 10], 6, "turbidity"), "falling")
        self.assertEqual(facts.trend([10, 10, 10, 10], 10.1, "turbidity"), "steady")
        self.assertEqual(facts.trend([10], 14, "turbidity"), "unknown")


@override_settings(**SETTINGS)
class SummaryApiAndDashboardTests(TestCase):
    def setUp(self):
        clean_state()
        make_readings("beach-temp", "temperature", steady(20.0, count=10), unit="°C", start=timezone.now() - timedelta(minutes=10))

    def test_summary_endpoint_is_public_and_labels_the_source(self):
        response = self.client.get(reverse("ai-summary"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source"], "fallback")
        self.assertFalse(body["ai_enabled"])
        self.assertIsNone(body["model"])
        self.assertIn("mätpunkt", body["text"])

    @override_settings(AI_ENABLED="1")
    def test_summary_endpoint_marks_ai_text(self):
        answer = ollama_response({"summary": numeric_statements(facts.latest_facts(), "sv")[0]})
        with patch("monitoring.ai.client.requests.post", return_value=answer):
            body = self.client.get(reverse("ai-summary")).json()
        self.assertEqual((body["source"], body["ai_enabled"], body["model"]), ("ai", True, "llama3.2:3b"))

    def test_summary_follows_the_request_language(self):
        body = self.client.get(reverse("ai-summary"), headers={"accept-language": "en"}).json()
        self.assertIn("measuring point", body["text"])

    def test_dashboard_has_the_panel_with_ai_labelling_for_everyone(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, 'id="ai-status"')
        self.assertContains(response, "Läget just nu")
        self.assertContains(response, 'data-label-ai="AI-genererad"')
        self.assertContains(response, "monitoring/ai_status.js")

    def test_dashboard_panel_is_translated(self):
        response = self.client.get(reverse("dashboard"), headers={"accept-language": "en"})
        self.assertContains(response, "Current situation")
        self.assertContains(response, 'data-label-ai="AI-generated"')
        de = self.client.get(reverse("dashboard"), headers={"accept-language": "de"})
        self.assertContains(de, "Aktuelle Lage")
        self.assertContains(de, "Datenqualität")
