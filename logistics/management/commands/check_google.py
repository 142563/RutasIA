from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from logistics.routing.google import RoutesApiError, RoutesClient

# Ciudad de Guatemala → Antigua Guatemala: una sola consulta (1 elemento)
PROBE_ORIGIN = (14.6349, -90.5069)
PROBE_DESTINATION = (14.5586, -90.7295)

HINTS = {
    "403": "La key existe pero no tiene permiso: activa \"Routes API\" en el proyecto y revisa que la "
           "restricción de la key incluya Routes API (docs/GOOGLE_KEYS.md, pasos 2 y 4).",
    "400": "Google rechazó la solicitud: suele ser una key mal copiada (espacios o comillas en .env).",
    "429": "Se superó la cuota: espera unos minutos o revisa las cuotas del proyecto.",
    "billing": "El proyecto no tiene facturación activa (docs/GOOGLE_KEYS.md, paso 1).",
}


class Command(BaseCommand):
    help = (
        "Verifica las keys de Google con una consulta mínima (1 elemento de Routes API) "
        "y explica cómo corregir los errores comunes."
    )

    def handle(self, *args, **options):
        ok = True

        self.stdout.write("Key del SERVIDOR (GOOGLE_ROUTES_API_KEY)")
        try:
            client = RoutesClient()
            elements = client.compute_route_matrix([PROBE_ORIGIN], [PROBE_DESTINATION], traffic=False)
            element = elements[0]
            if not element.ok:
                raise RoutesApiError(f"Google respondió sin ruta: {element.status}")
            self.stdout.write(self.style.SUCCESS(
                f"  OK · Ciudad de Guatemala → Antigua: {element.distance_m / 1000:.1f} km, "
                f"{(element.static_duration_s or element.duration_s) / 60:.0f} min sin tráfico (1 elemento consultado)"
            ))
        except RoutesApiError as exc:
            ok = False
            message = str(exc)
            self.stdout.write(self.style.ERROR(f"  Falla: {message[:300]}"))
            hint = next((h for code, h in HINTS.items() if code in message or code in message.lower()), None)
            self.stdout.write(f"  Qué hacer: {hint or 'revisa docs/GOOGLE_KEYS.md'}")

        self.stdout.write("\nKey del NAVEGADOR (GOOGLE_MAPS_API_KEY)")
        if settings.GOOGLE_MAPS_API_KEY:
            self.stdout.write(self.style.SUCCESS(
                "  Configurada. Se valida en el navegador (restringida por HTTP referrer): "
                "abre la app y revisa la consola si el mapa de Google no carga."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "  No configurada. La app funciona con el mapa esquemático; Places y Directions quedan apagados."
            ))

        if not ok:
            raise CommandError("La key del servidor no funciona todavía.")
        self.stdout.write(self.style.SUCCESS(
            "\nListo para datos reales: python manage.py build_graph && python manage.py calibrate_traffic"
        ))
