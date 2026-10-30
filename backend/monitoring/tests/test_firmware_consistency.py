"""Håller firmwarens larmgränser lika med backendens (backend avgör status, firmware larmar lokalt)."""
import os
import re
import unittest
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

KCONFIG = Path(__file__).resolve().parents[3] / "firmware" / "main" / "Kconfig.projbuild"


def kconfig_default(symbol: str) -> float:
    text = KCONFIG.read_text(encoding="utf-8")
    block = re.search(rf"config {symbol}\n((?:[ \t]+.*\n)+)", text)
    assert block, f"{symbol} saknas i Kconfig.projbuild"
    default = re.search(r"default\s+(-?\d+(?:\.\d+)?)", block.group(1))
    assert default, f"{symbol} saknar default"
    return float(default.group(1))


@unittest.skipUnless(KCONFIG.exists(), "firmware/ saknas i checkouten")
@unittest.skipIf(
    any(k in os.environ for k in ("ANOMALY_THRESHOLD", "ANOMALY_THRESHOLD_TURBIDITY", "ANOMALY_THRESHOLD_TEMPERATURE", "BEACH_LIMIT_TURBIDITY_NTU", "BEACH_LIMIT_WATER_TEMP_C")),
    "gränsvärden är överstyrda via miljövariabler",
)
class FirmwareThresholdSyncTests(SimpleTestCase):
    def test_turbidity_limit_matches_backend(self):
        self.assertEqual(kconfig_default("BEACH_LIMIT_TURBIDITY_NTU"), settings.ANOMALY_THRESHOLDS["turbidity"],
                         "Firmwarens och backendens turbiditetsgräns skiljer sig åt")

    def test_temperature_limit_matches_backend(self):
        self.assertEqual(kconfig_default("BEACH_LIMIT_WATER_TEMP_C"), settings.ANOMALY_THRESHOLDS["temperature"],
                         "Firmwarens och backendens temperaturgräns skiljer sig åt")
