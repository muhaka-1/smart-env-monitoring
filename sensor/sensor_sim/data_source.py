"""Läser och normaliserar mätdata från det öppna datasetet (med lokal reservfil).

Regler för saknade/felaktiga värden: se docs/data-rules.md.
"""
import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from .config import Config

log = logging.getLogger(__name__)
SUSPECT_TURBIDITY = 1000.0  # orimligt högt turbiditetsvärde -> misstänkt kvalitet (skickas ändå)
TEMP_RANGE = (-5.0, 50.0)   # fysiskt rimligt intervall för vattentemperatur (°C)


@dataclass(frozen=True)
class Measurement:
    sensor_id: str
    metric: str  # "turbidity" | "temperature"
    value: float
    quality: str
    unit: str


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_timestamp(value) -> datetime | None:
    """Tolkar ISO 8601 (med eller utan Z/tidszon). Returnerar naiv UTC-tid, eller None om ogiltig."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _number(rec: dict, key: str):
    """Returnerar float, eller None om värdet saknas, inte är ett tal, NaN eller oändligt."""
    try:
        v = float(rec[key])
    except (KeyError, TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def normalize(raw_records: list[dict], skipped: Counter | None = None) -> list[Measurement]:
    """Plockar ut turbiditet och temperatur, filtrerar ogiltigt och sorterar kronologiskt.

    Avvisade värden räknas per orsak i `skipped` (t.ex. "turbidity:invalid").
    """
    skipped = skipped if skipped is not None else Counter()
    found = []
    for rec in raw_records:
        beach = rec.get("beach_name")
        slug = slugify(beach) if isinstance(beach, str) else ""
        if not slug:
            skipped["row:beach_name"] += 1
            continue
        ts = parse_timestamp(rec.get("measurement_timestamp"))
        if ts is None:
            skipped["row:timestamp"] += 1
            continue

        turb = _number(rec, "turbidity")
        if turb is None:
            skipped["turbidity:invalid"] += 1
        elif turb < 0:
            skipped["turbidity:negative"] += 1
        else:
            quality = "suspect" if turb > SUSPECT_TURBIDITY else "good"
            found.append((ts, 0, Measurement(f"{slug}-turbidity", "turbidity", turb, quality, "NTU")))

        temp = _number(rec, "water_temperature")
        if temp is None:
            skipped["temperature:invalid"] += 1
        elif not TEMP_RANGE[0] <= temp <= TEMP_RANGE[1]:
            skipped["temperature:out_of_range"] += 1
        else:
            found.append((ts, 1, Measurement(f"{slug}-temperature", "temperature", temp, "good", "°C")))

    found.sort(key=lambda t: (t[0], t[1]))
    return [m for _, _, m in found]


def fetch_remote(cfg: Config) -> list[dict]:
    resp = requests.get(cfg.dataset_url, timeout=cfg.request_timeout * 3)
    resp.raise_for_status()
    return resp.json()


def load_sample(cfg: Config) -> list[dict]:
    return json.loads(cfg.sample_path.read_text(encoding="utf-8"))


def _normalize_logged(raw: list[dict], source: str) -> list[Measurement]:
    skipped: Counter = Counter()
    measurements = normalize(raw, skipped)
    if skipped:
        log.warning("%s: %d värden/rader avvisades %s", source, sum(skipped.values()), dict(skipped))
    return measurements


def load_measurements(cfg: Config, offline: bool = False) -> list[Measurement]:
    raw: list[dict] = []
    if not offline:
        try:
            raw = fetch_remote(cfg)
            log.info("Hämtade %d rader från öppna datasetet", len(raw))
        except (requests.RequestException, ValueError) as exc:
            log.warning("Kunde inte hämta dataset (%s) - använder lokal reservfil", exc)
    measurements = _normalize_logged(raw, "Datasetet") if raw else []
    if not measurements:
        measurements = _normalize_logged(load_sample(cfg), cfg.sample_path.name)
        log.info("Använder %d mätvärden från %s", len(measurements), cfg.sample_path.name)
    return measurements
