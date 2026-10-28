import json
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from monitoring.models import Reading


def make_file(records):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(records, f)
    f.close()
    return f.name


def rec(beach="Oak Street Beach", ts="2025-07-01T10:00:00.000", turb="5", temp="20"):
    return {"beach_name": beach, "measurement_timestamp": ts, "turbidity": turb, "water_temperature": temp}


def seed(path, **kw):
    out = StringIO()
    call_command("seed_demo_data", file=path, stdout=out, **kw)
    return out.getvalue()


class SeedDemoDataTests(TestCase):
    def test_creates_both_metrics_and_ends_at_now(self):
        path = make_file([rec(ts="2025-07-01T10:00:00.000"), rec(ts="2025-07-01T10:15:00.000", turb="40", temp="26")])
        seed(path)
        self.assertEqual(Reading.objects.count(), 4)
        self.assertEqual(set(Reading.objects.values_list("sensor_id", flat=True)),
                         {"oak-street-beach-turbidity", "oak-street-beach-temperature"})
        latest = Reading.objects.order_by("-timestamp").first()
        self.assertLess(abs(timezone.now() - latest.timestamp), timedelta(seconds=10))
        first = Reading.objects.order_by("timestamp").first()
        self.assertEqual(latest.timestamp - first.timestamp, timedelta(minutes=15))   # relativa avstånd bevaras

    def test_status_and_units(self):
        seed(make_file([rec(turb="40", temp="26")]))
        t = Reading.objects.get(metric="turbidity")
        w = Reading.objects.get(metric="temperature")
        self.assertEqual((t.unit, t.status), ("NTU", "ANOMALY"))
        self.assertEqual((w.unit, w.status), ("°C", "ANOMALY"))

    def test_invalid_rows_skipped(self):
        bad = [rec(turb="Infinity"), rec(beach="!!!"), rec(ts="nej"), rec(turb="-1", temp="500")]
        out = seed(make_file(bad + [rec()]))
        self.assertEqual(Reading.objects.count(), 2)   # bara den giltiga raden
        self.assertIn("hoppades över", out)

    def test_repeat_extends_history_backwards_with_variation(self):
        path = make_file([rec(ts="2025-07-01T10:00:00.000"), rec(ts="2025-07-01T10:15:00.000")])
        seed(path, repeat=3)
        self.assertEqual(Reading.objects.filter(metric="turbidity").count(), 6)
        stamps = list(Reading.objects.filter(metric="turbidity").values_list("timestamp", flat=True))
        self.assertEqual(len(set(stamps)), 6)                                     # inga dubbletter
        values = set(Reading.objects.filter(metric="turbidity").values_list("value", flat=True))
        self.assertGreater(len(values), 2)                                        # upprepningar är varierade
        self.assertTrue(all(v >= 0 for v in values))

    def test_clear_makes_rerun_idempotent(self):
        path = make_file([rec(), rec(ts="2025-07-01T10:15:00.000")])
        seed(path)
        seed(path, clear=True)
        self.assertEqual(Reading.objects.count(), 4)

    def test_without_clear_old_data_is_kept(self):
        path = make_file([rec()])
        seed(path)
        Reading.objects.update(timestamp=timezone.now() - timedelta(days=1))   # simulera att tiden gått
        seed(path)
        self.assertEqual(Reading.objects.count(), 4)

    def test_errors(self):
        with self.assertRaises(CommandError):
            seed("/finns/inte.json")
        with self.assertRaises(CommandError):
            seed(make_file({"inte": "en lista"}))
        with self.assertRaises(CommandError):
            seed(make_file([rec(turb="x", temp="y")]))
        with self.assertRaises(CommandError):
            seed(make_file([rec()]), repeat=0)

    def test_default_sample_file_loads(self):
        out = StringIO()
        call_command("seed_demo_data", repeat=7, stdout=out)
        self.assertEqual(Reading.objects.values("sensor_id").distinct().count(), 6)
        self.assertEqual(Reading.objects.count(), 240 * 2 * 7)
        self.assertNotIn("hoppades över", out.getvalue())
