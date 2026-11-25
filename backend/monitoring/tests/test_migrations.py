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


class LanguagePreferenceMigrationTests(TransactionTestCase):
    def test_existing_accounts_and_readings_are_unchanged(self):
        executor = MigrationExecutor(connection)
        old_target = [("monitoring", "0004_alert_notification")]
        executor.migrate(old_target)
        try:
            old_apps = executor.loader.project_state(old_target).apps
            User = old_apps.get_model("auth", "User")
            user = User.objects.create(username="existing-reader", email="reader@example.test",
                                       password="existing-test-hash", is_active=True)
            Reading = old_apps.get_model("monitoring", "Reading")
            reading = Reading.objects.create(sensor_id="rainbow-beach-turbidity", metric="turbidity",
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), value=38.27, unit="NTU")
            target = [("monitoring", "0005_user_language_preference")]
            executor = MigrationExecutor(connection)
            executor.migrate(target)
            apps = executor.loader.project_state(target).apps
            migrated_user = apps.get_model("auth", "User").objects.get(pk=user.pk)
            migrated_reading = apps.get_model("monitoring", "Reading").objects.get(pk=reading.pk)
            self.assertEqual((migrated_user.username, migrated_user.email, migrated_user.password,
                              migrated_user.is_active), ("existing-reader", "reader@example.test", "existing-test-hash", True))
            self.assertEqual((migrated_reading.value, migrated_reading.unit), (38.27, "NTU"))
            self.assertEqual(apps.get_model("monitoring", "UserLanguagePreference").objects.count(), 0)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
