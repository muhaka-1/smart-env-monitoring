from datetime import datetime, timezone

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ReadingMetricMigrationTests(TransactionTestCase):
    migrate_from = [("monitoring", "0001_initial")]
    migrate_to = [("monitoring", "0002_reading_metric")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        Reading = old_apps.get_model("monitoring", "Reading")

        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        Reading.objects.create(
            sensor_id="oak-street-beach-turbidity",
            timestamp=timestamp,
            value=12.3,
            unit="NTU",
        )
        Reading.objects.create(
            sensor_id="oak-street-beach-temperature",
            timestamp=timestamp,
            value=21.5,
            unit="°C",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_rows_keep_their_metric(self):
        Reading = self.apps.get_model("monitoring", "Reading")
        metrics = dict(Reading.objects.values_list("sensor_id", "metric"))

        self.assertEqual(metrics["oak-street-beach-turbidity"], "turbidity")
        self.assertEqual(metrics["oak-street-beach-temperature"], "temperature")
