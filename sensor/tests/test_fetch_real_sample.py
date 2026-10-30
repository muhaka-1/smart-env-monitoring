import unittest

from tools.fetch_real_sample import beach_rows, markdown_table, rejected_summary, usable_rows, usable_turbidity_per_beach


def rec(beach="Oak Street Beach", i=0, turb="3.2", temp="18.5"):
    return {"beach_name": beach, "measurement_timestamp": f"2026-07-01T{i % 24:02d}:00:00.000",
            "turbidity": turb, "water_temperature": temp, "measurement_id": f"{beach[:3]}{i}"}


class FetchRealSampleTests(unittest.TestCase):
    def setUp(self):
        self.raw = [rec(i=i) for i in range(30)] + [rec(i=40, turb="-1"), rec(i=41, turb="abc"), rec(beach="Rainbow Beach", i=1)]

    def test_counts_only_usable_rows_per_beach(self):
        per = usable_turbidity_per_beach(self.raw)
        self.assertEqual(per["Oak Street Beach"], 30)
        self.assertEqual(per["Rainbow Beach"], 1)

    def test_usable_rows_limit_and_filter(self):
        rows = beach_rows(self.raw, "Oak Street Beach")
        self.assertEqual(len(usable_rows(rows, 25)), 25)
        self.assertTrue(all(float(r["turbidity"]) >= 0 for r in usable_rows(rows, 100)))
        self.assertEqual(len(usable_rows(rows, 100)), 30)

    def test_rejected_summary_counts_reasons(self):
        skipped = rejected_summary(beach_rows(self.raw, "Oak Street Beach"))
        self.assertEqual(skipped["turbidity:negative"], 1)
        self.assertEqual(skipped["turbidity:invalid"], 1)

    def test_markdown_table_has_header_and_rows(self):
        table = markdown_table(self.raw[:3]).splitlines()
        self.assertEqual(len(table), 5)
        self.assertIn("turbidity (NTU)", table[0])
