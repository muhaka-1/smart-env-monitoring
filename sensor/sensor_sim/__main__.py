import argparse
import dataclasses
import logging

from .config import Config
from .data_source import load_measurements
from .publishers import create_publisher
from .simulator import Simulator


def main():
    p = argparse.ArgumentParser(description="Simulerad badvattensensor")
    p.add_argument("--transport", choices=["mqtt", "http"])
    p.add_argument("--interval", type=float, help="sekunder mellan meddelanden")
    p.add_argument("--count", type=int, help="antal meddelanden (standard: obegränsat)")
    p.add_argument("--offline", action="store_true", help="använd bara lokal sampledata")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = Config.from_env()
    overrides = {k: v for k, v in {"transport": args.transport, "interval": args.interval}.items() if v}
    cfg = dataclasses.replace(cfg, **overrides)

    publisher = create_publisher(cfg)
    sim = Simulator(load_measurements(cfg, args.offline), publisher, cfg.interval,
                    cfg.max_retries, cfg.retry_base_delay)
    try:
        sim.run(args.count)
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Stoppad av användaren")
    finally:
        publisher.close()


if __name__ == "__main__":
    main()
