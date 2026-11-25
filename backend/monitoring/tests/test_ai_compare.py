import io
import tempfile
from pathlib import Path
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from monitoring.management.commands.ai_compare_models import SCENARIOS, language_ok
from monitoring.ai import facts

from .ai_helpers import clean_state, ollama_response


def fake_ollama(url, json=None, **kwargs):
    model = json["model"]
    if model == "bra-modell":
        return ollama_response({"summary": json["format"]["properties"]["summary"]["enum"][0]})
    if model == "dålig-modell":
        return ollama_response({"summary": "Värdet är 99 NTU. Det är säkert att bada."})
    raise requests.ConnectionError("model not found")


@override_settings(AI_ENABLED="0")
class CompareModelsTests(SimpleTestCase):
    def setUp(self):
        clean_state()

    def run_command(self, *args):
        out = io.StringIO()
        with patch("monitoring.ai.client.requests.post", side_effect=fake_ollama) as post:
            call_command("ai_compare_models", *args, stdout=out)
        return out.getvalue(), post

    def test_scenarios_are_in_the_shape_of_the_real_facts(self):
        for scenario in SCENARIOS.values():
            self.assertEqual(set(scenario), {"sensor_points", "over_threshold", "suspected_sensor_faults", "items"})
            self.assertEqual(scenario["sensor_points"], len(scenario["items"]))
            self.assertTrue(facts.numbers_are_grounded("2 mätpunkter har ett senaste mätvärde.", scenario))

    def test_compares_models_and_runs_even_when_ai_is_switched_off(self):
        output, post = self.run_command("--models", "bra-modell,dålig-modell,saknas", "--no-warmup")
        self.assertEqual(post.call_count, 9)               # 3 modeller x 3 scenarier
        self.assertIn("| bra-modell | alla_ok |", output)
        good_rows = [line for line in output.splitlines() if line.startswith("| bra-modell | ")]
        self.assertTrue(all("✘" not in line for line in good_rows))
        bad = [line for line in output.splitlines() if line.startswith("| dålig-modell | ")][0]
        self.assertEqual(bad.count("✘"), 2)                 # ogrundat tal och badråd
        self.assertIn("(fel:", [line for line in output.splitlines() if line.startswith("| saknas | ")][0])
        self.assertIn("| bra-modell |", output.split("## Sammanfattning per modell")[1])
        self.assertIn("3/3", output)

    def test_warmup_is_an_extra_unmeasured_call_per_model(self):
        _, post = self.run_command("--models", "bra-modell")
        self.assertEqual(post.call_count, 4)

    def test_output_file_is_written(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "jamforelse.md"
            self.run_command("--models", "bra-modell", "--no-warmup", "--output", str(target))
            self.assertIn("# Modelljämförelse (sv)", target.read_text(encoding="utf-8"))

    def test_empty_model_list_is_an_error(self):
        with self.assertRaises(CommandError):
            call_command("ai_compare_models", "--models", " , ")

    def test_language_check(self):
        self.assertTrue(language_ok("Läget är lugnt och värdet är inte högt.", "sv"))
        self.assertFalse(language_ok("The situation is calm and the reading is low.", "sv"))
        self.assertTrue(language_ok("The reading is not above the limit.", "en"))
