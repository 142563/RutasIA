"""A qué usuarios del personal les toca un evento, según la matriz por rol (domain/notifications.py)."""
from __future__ import annotations

from django.contrib.auth.models import User

from logistics.domain.notifications import Event, Scope, staff_scopes
from logistics.models import Route


def _role(user: User | None) -> str | None:
    return getattr(getattr(user, "profile", None), "role", None) if user else None


def _reachable(user: User | None) -> bool:
    return bool(user and user.is_active and user.email)


def staff_recipients(event: Event, route: Route | None = None, user: User | None = None) -> list[User]:
    """Usuarios (sin repetir) que deben recibir `event`. `user` es el destinatario de SELF (bienvenida)."""
    found: dict[int, User] = {}
    for role, scope in staff_scopes(event).items():
        if scope is Scope.ALL:
            for u in User.objects.filter(is_active=True, profile__role=role).exclude(email="").select_related("profile"):
                found[u.pk] = u
        elif scope is Scope.SELF:
            if _reachable(user) and _role(user) == role:
                found[user.pk] = user
        elif scope is Scope.CREATOR and route is not None:
            creator = route.created_by
            if _reachable(creator) and _role(creator) == role:
                found[creator.pk] = creator
        elif scope is Scope.ASSIGNED and route is not None:
            driver_user = getattr(route.driver, "user", None) if route.driver_id else None
            if _reachable(driver_user) and _role(driver_user) == role:
                found[driver_user.pk] = driver_user
    return list(found.values())
