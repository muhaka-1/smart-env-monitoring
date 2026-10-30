"""Fyller databasen med historiska demomätvärden så att dashboarden har något att visa i diagrammet.

Läser sensor/data/sample_readings.json, flyttar tidsstämplarna så att den senaste mätningen hamnar på
"nu" och kan upprepa serien bakåt i tiden (--repeat). Simulatorn och dess "aktuell tidsstämpel"-regel
påverkas inte; detta är bara testdata. Regler för ogiltiga värden: docs/data-rules.md.
"""
import json
import math
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as dj_timezone

from monitoring import services
from monitoring.models import Reading

DEFAULT_FILE = Path(settings.BASE_DIR).parent / "sensor" / "data" / "sample_readings.json"
SUSPECT_TURBIDITY = 1000.0
TEMP_RANGE = (-5.0, 50.0)
DEFAULT_STEP = timedelta(minutes=15)


def _slug(name) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") if isinstance(name, str) else ""


def _number(rec, key):
    try:
        v = float(rec[key])
    except (KeyError, TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def load_series(path: Path):
    """Returnerar (rader, antal_avvisade). Rad = (sensor_id, metric, enhet, tid (naiv UTC), värde)."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CommandError(f"Kan inte läsa {path}: {exc}")
    if not isinstance(raw, list):
        raise CommandError(f"{path} måste innehålla en JSON-lista")

    rows, skipped = [], 0
    for rec in raw:
        slug, ts = _slug(rec.get("beach_name")), _timestamp(rec.get("measurement_timestamp"))
        if not slug or ts is None:
            skipped += 1
            continue
        turb, temp = _number(rec, "turbidity"), _number(rec, "water_temperature")
        if turb is not None and turb >= 0:
            rows.append((f"{slug}-turbidity", "turbidity", "NTU", ts, turb))
        else:
            skipped += 1
        if temp is not None and TEMP_RANGE[0] <= temp <= TEMP_RANGE[1]:
            rows.append((f"{slug}-temperature", "temperature", "°C", ts, temp))
        else:
            skipped += 1
    return rows, skipped


def build_readings(rows, now, repeat=1, seed=42):
    """Skapar Reading-objekt (osparade). Serien flyttas så att senaste mätningen = now."""
    rng = random.Random(seed)
    times = sorted({r[3] for r in rows})
    ts_max, span = times[-1], times[-1] - times[0]
    gaps = [b - a for a, b in zip(times, times[1:]) if b > a]
    step = min(gaps) if gaps else DEFAULT_STEP

    readings = []
    for k in range(repeat):
        shift = k * (span + step)
        for sensor_id, metric, unit, ts, value in rows:
            if k > 0:  # upprepade perioder varieras något så att diagrammet inte ser kopierat ut
                value = value * (1 + rng.uniform(-0.15, 0.15)) if metric == "turbidity" else value + rng.uniform(-1.5, 1.5)
                value = round(max(value, 0.0), 2)
            when = now + (ts - ts_max) - shift
            quality = Reading.Quality.SUSPECT if (metric == "turbidity" and value > SUSPECT_TURBIDITY) else Reading.Quality.GOOD
            readings.append(Reading(sensor_id=sensor_id, metric=metric, timestamp=when, value=value, unit=unit,
                                    quality=quality, status=services.evaluate_status(value, metric)))
    return readings


class Command(BaseCommand):
    help = "Fyller databasen med historiska demomätvärden (för dashboard-diagrammet)."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(DEFAULT_FILE), help="JSON-fil med mätvärden (standard: simulatorns reservfil)")
        parser.add_argument("--repeat", type=int, default=1, help="Antal gånger serien upprepas bakåt i tiden (1 = ca 20 h)")
        parser.add_argument("--clear", action="store_true", help="Avvisas för att skydda befintliga mätningar")
        parser.add_argument("--seed", type=int, default=42, help="Slumpfrö för variation i upprepade perioder")

    def handle(self, *args, **opts):
        if opts["clear"]:
            raise CommandError("--clear är inte tillåtet: befintliga mätningar kan vara verkliga data.")
        if opts["repeat"] < 1:
            raise CommandError("--repeat måste vara minst 1")
        rows, skipped = load_series(opts["file"])
        if not rows:
            raise CommandError("Inga giltiga mätvärden hittades i filen")

        now = dj_timezone.now().replace(microsecond=0)
        readings = build_readings(rows, now.replace(tzinfo=None), opts["repeat"], opts["seed"])
        for r in readings:
            r.timestamp = r.timestamp.replace(tzinfo=timezone.utc)
        sensor_ids = sorted({r.sensor_id for r in readings})

        before = Reading.objects.count()
        Reading.objects.bulk_create(readings, batch_size=1000, ignore_conflicts=True)  # dubbletter hoppas över
        created = Reading.objects.count() - before

        first, last = min(r.timestamp for r in readings), max(r.timestamp for r in readings)
        self.stdout.write(self.style.SUCCESS(
            f"Skapade {created} mätningar för {len(sensor_ids)} sensorer ({first:%Y-%m-%d %H:%M} - {last:%Y-%m-%d %H:%M} UTC)."))
        if skipped:
            self.stdout.write(self.style.WARNING(f"{skipped} ogiltiga värden/rader hoppades över."))
