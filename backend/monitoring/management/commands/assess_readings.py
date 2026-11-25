"""Bedömer redan sparade mätningar (till exempel efter att detektionen införts)."""
from django.core.management.base import BaseCommand
from django.db import transaction

from monitoring.ai.anomaly import analyse_series, record
from monitoring.models import Reading


class Command(BaseCommand):
    help = "Kör avvikelsedetektionen över sparade mätningar och uppdaterar bedömningarna."

    def add_arguments(self, parser):
        parser.add_argument("--sensor", help="Begränsa till ett sensor_id.")
        parser.add_argument("--dry-run", action="store_true", help="Visa utfallet utan att spara.")

    def handle(self, *args, **options):
        qs = Reading.objects.all()
        if options["sensor"]:
            qs = qs.filter(sensor_id=options["sensor"])
        pairs = qs.order_by().values_list("sensor_id", "metric").distinct()
        total = flagged = 0
        for sensor_id, metric in sorted(pairs):
            rows = list(qs.filter(sensor_id=sensor_id, metric=metric).order_by("timestamp"))
            findings = analyse_series([r.value for r in rows], metric)
            total += len(rows)
            for reading, finding in zip(rows, findings):
                if finding is None:
                    if not options["dry_run"] and hasattr(reading, "assessment"):
                        record(reading, None)
                    continue
                flagged += 1
                self.stdout.write(f"{sensor_id} {metric} {reading.timestamp:%Y-%m-%d %H:%M} "
                                  f"{reading.value}: {finding.kind}/{finding.reason}")
                if not options["dry_run"]:
                    with transaction.atomic():
                        record(reading, finding)
        self.stdout.write(f"Bedömde {total} mätningar, markerade {flagged}.")
