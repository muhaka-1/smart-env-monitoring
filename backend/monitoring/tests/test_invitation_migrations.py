from datetime import datetime, timezone

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class InvitationLanguageMigrationTests(TransactionTestCase):
    target = [("monitoring", "0006_merge_invitation_and_language")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def verify_upgrade(self, source, has_sent_at):
        executor = MigrationExecutor(connection)
        executor.migrate([("monitoring", "0004_alert_notification")])
        executor = MigrationExecutor(connection)
        executor.migrate(source)
        apps = executor.loader.project_state(source).apps
        user = apps.get_model("auth", "User").objects.create(
            username="migration-reader", email="reader@example.test", password="!", is_active=False
        )
        issued = datetime(2026, 11, 10, tzinfo=timezone.utc)
        invitation = apps.get_model("monitoring", "AccountInvitation").objects.create(
            user_id=user.pk, issued_at=issued, token_digest="a" * 64
        )
        if not has_sent_at:
            apps.get_model("monitoring", "UserLanguagePreference").objects.create(user_id=user.pk, language="de")
        executor = MigrationExecutor(connection)
        executor.migrate(self.target)
        apps = executor.loader.project_state(self.target).apps
        saved = apps.get_model("auth", "User").objects.get(pk=user.pk)
        self.assertEqual((saved.username, saved.email, saved.password, saved.is_active),
                         (user.username, user.email, "!", False))
        saved_invitation = apps.get_model("monitoring", "AccountInvitation").objects.get(pk=invitation.pk)
        self.assertEqual(saved_invitation.token_digest, "a" * 64)
        self.assertEqual(saved_invitation.issued_at, issued)
        self.assertEqual(saved_invitation.sent_at, None if has_sent_at else issued)
        preference = apps.get_model("monitoring", "UserLanguagePreference")
        if not has_sent_at:
            self.assertEqual(preference.objects.get(user_id=user.pk).language, "de")
        else:
            self.assertFalse(preference.objects.filter(user_id=user.pk).exists())
        # Senare migrationer får byggas ovanpå sammanslagningen, men grenarna måste vara sammanslagna.
        leaves = executor.loader.graph.leaf_nodes("monitoring")
        self.assertEqual(len(leaves), 1)
        self.assertIn(self.target[0], executor.loader.graph.forwards_plan(leaves[0]))

    def test_upgrade_from_language_migration_preserves_accounts_and_preferences(self):
        self.verify_upgrade([("monitoring", "0005_user_language_preference")], has_sent_at=False)

    def test_upgrade_from_invitation_migration_preserves_pending_delivery(self):
        self.verify_upgrade([("monitoring", "0005_accountinvitation_sent_at")], has_sent_at=True)
