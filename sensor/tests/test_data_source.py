import json
import unittest
from collections import Counter

from sensor_sim.config import Config
from sensor_sim.data_source import normalize, parse_timestamp, slugify


def rec(beach="A Beach", ts="2025-07-01T10:00:00.000", **values):
    return {"beach_name": beach, "measurement_timestamp": ts, **values}


class NormalizeTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("63rd Street Beach"), "63rd-street-beach")

    def test_sorted_chronologically_and_ids(self):
        raw = [rec(ts="2025-07-01T11:00:00.000", turbidity="5"), rec(ts="2025-07-01T10:00:00.000", turbidity="3")]
        result = normalize(raw)
        self.assertEqual([m.value for m in result], [3.0, 5.0])
        self.assertEqual(result[0].sensor_id, "a-beach-turbidity")

    def test_missing_nonnumeric_negative_rejected(self):
        skipped = Counter()
        raw = [rec(turbidity="-1"), rec(), rec(turbidity="abc"), rec(turbidity=None)]
        self.assertEqual(normalize(raw, skipped), [])
        self.assertEqual(skipped["turbidity:negative"], 1)
        self.assertEqual(skipped["turbidity:invalid"], 3)

    def test_nan_and_infinity_rejected(self):
        for bad in ("NaN", "Infinity", "-Infinity", "inf", float("inf"), float("nan")):
            with self.subTest(bad=bad):
                self.assertEqual(normalize([rec(turbidity=bad)]), [])
                self.assertEqual(normalize([rec(water_temperature=bad)]), [])

    def test_empty_or_unusable_beach_name_rejected(self):
        skipped = Counter()
        raw = [rec(beach="", turbidity="1"), rec(beach="!!!", turbidity="1"), rec(beach=None, turbidity="1"),
               rec(beach=123, turbidity="1")]
        self.assertEqual(normalize(raw, skipped), [])
        self.assertEqual(skipped["row:beach_name"], 4)

    def test_invalid_or_missing_timestamp_rejected(self):
        skipped = Counter()
        raw = [rec(ts="inte-ett-datum", turbidity="3"), rec(ts="", turbidity="3"), rec(ts=None, turbidity="3")]
        self.assertEqual(normalize(raw, skipped), [])
        self.assertEqual(skipped["row:timestamp"], 3)

    def test_timestamp_formats(self):
        self.assertIsNotNone(parse_timestamp("2025-07-01T10:00:00.000"))
        self.assertIsNotNone(parse_timestamp("2025-07-01T10:00:00Z"))
        self.assertIsNotNone(parse_timestamp("2025-07-01T10:00:00+02:00"))
        self.assertEqual(parse_timestamp("2025-07-01T12:00:00+02:00"), parse_timestamp("2025-07-01T10:00:00Z"))
        self.assertIsNone(parse_timestamp("2025-13-45"))

    def test_suspect_quality(self):
        m = normalize([rec(turbidity="5000")])[0]
        self.assertEqual((m.quality, m.value), ("suspect", 5000.0))

    def test_temperature_extracted_with_unit(self):
        result = normalize([rec(turbidity="3", water_temperature="18.5")])
        self.assertEqual([(m.metric, m.unit, m.value) for m in result],
                         [("turbidity", "NTU", 3.0), ("temperature", "°C", 18.5)])
        self.assertEqual(result[1].sensor_id, "a-beach-temperature")

    def test_implausible_temperature_dropped_but_turbidity_kept(self):
        skipped = Counter()
        result = normalize([rec(turbidity="3", water_temperature="120")], skipped)
        self.assertEqual([m.metric for m in result], ["turbidity"])
        self.assertEqual(skipped["temperature:out_of_range"], 1)


class SampleFileTests(unittest.TestCase):
    def test_fallback_file_is_valid_json_array_and_all_rows_valid(self):
        cfg = Config()
        raw = json.loads(cfg.sample_path.read_text(encoding="utf-8"))
        self.assertIsInstance(raw, list)
        skipped = Counter()
        measurements = normalize(raw, skipped)
        self.assertEqual(dict(skipped), {})                    # inga avvisade rader
        self.assertEqual(len(measurements), len(raw) * 2)      # turbiditet + temperatur per rad
        self.assertGreaterEqual(len(raw), 20)
        self.assertEqual({m.sensor_id for m in measurements},
                         {"ohio-street-beach-turbidity", "ohio-street-beach-temperature"})
