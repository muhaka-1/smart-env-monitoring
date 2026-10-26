"""Läser och normaliserar mätdata från det öppna datasetet (med lokal reservfil)."""
import json
import logging
import re
from dataclasses import dataclass

import requests

from .config import Config

log = logging.getLogger(__name__)
UNIT = "NTU"
SUSPECT_ABOVE = 1000.0  # orimligt högt turbiditetsvärde -> misstänkt kvalitet


@dataclass(frozen=True)
class Measurement:
    sensor_id: str
    value: float
    quality: str
    unit: str = UNIT


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def normalize(raw_records: list[dict]) -> list[Measurement]:
    """Filtrerar bort ogiltiga rader och sorterar kronologiskt."""
    valid = []
    for rec in raw_records:
        beach, ts = rec.get("beach_name"), rec.get("measurement_timestamp", "")
        try:
            value = float(rec["turbidity"])
        except (KeyError, TypeError, ValueError):
            continue
        if not beach or value < 0 or value != value:  # saknas / negativt / NaN
            continue
        valid.append((ts, Measurement(f"{slugify(beach)}-turbidity", value,
                                      "suspect" if value > SUSPECT_ABOVE else "good")))
    valid.sort(key=lambda t: t[0])
    return [m for _, m in valid]


def fetch_remote(cfg: Config) -> list[dict]:
    resp = requests.get(cfg.dataset_url, timeout=cfg.request_timeout * 3)
    resp.raise_for_status()
    return resp.json()


def load_sample(cfg: Config) -> list[dict]:
    return json.loads(cfg.sample_path.read_text(encoding="utf-8"))


def load_measurements(cfg: Config, offline: bool = False) -> list[Measurement]:
    raw: list[dict] = []
    if not offline:
        try:
            raw = fetch_remote(cfg)
            log.info("Hämtade %d rader från öppna datasetet", len(raw))
        except (requests.RequestException, ValueError) as exc:
            log.warning("Kunde inte hämta dataset (%s) - använder lokal reservfil", exc)
    measurements = normalize(raw)
    if not measurements:
        measurements = normalize(load_sample(cfg))
        log.info("Använder %d rader från %s", len(measurements), cfg.sample_path.name)
    return measurements
