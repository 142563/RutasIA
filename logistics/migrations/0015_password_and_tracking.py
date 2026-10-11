import secrets

from django.db import migrations, models

import logistics.models


def fill_tokens(apps, schema_editor):
    Order = apps.get_model("logistics", "Order")
    for order in Order.objects.filter(tracking_token__isnull=True).only("id"):
        order.tracking_token = secrets.token_urlsafe(16)
        order.save(update_fields=["tracking_token"])


class Migration(migrations.Migration):
    dependencies = [("logistics", "0014_notification_log")]

    operations = [
        migrations.AddField(
            model_name="userprofile", name="must_change_password", field=models.BooleanField(default=False)),
        migrations.AddField(
            model_name="userprofile", name="temp_password_expires_at",
            field=models.DateTimeField(blank=True, null=True)),
        # Primero sin unique y vacío, se llena uno por uno y luego se vuelve único y obligatorio
        migrations.AddField(
            model_name="order", name="tracking_token", field=models.CharField(max_length=32, null=True, editable=False)),
        migrations.RunPython(fill_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order", name="tracking_token",
            field=models.CharField(default=logistics.models.new_tracking_token, editable=False, max_length=32,
                                   unique=True)),
    ]
