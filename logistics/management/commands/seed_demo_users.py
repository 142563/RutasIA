import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from logistics.models import Driver, UserProfile

DEMO_USERS = [
    ("admin", "Andrea", "Castillo", UserProfile.Role.ADMIN),
    ("despachador", "Luis", "Ortiz", UserProfile.Role.DISPATCHER),
    ("conductor", "Carlos", "Mendoza", UserProfile.Role.DRIVER),
]


class Command(BaseCommand):
    help = (
        "Crea los usuarios de demostración admin, despachador y conductor. "
        "La contraseña es obligatoria (--password o variable DEMO_PASSWORD): nunca hay una fija."
    )

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Contraseña para los tres usuarios (o DEMO_PASSWORD en .env).")

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"] or os.getenv("DEMO_PASSWORD", "")
        if len(password) < 10:
            raise CommandError("Indica una contraseña de al menos 10 caracteres con --password o DEMO_PASSWORD.")

        for username, first, last, role in DEMO_USERS:
            user, created = User.objects.get_or_create(username=username)
            user.first_name, user.last_name = first, last
            user.is_staff = user.is_superuser = role == UserProfile.Role.ADMIN
            user.set_password(password)
            user.save()
            UserProfile.objects.update_or_create(user=user, defaults={"role": role})
            action = "Creado" if created else "Actualizado"
            self.stdout.write(f"{action}: {username} ({UserProfile.Role(role).label})")

        conductor = User.objects.get(username="conductor")
        driver = Driver.objects.filter(user=conductor).first() or Driver.objects.filter(user__isnull=True).first()
        if driver is None:
            driver = Driver.objects.create(name="Carlos Mendoza", license_number="DEMO-0001")
        driver.user = conductor
        driver.save(update_fields=["user", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"El usuario 'conductor' maneja como: {driver.name}"))
