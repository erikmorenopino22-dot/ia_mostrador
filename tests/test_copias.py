import sqlite3

from fastapi.testclient import TestClient

from app import copias
from app.config import get_settings
from app.main import app


def test_copia_valida_y_rotacion():
    TestClient(app)  # asegura que la base de datos existe
    primera = copias.hacer_copia()
    assert primera.exists() and primera.parent == copias.carpeta()
    with sqlite3.connect(primera) as c:
        tablas = {f[0] for f in c.execute("select name from sqlite_master where type='table'")}
    assert {"casos", "profesores", "sesiones"} <= tablas
    assert copias.ultima() is not None

    cfg = get_settings()
    antes, cfg.copias_conservar = cfg.copias_conservar, 2
    try:
        for i in range(3):
            # nombres distintos aunque se hagan en el mismo segundo
            ruta = copias.hacer_copia()
            ruta.rename(ruta.with_name(f"mostrador-2000-01-0{i + 1}_000000.db"))
        nueva = copias.hacer_copia()
        quedan = copias.listar()
        assert len(quedan) == 2 and quedan[0] == nueva  # se conservan las más recientes
    finally:
        cfg.copias_conservar = antes


def test_estado_informa_de_copias():
    e = TestClient(app).get("/api/estado").json()
    assert e["copias"]["activas"] is True
