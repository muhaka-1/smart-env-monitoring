import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

SETTINGS = Path(__file__).resolve().parents[2] / "config" / "settings.py"


class ThresholdConfigurationTests(SimpleTestCase):
    def test_legacy_environment_variables_are_supported(self):
        with patch.dict(os.environ, {"BEACH_LIMIT_TURBIDITY_NTU": "41", "BEACH_LIMIT_WATER_TEMP_C": "19"}, clear=True):
            thresholds = runpy.run_path(str(SETTINGS))["ANOMALY_THRESHOLDS"]
        self.assertEqual(thresholds, {"turbidity": 41, "temperature": 19})

    def test_new_environment_variables_take_precedence(self):
        env = {"BEACH_LIMIT_TURBIDITY_NTU": "41", "BEACH_LIMIT_WATER_TEMP_C": "19",
               "ANOMALY_THRESHOLD_TURBIDITY": "33", "ANOMALY_THRESHOLD_TEMPERATURE": "26"}
        with patch.dict(os.environ, env, clear=True):
            thresholds = runpy.run_path(str(SETTINGS))["ANOMALY_THRESHOLDS"]
        self.assertEqual(thresholds, {"turbidity": 33, "temperature": 26})
