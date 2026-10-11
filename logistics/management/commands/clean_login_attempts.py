"""Elimina contadores inactivos sin liberar bloqueos vigentes."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from logistics.models import LoginAttempt


class Command(BaseCommand):
    help = "Elimina los contadores de login sin actividad en las últimas 24 horas."

    def handle(self, *args, **options):
        now = timezone.now()
        deleted, _ = LoginAttempt.objects.filter(touched_at__lt=now - timedelta(hours=24)).filter(
            Q(blocked_until__isnull=True) | Q(blocked_until__lte=now)
        ).delete()
        self.stdout.write(f"Contadores de inicio de sesión eliminados: {deleted}.")
