from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0004_alert_notification")]

    operations = [
        migrations.AddField(
            model_name="accountinvitation",
            name="sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Inbjudningar som skickades före detta fält räknas som skickade vid utfärdandet.
        migrations.RunSQL(
            "UPDATE monitoring_accountinvitation SET sent_at = issued_at WHERE sent_at IS NULL",
            migrations.RunSQL.noop,
        ),
    ]
