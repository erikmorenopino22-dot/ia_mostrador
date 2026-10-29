"""Primer arranque: se ejecuta antes que el resto (orden alfabético)."""
from fastapi.testclient import TestClient

from app.main import app
from app.routers import inicio

c = TestClient(app)


def test_primer_arranque():
    e = c.get("/api/estado").json()
    assert e["necesita_configuracion"] is True
    assert inicio.ARCHIVO_CODIGO.exists()
    codigo = inicio.codigo_configuracion()

    datos = {"nombre": "Admin", "email": "admin@centro.es", "password": "una-contraseña-larga"}
    assert c.post("/api/configuracion-inicial", json={**datos, "codigo": "000000"}).status_code == 403
    r = c.post("/api/configuracion-inicial", json={**datos, "codigo": codigo})
    assert r.status_code == 200 and r.json()["rol"] == "profe"
    assert not inicio.ARCHIVO_CODIGO.exists()

    # Ya no se puede repetir
    assert c.post("/api/configuracion-inicial", json={**datos, "codigo": codigo}).status_code == 409
    assert c.get("/api/estado").json()["necesita_configuracion"] is False

    # Los casos de ejemplo se cargan solos
    token = r.json()["token"]
    assert len(c.get("/api/casos", headers={"Authorization": f"Bearer {token}"}).json()) == 9

    # Puede dar acceso a otra profesora; el alumnado no
    h = {"Authorization": f"Bearer {token}"}
    nueva = {"nombre": "Laura", "email": "laura@centro.es", "password": "otra-contraseña-larga"}
    assert c.post("/api/profesores", json=nueva, headers=h).status_code == 200
    assert c.post("/api/profesores", json=nueva, headers=h).status_code == 409
    assert c.post("/api/profe/login", json={"email": "laura@centro.es", "password": "otra-contraseña-larga"}).status_code == 200
