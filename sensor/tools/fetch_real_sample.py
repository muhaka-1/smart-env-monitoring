"""Hämtar riktiga rader från datasetet (Chicago Park District, Socrata qmqz-2xku) och tar fram underlag
för issue #3: val av strand, minst 20 användbara rader, kolumnmappning och antal avvisade värden.

Körs från mappen sensor/:
    python -m tools.fetch_real_sample                          # visar antal användbara rader per strand
    python -m tools.fetch_real_sample --beach "Ohio Street Beach" --rows 25
"""
import argparse
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

from sensor_sim.config import Config
from sensor_sim.data_source import fetch_remote, normalize, slugify


def fetch(limit: int, beach: str | None = None) -> list[dict]:
    cfg = replace(Config(), rows_per_beach=limit)
    if beach:
        cfg = replace(cfg, beaches=(beach,))
    return fetch_remote(cfg)


def usable_turbidity_per_beach(raw: list[dict]) -> Counter:
    """Antal användbara turbiditetsvärden per strand (enligt reglerna i docs/data-rules.md)."""
    per = Counter()
    for rec in raw:
        if any(m.metric == "turbidity" for m in normalize([rec])):
            per[rec.get("beach_name")] += 1
    return per


def beach_rows(raw: list[dict], beach: str) -> list[dict]:
    return [r for r in raw if r.get("beach_name") == beach]


def usable_rows(rows: list[dict], n: int) -> list[dict]:
    out = [r for r in rows if any(m.metric == "turbidity" for m in normalize([r]))]
    return out[:n]


def rejected_summary(rows: list[dict]) -> Counter:
    skipped: Counter = Counter()
    normalize(rows, skipped)
    return skipped


def markdown_table(rows: list[dict]) -> str:
    lines = ["| measurement_timestamp | turbidity (NTU) | water_temperature (°C) | measurement_id |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r.get('measurement_timestamp', '')} | {r.get('turbidity', '')} | "
                     f"{r.get('water_temperature', '')} | {r.get('measurement_id', '')} |")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--beach", help='Strandnamn exakt som i datasetet, t.ex. "Ohio Street Beach"')
    p.add_argument("--rows", type=int, default=25, help="antal användbara rader att visa/spara")
    p.add_argument("--out", help="sökväg för JSON-fil med de sparade raderna")
    args = p.parse_args()

    if args.rows < 1:
        p.error("--rows måste vara minst 1")
    raw = fetch(args.rows, args.beach)
    print(f"Hämtade {len(raw)} giltiga rader. Tidsspann: "
          f"{min(r['measurement_timestamp'] for r in raw)} - "
          f"{max(r['measurement_timestamp'] for r in raw)}\n")

    if not args.beach:
        print("Användbara turbiditetsvärden per strand (välj stranden med flest):")
        for beach, n in usable_turbidity_per_beach(raw).most_common():
            print(f"  {n:5d}  {beach}")
        return

    rows = beach_rows(raw, args.beach)
    good = usable_rows(rows, args.rows)
    skipped = rejected_summary(rows)
    print(f"Strand: {args.beach}  (sensor_id: {slugify(args.beach)}-turbidity)")
    print(f"Hämtade rader för stranden: {len(rows)}, användbara visas: {len(good)}, "
          f"avvisade värden: {dict(skipped) or 'inga'}\n")
    print(markdown_table(good))
    if len(good) < 20:
        print(f"\nVARNING: bara {len(good)} användbara rader. Välj en annan strand eller justera --rows.")
    out = Path(args.out or f"data/real_sample_{slugify(args.beach)}.json")
    out.write_text(json.dumps(good, indent=1), encoding="utf-8")
    print(f"\nSparade {len(good)} rader i {out}")


if __name__ == "__main__":
    main()
