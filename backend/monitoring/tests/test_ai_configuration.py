import math
from unittest.mock import patch

import requests
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from monitoring.ai import client, config
from monitoring.models import Reading

from .ai_helpers import clean_state, ollama_response


class NumericConfigurationTests(SimpleTestCase):
    def test_nonfinite_numbers_use_finite_defaults(self):
        options = (
            ("AI_TIMEOUT", config.timeout, 30),
            ("AI_MAIL_TIMEOUT", config.mail_timeout, 8),
            ("AI_COOLDOWN_SECONDS", config.cooldown_seconds, 60),
            ("AI_SUMMARY_CACHE_SECONDS", config.summary_cache_seconds, 300),
        )
        for name, read, expected in options:
            for value in ("nan", "NaN", "inf", "Infinity", "-inf", "1e999"):
                with self.subTest(name=name, value=value), override_settings(**{name: value}):
                    result = read()
                    self.assertTrue(math.isfinite(result))
                    self.assertEqual(result, expected)

    @override_settings(AI_ENABLED="1", AI_TIMEOUT="inf")
    def test_request_receives_the_finite_default_timeout(self):
        clean_state()
        self.addCleanup(clean_state)
        with patch("monitoring.ai.client.requests.post", return_value=ollama_response({"summary": "ok"})) as post:
            client.chat_json("system", "facts", {})
        self.assertEqual(post.call_args.kwargs["timeout"], 30)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   AI_ENABLED="1", AI_TIMEOUT="nan", AI_COOLDOWN_SECONDS="inf")
class FailureFallbackTests(TestCase):
    def setUp(self):
        clean_state()
        self.addCleanup(clean_state)
        Reading.objects.create(sensor_id="ohio-street-beach-temperature", metric="temperature",
                               value=22.5, unit="°C", timestamp=timezone.now(), status="OK")

    def test_timeout_with_invalid_numeric_settings_still_returns_public_fallback(self):
        with patch("monitoring.ai.client.requests.post", side_effect=requests.Timeout("private-request-marker")) as post:
            with self.assertLogs("monitoring.ai.client", level="WARNING") as logs:
                response = self.client.get(reverse("ai-summary"))
            second = self.client.get(reverse("ai-summary"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(response.json()["source"], "fallback")
        self.assertIsNone(response.json()["model"])
        self.assertIn("22.5 °C", response.json()["text"])
        self.assertEqual(second.json()["source"], "fallback")
        self.assertEqual(post.call_count, 1)
        self.assertNotIn("private-request-marker", "\n".join(logs.output))
