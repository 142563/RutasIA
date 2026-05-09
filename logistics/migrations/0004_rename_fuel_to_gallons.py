from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logistics", "0003_fuelprice_trip_estimated_fuel_cost_gtq_and_more"),
    ]

    operations = [
        # FuelPrice: rename _l fields to _gal and update defaults to Q/galón
        migrations.RenameField(
            model_name="fuelprice",
            old_name="regular_gtq_l",
            new_name="regular_gtq_gal",
        ),
        migrations.RenameField(
            model_name="fuelprice",
            old_name="super_gtq_l",
            new_name="super_gtq_gal",
        ),
        migrations.RenameField(
            model_name="fuelprice",
            old_name="diesel_gtq_l",
            new_name="diesel_gtq_gal",
        ),
        migrations.AlterField(
            model_name="fuelprice",
            name="regular_gtq_gal",
            field=models.DecimalField(decimal_places=2, default=Decimal("32.00"), max_digits=6),
        ),
        migrations.AlterField(
            model_name="fuelprice",
            name="super_gtq_gal",
            field=models.DecimalField(decimal_places=2, default=Decimal("35.00"), max_digits=6),
        ),
        migrations.AlterField(
            model_name="fuelprice",
            name="diesel_gtq_gal",
            field=models.DecimalField(decimal_places=2, default=Decimal("29.00"), max_digits=6),
        ),
        # Trip: rename estimated_fuel_liters → estimated_fuel_gallons
        migrations.RenameField(
            model_name="trip",
            old_name="estimated_fuel_liters",
            new_name="estimated_fuel_gallons",
        ),
        # Trip: rename fuel_price_gtq_l → fuel_price_gtq_gal
        migrations.RenameField(
            model_name="trip",
            old_name="fuel_price_gtq_l",
            new_name="fuel_price_gtq_gal",
        ),
    ]
