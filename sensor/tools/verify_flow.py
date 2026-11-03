"""Verifierar hela kedjan: simulator -> HTTP -> Django -> databas -> REST-API (latest + history).

Använder den riktiga simulatorn (datakälla, meddelande, HTTP-publisher) mot en körande backend och
kontrollerar att varje skickad mätning kan läsas tillbaka oförändrad via /api/readings/latest/ och
/api/readings/ (historik). Används både manuellt och av backend-testet test_end_to_end.py.

Körs från mappen sensor/ med backend igång:
    python -m tools.verify_flow --base-url http://localhost:8001
"""
import argparse
import dataclasses
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

from sensor_sim.config import Config
from sensor_sim.data_source import load_measurements
from sensor_sim.publishers import HttpPublisher
from sensor_sim.simulator import Simulator

REQUIRED_FIELDS = ("sensor_id", "timestamp", "value", "unit", "quality")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


class RecordingPublisher(HttpPublisher):
    """Samma publicering som simulatorn, men minns de meddelanden som backend bekräftade."""

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.sent: list[dict] = []

    def send(self, message: dict) -> None:
        super().send(message)          # kastar vid fel, så bara bekräftade meddelanden sparas
        self.sent.append(message)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def run_flow(base_url: str, count: int = 3, offline: bool = True, interval: float = 0.2,
             api_key: str | None = None) -> list[Check]:
    base = base_url.rstrip("/")
    checks: list[Check] = []

    try:
        health = requests.get(f"{base}/api/health/", timeout=5)
    except requests.RequestException as exc:
        return [Check("Backend svarar (/api/health/)", False, f"ingen kontakt med {base}: {exc}")]
    checks.append(Check("Backend svarar (/api/health/)", health.ok, f"HTTP {health.status_code}"))
    if not health.ok:
        return checks

    cfg = dataclasses.replace(
        Config.from_env(), api_url=f"{base}/api/readings/", interval=interval, max_retries=2, retry_base_delay=0.2,
        api_key=api_key if api_key is not None else os.environ.get("INGEST_API_KEY", ""))
    publisher = RecordingPublisher(cfg)
    started = datetime.now(timezone.utc) - timedelta(seconds=1)
    sim = Simulator(load_measurements(cfg, offline=offline), publisher, cfg.interval, cfg.max_retries, cfg.retry_base_delay)
    delivered = sim.run(count=count)
    sent = publisher.sent
    checks.append(Check(f"Simulatorn skickade {count} mätningar och backend bekräftade alla (HTTP 201)",
                        delivered == count and len(sent) == count, f"{len(sent)} av {count} bekräftade"))
    if not sent:
        return checks

    missing = [(m.get("sensor_id"), f) for m in sent for f in REQUIRED_FIELDS if f not in m]
    utc = all(parse_ts(m["timestamp"]).utcoffset() == timedelta(0) for m in sent)
    checks.append(Check("Varje meddelande har sensor_id, timestamp (UTC), value, unit och quality",
                        not missing and utc, "alla fält finns" if not missing and utc else f"saknas: {missing[:3]}"))

    by_sensor: dict[str, list[dict]] = {}
    for message in sent:
        by_sensor.setdefault(message["sensor_id"], []).append(message)

    for sensor_id, messages in by_sensor.items():
        last = messages[-1]
        r = requests.get(f"{base}/api/readings/latest/", params={"sensor_id": sensor_id}, timeout=5)
        data = r.json() if r.ok else {}
        same = (r.ok and abs(data["value"] - last["value"]) < 1e-9 and data["unit"] == last["unit"]
                and data["quality"] == last["quality"] and parse_ts(data["timestamp"]) == parse_ts(last["timestamp"]))
        checks.append(Check(f"latest: {sensor_id} returnerar senast skickade mätning", same,
                            f"värde {data.get('value')} {data.get('unit')}, status {data.get('status')}" if r.ok else f"HTTP {r.status_code}"))

        r = requests.get(f"{base}/api/readings/", params={"sensor_id": sensor_id, "start": started.isoformat(), "limit": 5000}, timeout=5)
        results = r.json().get("results", []) if r.ok else []
        stamps = [parse_ts(x["timestamp"]) for x in results]
        expected = [parse_ts(m["timestamp"]) for m in messages]
        ok = r.ok and stamps == sorted(stamps) and stamps[-len(expected):] == expected
        checks.append(Check(f"history: {sensor_id} innehåller alla {len(expected)} skickade mätningar i tidsordning", ok,
                            f"{len(results)} rader i API:t"))
    return checks


def format_report(checks: list[Check]) -> str:
    lines = [f"{'PASS' if c.ok else 'FAIL'}  {c.name}" + (f"  [{c.detail}]" if c.detail else "") for c in checks]
    passed = sum(c.ok for c in checks)
    lines.append(f"\nRESULTAT: {passed}/{len(checks)} kontroller godkända")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000", help="backendens adress (standard http://localhost:8000)")
    parser.add_argument("--count", type=int, default=3, help="antal mätningar som skickas")
    parser.add_argument("--online", action="store_true", help="hämta riktiga datasetet i stället för lokal reservfil")
    args = parser.parse_args()

    checks = run_flow(args.base_url, args.count, offline=not args.online)
    print(format_report(checks))
    sys.exit(0 if all(c.ok for c in checks) else 1)


if __name__ == "__main__":
    main()
