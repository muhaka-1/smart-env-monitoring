"""Trusted numeric statements shared by summaries and mail explanations."""
import re

from django.utils.translation import gettext as _, ngettext, override


def numeric_statements(facts, language):
    with override(language):
        items = facts.get("items", [facts] if "sensor" in facts else [])
        statements = []
        if "sensor_points" in facts:
            count = facts["sensor_points"]
            statements.append(ngettext(
                "%(n)d mätpunkt har ett senaste mätvärde.",
                "%(n)d mätpunkter har ett senaste mätvärde.", count) % {"n": count})
        for item in items:
            if item.get("threshold") is None:
                continue
            metric = {"temperature": _("Temperatur"), "turbidity": _("Turbiditet")}.get(item["metric"], item["metric"])
            statements.append(_("%(sensor)s (%(metric)s) %(value)s %(unit)s, gräns %(threshold)s.") % {
                "sensor": item["sensor"], "metric": metric.lower(),
                "value": f"{item['value']:.1f}", "unit": item["unit"],
                "threshold": f"{item['threshold']:.1f}",
            })
        return statements


def numeric_text_is_grounded(text, facts):
    # Free prose cannot reliably bind a number to a sensor or distinguish a
    # reading from a threshold. Numeric responses use complete trusted clauses.
    if not re.search(r"\d", text):
        return True
    allowed = set()
    for language in ("sv", "en", "de"):
        allowed.update(numeric_statements(facts, language))
    remaining = text.strip()
    while remaining:
        matches = [line for line in allowed if remaining.startswith(line)]
        if not matches:
            return False
        remaining = remaining[len(max(matches, key=len)):].lstrip()
    return True
