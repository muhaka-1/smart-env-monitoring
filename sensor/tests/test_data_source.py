import unittest

from sensor_sim.data_source import normalize, slugify


class NormalizeTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("63rd Street Beach"), "63rd-street-beach")

    def test_filters_invalid_and_sorts(self):
        raw = [
            {"beach_name": "A Beach", "measurement_timestamp": "2", "turbidity": "5"},
            {"beach_name": "A Beach", "measurement_timestamp": "1", "turbidity": "3"},
            {"beach_name": "A Beach", "measurement_timestamp": "3", "turbidity": "-1"},
            {"beach_name": "A Beach", "measurement_timestamp": "4"},
            {"beach_name": "", "measurement_timestamp": "5", "turbidity": "1"},
            {"beach_name": "A Beach", "measurement_timestamp": "6", "turbidity": "abc"},
        ]
        result = normalize(raw)
        self.assertEqual([m.value for m in result], [3.0, 5.0])
        self.assertEqual(result[0].sensor_id, "a-beach-turbidity")

    def test_suspect_quality(self):
        m = normalize([{"beach_name": "X", "measurement_timestamp": "1", "turbidity": "5000"}])[0]
        self.assertEqual(m.quality, "suspect")
