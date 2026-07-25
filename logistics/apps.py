from django.apps import AppConfig


class LogisticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "logistics"

    def ready(self):
        from django.db.models.signals import post_delete, post_save
        from logistics.models import Department, RouteConnection
        from logistics.domain.services import invalidate_route_cache

        def _invalidate(sender, **kwargs):
            invalidate_route_cache()

        post_save.connect(_invalidate, sender=RouteConnection)
        post_delete.connect(_invalidate, sender=RouteConnection)
        post_save.connect(_invalidate, sender=Department)
        post_delete.connect(_invalidate, sender=Department)
