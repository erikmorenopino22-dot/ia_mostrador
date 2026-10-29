import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Profesor
from app.security import hash_secreto
from scripts.cargar_casos import main as cargar_casos

c = TestClient(app)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def entorno():
    import sys
    sys.argv = ["cargar_casos"]
    cargar_casos()
    with SessionLocal() as db:
        db.add(Profesor(email="profe@centro.es", nombre="Marta", password_hash=hash_secreto("contraseña-segura")))
        db.add(Profesor(email="otro@centro.es", nombre="Otro", password_hash=hash_secreto("contraseña-segura")))
        db.commit()
    tp = c.post("/api/profe/login", json={"email": "profe@centro.es", "password": "contraseña-segura"}).json()["token"]
    grupo = c.post("/api/grupos", json={"nombre": "1º Farmacia A"}, headers=auth(tp)).json()
    ta = c.post("/api/alumno/entrar", json={"codigo": grupo["codigo"], "alias": "Lucía", "pin": "1234"}).json()["token"]
    tb = c.post("/api/alumno/entrar", json={"codigo": grupo["codigo"], "alias": "Pau", "pin": "5678"}).json()["token"]
    return {"profe": tp, "a": ta, "b": tb, "grupo": grupo}


def test_login_incorrecto():
    r = c.post("/api/profe/login", json={"email": "profe@centro.es", "password": "mal"})
    assert r.status_code == 401


def test_pin_incorrecto(entorno):
    r = c.post("/api/alumno/entrar", json={"codigo": entorno["grupo"]["codigo"], "alias": "lucía", "pin": "0000"})
    assert r.status_code == 401


def test_alumno_no_ve_personaje(entorno):
    casos = c.get("/api/casos", headers=auth(entorno["a"])).json()
    assert len(casos) == 9
    assert "personaje" not in casos[0]
    completos = c.get("/api/casos", headers=auth(entorno["profe"])).json()
    assert "personaje" in completos[0]


def test_alumno_no_puede_crear_casos(entorno):
    r = c.post("/api/casos", json={"titulo": "x", "rubrica": [{"id": "c1", "texto": "t", "puntos": 1}]}, headers=auth(entorno["a"]))
    assert r.status_code == 403


def test_flujo_completo(entorno):
    s = c.post("/api/sesiones", json={"caso_id": "embarazada-espalda", "idioma": "es"}, headers=auth(entorno["a"])).json()
    assert s["rubrica"] == []  # rúbrica oculta en este caso mientras dura la práctica
    assert s["mensajes"][0]["r"] == "cliente"

    r = c.post(f"/api/sesiones/{s['id']}/mensajes", json={"texto": "Hola, ¿para quién es?"}, headers=auth(entorno["a"]))
    assert r.status_code == 200 and len(r.json()["mensajes"]) == 3

    r = c.post(f"/api/sesiones/{s['id']}/pista", headers=auth(entorno["a"]))
    assert r.json()["pistas"] == 1

    # Otro alumno no puede ver ni escribir en esta práctica
    assert c.get(f"/api/sesiones/{s['id']}", headers=auth(entorno["b"])).status_code == 404
    assert c.post(f"/api/sesiones/{s['id']}/mensajes", json={"texto": "x"}, headers=auth(entorno["b"])).status_code == 404

    fin = c.post(f"/api/sesiones/{s['id']}/terminar", headers=auth(entorno["a"])).json()
    assert fin["estado"] == "entregada"
    assert len(fin["propuesta_ia"]["criterios"]) == 6
    assert len(fin["rubrica"]) == 6  # al terminar ya se muestra

    # Ya no se puede seguir escribiendo
    assert c.post(f"/api/sesiones/{s['id']}/mensajes", json={"texto": "x"}, headers=auth(entorno["a"])).status_code == 409

    lista = c.get("/api/entregas?estado=entregada", headers=auth(entorno["profe"])).json()
    assert any(e["id"] == s["id"] and e["alias"] == "Lucía" for e in lista)

    # Otro profesor no ve prácticas de grupos ajenos
    to = c.post("/api/profe/login", json={"email": "otro@centro.es", "password": "contraseña-segura"}).json()["token"]
    assert c.get(f"/api/sesiones/{s['id']}", headers=auth(to)).status_code == 404

    nota = c.put(f"/api/sesiones/{s['id']}/nota", json={"puntos": {"c1": 1, "c2": 99}, "comentario": "Bien"},
                 headers=auth(entorno["profe"])).json()
    assert nota["estado"] == "revisada"
    assert nota["evaluacion_profe"]["puntos"]["c2"] == 3  # se recorta al máximo

    mias = c.get("/api/sesiones", headers=auth(entorno["a"])).json()
    assert mias[0]["puntos_profe"] == 4 and mias[0]["puntos_max"] == 10


def test_caso_con_practicas_se_archiva(entorno):
    r = c.delete("/api/casos/embarazada-espalda", headers=auth(entorno["profe"]))
    assert r.json() == {"archivado": True}
    casos = c.get("/api/casos", headers=auth(entorno["a"])).json()
    assert all(x["id"] != "embarazada-espalda" for x in casos)


def test_exportar_entrenamiento(entorno, tmp_path):
    import json
    import sys

    from scripts.exportar_entrenamiento import main as exportar
    sys.argv = ["exportar", str(tmp_path)]
    exportar()
    lineas = (tmp_path / "valoracion.jsonl").read_text(encoding="utf-8").splitlines()
    assert lineas
    ejemplo = json.loads(lineas[0])
    respuesta = json.loads(ejemplo["messages"][1]["content"])
    # La respuesta esperada es la nota de la profesora (c2 = 3), no la de la IA (1)
    assert {c["id"]: c["puntos"] for c in respuesta["criterios"]}["c2"] == 3
    assert respuesta["mejorar"] == "Bien"
    todo = (tmp_path / "valoracion.jsonl").read_text(encoding="utf-8") + (tmp_path / "cliente.jsonl").read_text(encoding="utf-8")
    assert "Lucía" not in todo
    assert "Coincidencia" in (tmp_path / "resumen.txt").read_text(encoding="utf-8")


def test_eliminar_grupo(entorno):
    h = auth(entorno["profe"])
    gid = entorno["grupo"]["id"]
    assert c.delete(f"/api/grupos/{gid}", headers=h).status_code == 409  # abierto: no se puede
    c.post(f"/api/grupos/{gid}/activo?activo=false", headers=h)
    # otro profesor no puede borrarlo
    to = c.post("/api/profe/login", json={"email": "otro@centro.es", "password": "contraseña-segura"}).json()["token"]
    assert c.delete(f"/api/grupos/{gid}", headers=auth(to)).status_code == 404
    r = c.delete(f"/api/grupos/{gid}", headers=h).json()
    assert r["eliminado"] and r["alumnos"] == 2 and r["practicas"] >= 1
    assert c.get("/api/entregas?estado=todas", headers=h).json() == []
    # el alumnado del grupo borrado ya no puede entrar con su sesión
    assert c.get("/api/sesiones", headers=auth(entorno["a"])).status_code == 401
