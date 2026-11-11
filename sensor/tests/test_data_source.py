import json
import unittest
from collections import Counter
from dataclasses import replace
from unittest.mock import MagicMock, patch

import requests

from sensor_sim.config import Config
from sensor_sim.data_source import fetch_remote, load_measurements, normalize, parse_timestamp, slugify


def rec(beach="A Beach", ts="2025-07-01T10:00:00.000", **values):
    return {"beach_name": beach, "measurement_timestamp": ts, **values}


class NormalizeTests(unittest.TestCase):
    def test_boolean_measurements_are_rejected_without_replacing_them(self):
        for key in ("turbidity", "water_temperature"):
            for value in (True, False):
                with self.subTest(key=key, value=value):
                    self.assertEqual(normalize([rec(**{key: value})]), [])
        for zero in (0, 0.0):
            self.assertEqual([m.value for m in normalize([rec(turbidity=zero, water_temperature=zero)])], [0, 0])

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
                         {slugify(b) + "-" + metric for b in cfg.beaches
                          for metric in ("turbidity", "temperature")})
        self.assertEqual(Counter(row["beach_name"] for row in raw),
                         Counter({b: cfg.rows_per_beach for b in cfg.beaches}))
        self.assertEqual(len({r["measurement_id"] for r in raw}), len(raw))


class RemoteSelectionTests(unittest.TestCase):
    @patch("sensor_sim.data_source.requests.get")
    def test_boolean_row_does_not_fill_quota_and_next_page_is_used(self, get):
        cfg = replace(Config(), beaches=("Ohio Street Beach",), rows_per_beach=1)
        bad = dict(rec(beach=cfg.beaches[0], turbidity=True, water_temperature=False), measurement_id="bad")
        good = dict(rec(beach=cfg.beaches[0], turbidity=0, water_temperature=18.2), measurement_id="real")
        get.side_effect = [MagicMock(json=lambda: [bad]), MagicMock(json=lambda: [good])]
        self.assertEqual(fetch_remote(cfg), [good])
        self.assertEqual(get.call_count, 2)

    @patch("sensor_sim.data_source.requests.get")
    def test_server_filter_and_pagination_preserve_official_values(self, get):
        cfg = replace(Config(), rows_per_beach=2)
        originals = []

        def response(url, params, timeout):
            beach = next(b for b in cfg.beaches if b in params["$where"])
            self.assertEqual(params["$order"], "measurement_timestamp DESC, measurement_id DESC")
            self.assertEqual(params["$limit"], 2)
            good = dict(rec(beach=beach, turbidity="0", water_temperature="-5"),
                        measurement_id=slugify(beach) + str(params["$offset"]))
            originals.append(good)
            bad = dict(rec(beach=beach, turbidity="-1", water_temperature=None), measurement_id="bad")
            return MagicMock(json=lambda: [bad, good] if params["$offset"] == 0 else [good])

        get.side_effect = response
        selected = fetch_remote(cfg)
        self.assertEqual(selected, originals)
        self.assertEqual(get.call_count, 6)
        self.assertEqual(Counter(r["beach_name"] for r in selected), Counter({b: 2 for b in cfg.beaches}))
        self.assertTrue(all(m.value in (0, -5) for m in normalize(selected)))

    @patch("sensor_sim.data_source.requests.get")
    def test_missing_rows_wrong_beach_and_duplicate_ids_do_not_fill_quota(self, get):
        cfg = replace(Config(), rows_per_beach=3, beaches=("Ohio Street Beach",))
        good = dict(rec(beach=cfg.beaches[0], turbidity="1", water_temperature="20"), measurement_id="real")
        wrong = dict(good, beach_name="Oak Street Beach", measurement_id="wrong")
        get.side_effect = [MagicMock(json=lambda: [good, good, wrong]), MagicMock(json=lambda: [])]
        with self.assertRaises(ValueError):
            fetch_remote(cfg)

    @patch("sensor_sim.data_source.requests.get", side_effect=requests.ConnectionError("offline"))
    def test_failure_replays_only_the_verified_fallback(self, get):
        online = load_measurements(Config())
        self.assertEqual(online, load_measurements(Config(), offline=True))
        self.assertEqual(get.call_count, 1)

    @patch("sensor_sim.data_source.requests.get")
    def test_offline_does_not_fetch_and_sensors_are_interleaved(self, get):
        items = load_measurements(Config(), offline=True)
        get.assert_not_called()
        self.assertEqual(len(items), 150)
        for index in range(0, len(items), 6):
            self.assertEqual(len({m.sensor_id for m in items[index:index + 6]}), 6)
