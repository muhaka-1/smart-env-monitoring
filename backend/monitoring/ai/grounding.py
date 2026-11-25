"""Trusted numeric statements shared by summaries and mail explanations."""
import re

from django.utils.translation import gettext as _, ngettext, override

from .beach_summary import beach_blocks


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
            metric = {"temperature": _("Temperatur"), "turbidity": _("Turbiditet")}.get(item["metric"], item["metric"])
            template = (_("%(sensor)s (%(metric)s) %(value)s %(unit)s, gräns saknas.")
                        if item.get("threshold") is None else
                        _("%(sensor)s (%(metric)s) %(value)s %(unit)s, gräns %(threshold)s."))
            statement = template % {
                "sensor": item["sensor"], "metric": metric.lower(),
                "value": f"{item['value']:.1f}", "unit": item["unit"],
                "threshold": "" if item.get("threshold") is None else f"{item['threshold']:.1f}",
            }
            if "trend_window_hours" in item:
                trend_text = {
                    "rising": _("Värdet är högre än medelvärdet under de senaste %(hours)d timmarna."),
                    "falling": _("Värdet är lägre än medelvärdet under de senaste %(hours)d timmarna."),
                    "steady": _("Värdet är ungefär lika med medelvärdet under de senaste %(hours)d timmarna."),
                    "unknown": _("För få tidigare mätningar under de senaste %(hours)d timmarna för att bedöma trenden."),
                }[item["trend"]] % {"hours": item["trend_window_hours"]}
                statement += " " + _("Värdet överskrider projektets gräns.") + " " + trend_text
            statements.append(statement)
        return statements


def numeric_text_is_grounded(text, facts):
    # Free prose cannot reliably bind a number to a sensor or distinguish a
    # reading from a threshold. Numeric responses use complete trusted clauses.
    if not re.search(r"\d", text):
        return True
    allowed = set()
    for language in ("sv", "en", "de"):
        statements = numeric_statements(facts, language)
        allowed.update(statements)
        if "sensor_points" in facts:
            allowed.update(beach_blocks(facts["items"], statements[1:], language))
    remaining = text.strip()
    while remaining:
        matches = [line for line in allowed if remaining.startswith(line)]
        if not matches:
            return False
        remaining = remaining[len(max(matches, key=len)):].lstrip()
    return True


def response_schema(field, facts, language, max_length):
    """Constrain generation as well as validation to complete trusted facts."""
    statements = numeric_statements(facts, language)
    options = list(statements)
    if "sensor_points" in facts and statements:
        count, *measurements = statements
        blocks = beach_blocks(facts["items"], measurements, language)
        options = ["\n\n".join([count, *blocks])]
        if len(blocks) > 1:
            options.append("\n\n".join([count, *reversed(blocks)]))
    options = list(dict.fromkeys(text for text in options if len(text) <= max_length))
    if not options:
        raise ValueError("No trusted statements available")
    return {
        "type": "object",
        "properties": {field: {"type": "string", "enum": options, "maxLength": max_length}},
        "required": [field],
        "additionalProperties": False,
    }


def selected_text(result, field, schema):
    """Do not assume that the model/server enforced its response schema."""
    if set(result) != {field}:
        return None
    text = result[field]
    if not isinstance(text, str) or text not in schema["properties"][field]["enum"]:
        return None
    return text
