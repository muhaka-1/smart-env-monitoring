"""Complete, verified status blocks grouped by the sensor's beach."""
from collections import defaultdict

from django.utils.translation import gettext as _, override

BEACH_NAMES = {
    "ohio-street-beach": "Ohio Street Beach",
    "63rd-street-beach": "63rd Street Beach",
    "rainbow-beach": "Rainbow Beach",
}


def beach_blocks(items, statements, language):
    with override(language):
        statuses = {"OK": "OK", "ANOMALY": _("Avvikelse")}
        trends = {
            "rising": _("Högre än tidigare medelvärde"),
            "falling": _("Lägre än tidigare medelvärde"),
            "steady": _("Ungefär oförändrat"),
            "unknown": _("Otillräckligt underlag"),
        }
        groups = defaultdict(list)
        for item, statement in zip(items, statements, strict=True):
            sensor = item["sensor"]
            suffix = "-" + item["metric"]
            slug = sensor.removesuffix(suffix)
            beach = BEACH_NAMES.get(slug, slug)
            status = statuses.get(item.get("status"), _("Okänd status"))
            if item.get("stale", False):
                detail = _("Senaste status: %(status)s. Mätningen är inaktuell eller saknar giltig tid.") % {"status": status}
            else:
                detail = _("Status: %(status)s. Trend: %(trend)s.") % {
                    "status": status, "trend": trends.get(item.get("trend"), trends["unknown"])}
                if item.get("data_quality") == "sensor_fault":
                    detail += " " + _("Misstänkt sensorfel") + "."
            groups[beach].append(statement + " " + detail)
        return [beach + ": " + " ".join(lines) for beach, lines in sorted(groups.items())]
