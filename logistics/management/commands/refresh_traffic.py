from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Recalibración semanal del tráfico con Google, sin preguntar. "
        "Solo vuelve a pedir las muestras de más de 7 días (las recientes salen de la caché en BD)."
    )

    def handle(self, *args, **options):
        self.stdout.write("Recalibrando el tráfico con Google (solo muestras de más de 7 días)...")
        try:
            call_command("calibrate_traffic", yes=True, stdout=self.stdout, stderr=self.stderr)
        except CommandError as exc:
            raise CommandError(f"No se pudo recalibrar el tráfico: {exc}") from exc
        self.stdout.write(self.style.SUCCESS("Recalibración del tráfico terminada."))
