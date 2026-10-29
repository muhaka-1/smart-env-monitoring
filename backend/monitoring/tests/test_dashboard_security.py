"""Skyddsräcke för issue #43: dashboarden får inte tolka API-data som HTML."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

DASHBOARD_JS = Path(settings.BASE_DIR) / "monitoring" / "static" / "monitoring" / "dashboard.js"


class DashboardRenderingTests(SimpleTestCase):
    def test_no_html_injection_sinks(self):
        source = DASHBOARD_JS.read_text(encoding="utf-8")
        for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
            self.assertNotIn(sink, source, f"{sink} får inte användas med data från API:t")
