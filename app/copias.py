"""Copias de seguridad automáticas de la base de datos.

Con SQLite (la instalación normal), mientras Mostrador está abierto:
  - hace una copia al arrancar si la última tiene más de COPIAS_HORAS horas,
  - y vuelve a comprobarlo cada hora;
  - conserva las COPIAS_CONSERVAR más recientes en la carpeta COPIAS_CARPETA.

La copia se hace con la función de copia en caliente de SQLite, así que es
segura aunque haya alumnado practicando en ese momento. Cada copia se
comprueba al terminar.

Con PostgreSQL (instalación con Docker) las copias se hacen con pg_dump:
ver README.md.
"""
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from .config import get_settings

_lock = threading.Lock()
_hilo: threading.Thread | None = None


def ruta_bd() -> Path | None:
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        return None
    return Path(url[len("sqlite:///"):]).resolve()


def carpeta() -> Path:
    return Path(get_settings().copias_carpeta).resolve()


def listar() -> list[Path]:
    c = carpeta()
    return sorted(c.glob("mostrador-*.db"), reverse=True) if c.exists() else []


def ultima() -> datetime | None:
    copias = listar()
    return datetime.fromtimestamp(copias[0].stat().st_mtime) if copias else None


def hacer_copia() -> Path:
    """Copia la base de datos ahora mismo. Devuelve la ruta de la copia."""
    origen = ruta_bd()
    if origen is None:
        raise RuntimeError("Las copias automáticas solo funcionan con SQLite. Con PostgreSQL, usa pg_dump.")
    if not origen.exists():
        raise RuntimeError("Todavía no hay base de datos que copiar.")
    with _lock:
        destino_dir = carpeta()
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / f"mostrador-{datetime.now():%Y-%m-%d_%H%M%S}.db"
        temporal = destino.with_suffix(".tmp")
        with sqlite3.connect(origen) as fuente, sqlite3.connect(temporal) as copia:
            fuente.backup(copia)
            if copia.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("La copia no ha superado la comprobación de integridad.")
        # Cerrar la conexión antes de renombrar (necesario en Windows).
        copia.close()
        temporal.replace(destino)
        for vieja in listar()[get_settings().copias_conservar:]:
            vieja.unlink(missing_ok=True)
        return destino


def _toca() -> bool:
    u = ultima()
    return u is None or (datetime.now() - u).total_seconds() >= get_settings().copias_horas * 3600


def _bucle():
    while True:
        try:
            if _toca():
                hecha = hacer_copia()
                print(f"Mostrador: copia de seguridad guardada en {hecha}", flush=True)
        except Exception as e:  # una copia fallida no debe parar la aplicación
            print(f"Mostrador: no se ha podido hacer la copia de seguridad: {e}", flush=True)
        time.sleep(3600)


def iniciar() -> None:
    """Arranca las copias automáticas en segundo plano (una sola vez)."""
    global _hilo
    if _hilo or ruta_bd() is None or get_settings().copias_horas <= 0:
        return
    _hilo = threading.Thread(target=_bucle, name="copias", daemon=True)
    _hilo.start()
