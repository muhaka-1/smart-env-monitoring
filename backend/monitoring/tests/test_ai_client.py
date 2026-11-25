import logging
from unittest.mock import patch

import requests
from django.test import SimpleTestCase, override_settings

from monitoring.ai import client, config

from .ai_helpers import clean_state, http_error, ollama_response, raw_response

SCHEMA = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}


@override_settings(AI_ENABLED="1")
class OllamaClientTests(SimpleTestCase):
    def setUp(self):
        clean_state()
        self.addCleanup(clean_state)

    def test_defaults_are_off_and_local(self):
        with override_settings(AI_ENABLED=None, OLLAMA_URL=None, OLLAMA_MODEL=None), patch.dict("os.environ", {}, clear=True):
            self.assertFalse(config.enabled())
            self.assertEqual(config.base_url(), "http://127.0.0.1:11434")
            self.assertEqual(config.model(), "llama3.2:3b")

    @override_settings(AI_ENABLED="0")
    def test_disabled_never_calls_the_network(self):
        with patch("monitoring.ai.client.requests.post") as post:
            with self.assertRaises(client.AIUnavailable):
                client.chat_json("s", "u", SCHEMA)
        post.assert_not_called()

    @override_settings(OLLAMA_URL="http://ollama.test:11434/", OLLAMA_MODEL="mistral:7b", AI_TIMEOUT="12")
    def test_request_uses_chat_api_schema_and_settings(self):
        with patch("monitoring.ai.client.requests.post", return_value=ollama_response({"summary": "Hej"})) as post:
            result = client.chat_json("system text", "user text", SCHEMA)
        self.assertEqual(result, {"summary": "Hej"})
        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://ollama.test:11434/api/chat")
        body = kwargs["json"]
        self.assertEqual(body["model"], "mistral:7b")
        self.assertIs(body["stream"], False)
        self.assertEqual(body["format"], SCHEMA)
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user"])
        self.assertEqual(kwargs["timeout"], 12)
        self.assertIs(kwargs["allow_redirects"], False)

    def test_unsafe_urls_fall_back_to_the_local_default(self):
        for url in ("ftp://host", "http://user:pw@host:11434", "http://host?x=1", "not a url", ""):
            with self.subTest(url=url), override_settings(OLLAMA_URL=url):
                self.assertEqual(config.base_url(), "http://127.0.0.1:11434")

    def test_failures_become_ai_unavailable(self):
        cases = {
            "anslutning": {"side_effect": requests.ConnectionError("refused")},
            "os-fel": {"side_effect": OSError("socket")},
            "timeout": {"side_effect": requests.Timeout("slow")},
            "http-fel": {"return_value": http_error()},
            "ingen json": {"return_value": raw_response("detta är inte json")},
            "fel typ": {"return_value": raw_response("[1, 2]")},
            "saknar message": {"return_value": ollama_response({"x": 1})},
        }
        for name, mock_args in cases.items():
            with self.subTest(name), override_settings(AI_COOLDOWN_SECONDS="0"):
                if name == "saknar message":
                    mock_args["return_value"].json.return_value = {"error": "model not found"}
                with patch("monitoring.ai.client.requests.post", **mock_args):
                    with self.assertRaises(client.AIUnavailable):
                        client.chat_json("s", "u", SCHEMA)

    @override_settings(AI_COOLDOWN_SECONDS="60")
    def test_cooldown_after_a_failure_skips_further_calls(self):
        with patch("monitoring.ai.client.requests.post", side_effect=requests.ConnectionError()) as post:
            with self.assertRaises(client.AIUnavailable):
                client.chat_json("s", "u", SCHEMA)
            self.assertFalse(client.available())
            with self.assertRaises(client.AIUnavailable):
                client.chat_json("s", "u", SCHEMA)
        self.assertEqual(post.call_count, 1)
        client.reset_cooldown()
        self.assertTrue(client.available())

    @override_settings(AI_COOLDOWN_SECONDS="0")
    def test_zero_cooldown_retries_immediately(self):
        with patch("monitoring.ai.client.requests.post", side_effect=requests.ConnectionError()) as post:
            for _ in range(2):
                with self.assertRaises(client.AIUnavailable):
                    client.chat_json("s", "u", SCHEMA)
        self.assertEqual(post.call_count, 2)

    def test_logs_never_contain_prompt_or_response(self):
        secret = "hemlig-prompt-123"
        with patch("monitoring.ai.client.requests.post", side_effect=requests.ConnectionError(secret)):
            with self.assertLogs("monitoring.ai.client", level=logging.WARNING) as logs:
                with self.assertRaises(client.AIUnavailable):
                    client.chat_json("s", secret, SCHEMA)
        self.assertNotIn(secret, "\n".join(logs.output))

    @override_settings(AI_ENABLED="0")
    def test_standalone_mode_ignores_switch_and_cooldown(self):
        with patch("monitoring.ai.client.requests.post", return_value=ollama_response({"summary": "ok"})) as post:
            result = client.chat_json("s", "u", SCHEMA, model="gemma2:2b", standalone=True)
        self.assertEqual(result["summary"], "ok")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "gemma2:2b")
        with patch("monitoring.ai.client.requests.post", side_effect=requests.ConnectionError()):
            with self.assertRaises(client.AIUnavailable):
                client.chat_json("s", "u", SCHEMA, standalone=True)
        with override_settings(AI_ENABLED="1"):
            self.assertTrue(client.available())   # standalone-fel startar ingen paus

    def test_invalid_numbers_in_settings_use_defaults(self):
        with override_settings(AI_TIMEOUT="abc", AI_MAIL_TIMEOUT="-5", AI_COOLDOWN_SECONDS="x"):
            self.assertEqual(config.timeout(), 30)
            self.assertEqual(config.mail_timeout(), 1)
            self.assertEqual(config.cooldown_seconds(), 60)
