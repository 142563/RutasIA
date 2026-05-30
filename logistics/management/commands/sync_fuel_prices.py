from django.core.management.base import BaseCommand, CommandError

from logistics.infrastructure.fuel_scraper import fetch_mem_fuel_prices
from logistics.models import FuelPrice


class Command(BaseCommand):
    help = "Sincroniza los precios de combustible desde el sitio del MEM Guatemala."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra los precios encontrados sin guardarlos en la base de datos.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        self.stdout.write("Consultando precios en mem.gob.gt...")

        try:
            prices = fetch_mem_fuel_prices()
        except Exception as exc:
            raise CommandError(f"Error al obtener precios: {exc}") from exc

        self.stdout.write(
            f"  Regular : Q{prices.regular}/galón\n"
            f"  Super   : Q{prices.super_}/galón\n"
            f"  Diesel  : Q{prices.diesel}/galón"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run activo: no se guardaron cambios."))
            return

        fuel = FuelPrice.current()
        fuel.regular_gtq_gal = prices.regular
        fuel.super_gtq_gal = prices.super_
        fuel.diesel_gtq_gal = prices.diesel
        fuel.source = f"MEM Guatemala (auto-sync)"
        fuel.save()

        self.stdout.write(self.style.SUCCESS("Precios actualizados correctamente."))
