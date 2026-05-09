from decimal import Decimal
from django.db import migrations, models


def set_market_prices(apps, schema_editor):
    FuelPrice = apps.get_model("logistics", "FuelPrice")
    FuelPrice.objects.update_or_create(
        pk=1,
        defaults={
            "regular_gtq_gal": Decimal("29.50"),
            "super_gtq_gal": Decimal("32.00"),
            "diesel_gtq_gal": Decimal("24.00"),
            "source": "MEM Guatemala",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0004_rename_fuel_to_gallons"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fuelprice",
            name="regular_gtq_gal",
            field=models.DecimalField(decimal_places=2, default=Decimal("29.50"), max_digits=6),
        ),
        migrations.AlterField(
            model_name="fuelprice",
            name="super_gtq_gal",
            field=models.DecimalField(decimal_places=2, default=Decimal("32.00"), max_digits=6),
        ),
        migrations.AlterField(
            model_name="fuelprice",
            name="diesel_gtq_gal",
            field=models.DecimalField(decimal_places=2, default=Decimal("24.00"), max_digits=6),
        ),
        migrations.RunPython(set_market_prices, migrations.RunPython.noop),
    ]
