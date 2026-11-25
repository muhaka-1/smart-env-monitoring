from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from monitoring import services
from monitoring.models import Alert, Reading, UserLanguagePreference

from .ai_helpers import clean_state, http_error, make_readings, ollama_response, raw_response, steady

User = get_user_model()
SETTINGS = dict(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                PLATFORM_BASE_URL="https://monitor.example.test",
                ANOMALY_THRESHOLDS={"turbidity": 30, "temperature": 25}, AI_COOLDOWN_SECONDS="0")
EXPLANATION = "ohio-turbidity (turbiditet) 34.0 NTU, gräns 30.0."


@override_settings(**SETTINGS)
class AlertMailExplanationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.anna = User.objects.create_user("anna", "anna@example.test", "Test-Strand-2026!")
        cls.erik = User.objects.create_user("erik", "erik@example.test", "Test-Strand-2026!")

    def setUp(self):
        clean_state()
        self.addCleanup(clean_state)
        make_readings("ohio-turbidity", "turbidity", steady(29.0, count=10))

    def ingest(self, value=34.0):
        with self.captureOnCommitCallbacks(execute=True):
            return services.ingest_reading({"sensor_id": "ohio-turbidity", "metric": "turbidity",
                                            "timestamp": "2026-01-01T10:00:00Z", "value": value})

    def reset(self):
        """Tar bort den nya mätningen med varning och rensar cache och utkorg så att den kan matas in igen."""
        Alert.objects.all().delete()
        Reading.objects.filter(timestamp__gte="2026-01-01T10:00:00Z").delete()
        mail.outbox.clear()
        clean_state()

    def bodies(self):
        return {m.to[0]: m.body for m in mail.outbox}

    def test_disabled_mail_is_exactly_the_ordinary_alert(self):
        with patch("monitoring.ai.client.requests.post") as post:
            self.ingest(33.0)
        post.assert_not_called()
        body = self.bodies()["anna@example.test"]
        self.assertNotIn("AI-genererad", body)
        self.assertIn("Status: Avvikelse\n\nLogga in på plattformen", body)
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(AI_ENABLED="1")
    def test_verified_explanation_is_added_and_labelled(self):
        with patch("monitoring.ai.client.requests.post", return_value=ollama_response({"explanation": EXPLANATION})) as post:
            self.ingest()
        body = self.bodies()["anna@example.test"]
        self.assertIn("Förklaring (AI-genererad, kontrollera mot värdena ovan):\n" + EXPLANATION, body)
        self.assertEqual(post.call_count, 1)                  # en förklaring delas av mottagare med samma språk
        self.assertEqual(post.call_args.kwargs["timeout"], 8)  # mejlets egen, korta tidsgräns

    @override_settings(AI_ENABLED="1")
    def test_mail_is_still_sent_when_the_model_fails(self):
        for failure in (dict(side_effect=ConnectionError()), dict(return_value=http_error()), dict(return_value=raw_response("x"))):
            with self.subTest(failure=list(failure)), patch("monitoring.ai.client.requests.post", **failure):
                self.reset()
                self.ingest()
                self.assertEqual(len(mail.outbox), 2)
                self.assertNotIn("AI-genererad", mail.outbox[0].body)

    @override_settings(AI_ENABLED="1")
    def test_explanation_with_invented_numbers_or_advice_is_left_out(self):
        for text in ("Värdet är 77 NTU.", "Det är säkert att bada trots värdet 34."):
            with self.subTest(text=text), patch("monitoring.ai.client.requests.post", return_value=ollama_response({"explanation": text})):
                self.reset()
                self.ingest()
                self.assertEqual(len(mail.outbox), 2)
                self.assertNotIn(text, mail.outbox[0].body)

    @override_settings(AI_ENABLED="1")
    def test_explanation_is_written_in_each_recipients_language(self):
        UserLanguagePreference.objects.create(user=self.erik, language="de")
        with patch("monitoring.ai.client.requests.post", return_value=ollama_response({"explanation": EXPLANATION})) as post:
            self.ingest()
        prompts = [c.kwargs["json"]["messages"][0]["content"] for c in post.call_args_list]
        self.assertEqual(len(prompts), 2)
        self.assertTrue(any("svenska" in p for p in prompts) and any("Deutsch" in p for p in prompts))
        self.assertIn("Erklärung (KI-generiert", self.bodies()["erik@example.test"])

    def test_suspected_sensor_fault_adds_a_plain_note_without_ai(self):
        self.ingest(80.0)    # orimligt hopp över gränsen
        body = self.bodies()["anna@example.test"]
        self.assertIn("Obs: mätvärdet misstänks vara ett sensorfel (orimligt hopp).", body)
        self.assertNotIn("AI-genererad", body)

    def test_sensor_fault_note_is_translated(self):
        UserLanguagePreference.objects.create(user=self.anna, language="en")
        self.ingest(80.0)
        self.assertIn("Note: the reading is suspected to be a sensor fault (implausible jump).", self.bodies()["anna@example.test"])

    def test_extra_content_failure_does_not_stop_the_mail(self):
        with patch("monitoring.notifications.explain.explain_alert", side_effect=RuntimeError("boom")):
            with self.assertLogs("monitoring.notifications", level="WARNING"):
                self.ingest()
        self.assertEqual(len(mail.outbox), 2)
