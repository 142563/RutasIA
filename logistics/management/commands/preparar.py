"""Deja el proyecto listo para usar con un solo comando.

    python manage.py preparar
    python manage.py runserver      ->  http://127.0.0.1:8000

Se puede repetir sin miedo: no borra nada y no reemplaza datos reales de Google por estimados.
"""
from __future__ import annotations

import os
import secrets
import shutil
import subprocess

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from logistics.models import Edge, TrafficProfile


class Command(BaseCommand):
    help = (
        "Prepara todo en un paso: base de datos, grafo nacional, tráfico, datos y usuarios de demo, "
        "y compila la app React. Sin --google usa datos estimados/sintéticos (gratis, sin internet)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--google", action="store_true",
                            help="Grafo y tráfico REALES con Google Routes API (necesita GOOGLE_ROUTES_API_KEY; tiene costo).")
        parser.add_argument("--password", help="Contraseña de los usuarios de demo (si no, se usa DEMO_PASSWORD o se genera una).")
        parser.add_argument("--sin-frontend", action="store_true", help="No compilar la app React.")

    def step(self, n: int, text: str):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n[{n}/6] {text}"))

    def handle(self, *args, **options):
        google = options["google"]

        self.step(1, "Base de datos")
        call_command("migrate", interactive=False, verbosity=0)
        self.stdout.write("Migraciones aplicadas.")

        self.step(2, "Nodos del grafo nacional (cabeceras, municipios y cruces)")
        call_command("seed_graph_nodes")

        self.step(3, "Tramos de carretera")
        if google:
            call_command("build_graph")
        elif Edge.objects.exists():
            self.stdout.write("Ya existen; se conservan (no se reemplazan por estimados).")
        else:
            call_command("build_graph", estimate=True)

        self.step(4, "Tráfico por franja horaria")
        if google:
            call_command("calibrate_traffic")
        elif TrafficProfile.objects.exists():
            self.stdout.write("Ya existe; se conserva.")
        else:
            call_command("calibrate_traffic", synthetic=True)

        self.step(5, "Datos y usuarios de demostración")
        call_command("seed_demo_data")
        password, generated = self.demo_password(options["password"])
        call_command("seed_demo_users", password=password)

        self.step(6, "App React")
        built = False if options["sin_frontend"] else self.build_frontend()

        self.summary(password, generated, built, google)

    def demo_password(self, given: str | None) -> tuple[str, bool]:
        """La contraseña de demo nunca es fija: se toma de --password, de DEMO_PASSWORD o se genera y se guarda en .env."""
        password = given or os.getenv("DEMO_PASSWORD", "")
        if password:
            if len(password) < 10:
                raise CommandError("La contraseña de demo debe tener al menos 10 caracteres.")
            return password, False
        password = secrets.token_urlsafe(9)
        env_path = settings.BASE_DIR / ".env"
        with env_path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n# Generada por 'manage.py preparar' para los usuarios de demo\nDEMO_PASSWORD={password}\n")
        os.environ["DEMO_PASSWORD"] = password
        return password, True

    def build_frontend(self) -> bool:
        frontend = settings.BASE_DIR / "frontend"
        npm = shutil.which("npm")
        if npm is None:
            self.stdout.write(self.style.WARNING(
                "No se encontró Node.js. Instala Node.js 20 o superior (https://nodejs.org) y vuelve a correr este comando."))
            return False
        try:
            if not (frontend / "node_modules").exists():
                self.stdout.write("Instalando dependencias (npm ci, solo la primera vez)...")
                subprocess.run([npm, "ci"], cwd=frontend, check=True)
            self.stdout.write("Compilando (npm run build)...")
            subprocess.run([npm, "run", "build"], cwd=frontend, check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            self.stdout.write(self.style.ERROR(f"No se pudo compilar la app React: {exc}"))
            return False
        self.stdout.write("App compilada en frontend/dist/app/.")
        return True

    def summary(self, password: str, generated: bool, built: bool, google: bool):
        ok = self.style.SUCCESS
        self.stdout.write(ok("\nTodo listo."))
        self.stdout.write("  1. Corre:  python manage.py runserver")
        self.stdout.write("  2. Abre:   http://127.0.0.1:8000")
        self.stdout.write(f"  3. Entra con 'despachador' (planifica) o 'conductor' (entrega). Contraseña: {password}")
        if generated:
            self.stdout.write("     (La contraseña se generó y quedó guardada en .env como DEMO_PASSWORD.)")
        if not built:
            self.stdout.write(self.style.WARNING("  La app React no está compilada: la página mostrará cómo hacerlo."))
        if not settings.GOOGLE_MAPS_API_KEY:
            self.stdout.write(self.style.WARNING(
                "  Sin GOOGLE_MAPS_API_KEY en .env se verá el mapa esquemático en lugar de Google Maps."))
        if not google:
            self.stdout.write(self.style.WARNING(
                "  Datos de tráfico estimados/sintéticos: sirven para probar, NO para la tesis. "
                "Para datos reales: python manage.py preparar --google"))
