"""Límites sencillos en memoria (se reinician al reiniciar el servidor).

Con varias instancias del servidor habría que moverlos a Redis o a la base
de datos; para un centro con un único servidor es suficiente.
"""
import threading
import time
from datetime import date

from fastapi import HTTPException

from .config import get_settings

_lock = threading.Lock()
_uso: dict[int, tuple[date, int]] = {}
_fallos: dict[str, list[float]] = {}


def consumir_mensaje_ia(alumno_id: int) -> None:
    limite = get_settings().limite_diario_alumno
    hoy = date.today()
    with _lock:
        dia, n = _uso.get(alumno_id, (hoy, 0))
        if dia != hoy:
            n = 0
        if n >= limite:
            raise HTTPException(429, "Has llegado al límite de mensajes de hoy. Mañana podrás seguir practicando.")
        _uso[alumno_id] = (hoy, n + 1)


def comprobar_bloqueo(clave: str) -> None:
    ahora = time.time()
    with _lock:
        recientes = [t for t in _fallos.get(clave, []) if ahora - t < 600]
        _fallos[clave] = recientes
        if len(recientes) >= 5:
            raise HTTPException(429, "Demasiados intentos. Espera 10 minutos o pide ayuda a tu profesora.")


def registrar_fallo(clave: str) -> None:
    with _lock:
        _fallos.setdefault(clave, []).append(time.time())


def limpiar_fallos(clave: str) -> None:
    with _lock:
        _fallos.pop(clave, None)
