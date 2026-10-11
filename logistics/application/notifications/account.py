"""Bienvenida al crear una cuenta (A2, RUT-70): usuario, rol, qué correos recibirá y contraseña temporal.

La contraseña temporal solo viaja en el cuerpo del correo; nunca se guarda en la bitácora ni en logs.
"""
from __future__ import annotations


def notify_account_created(user_id: int, temp_password: str) -> list[str]:
    return []
