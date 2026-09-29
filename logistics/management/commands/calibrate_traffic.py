from django.core.management.base import BaseCommand, CommandError

from logistics.models import Edge
from logistics.routing.calibration import (
    PROFILES, calibrate_from_google, calibrate_synthetic, elements_needed,
)
from logistics.routing.google import RoutesApiError, RoutesClient


class Command(BaseCommand):
    help = (
        "Calibra los 14 perfiles de tráfico (7 franjas × laboral/fin de semana) de cada arista. "
        "Con Google Routes API (por defecto) o sintéticos sin conexión (--synthetic)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--synthetic", action="store_true",
                            help="Sin conexión: multiplicadores de un modelo simple (NO aptos para la tesis).")
        parser.add_argument("--refresh", action="store_true",
                            help="Vuelve a pedir a Google aunque haya muestras recientes.")
        parser.add_argument("--yes", action="store_true", help="No pedir confirmación antes de consultar a Google.")

    def handle(self, *args, **options):
        if not Edge.objects.filter(is_active=True).exists():
            raise CommandError("No hay aristas. Corre primero: python manage.py build_graph")

        if options["synthetic"]:
            report = calibrate_synthetic()
            self.stdout.write(self.style.WARNING(
                "Modo sin conexión: perfiles SINTÉTICOS (source=synthetic). No usar en el documento de tesis."
            ))
        else:
            try:
                client = RoutesClient()
            except RoutesApiError as exc:
                raise CommandError(str(exc)) from exc
            needed = elements_needed()
            self.stdout.write(
                f"Se consultarán hasta {needed} elementos de Routes API con tráfico "
                f"({needed // len(PROFILES)} aristas × {len(PROFILES)} perfiles; los recientes salen de la caché)."
            )
            if not options["yes"] and input("¿Continuar? [s/N] ").strip().lower() not in ("s", "si", "sí", "y", "yes"):
                raise CommandError("Calibración cancelada.")
            report = calibrate_from_google(client, refresh=options["refresh"])
            self.stdout.write(f"Solicitudes a Google: {report.requests} ({report.elements} elementos).")

        self.stdout.write(self.style.SUCCESS(
            f"Aristas calibradas: {report.edges_calibrated}; perfiles escritos: {report.profiles_written}."
        ))
        for a, b, reason in report.edges_skipped[:20]:
            self.stdout.write(self.style.WARNING(f"  Omitida {a} -> {b}: {reason}"))
        if report.missing_profiles:
            self.stdout.write(self.style.WARNING(
                f"  {len(report.missing_profiles)} perfiles sin respuesta de Google (se usa m = 1)."
            ))
