"""Puesta en marcha sin consola: estado del sistema, configuración inicial
desde el navegador y alta de más profesorado."""
import json
import secrets
import socket
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import copias
from ..config import get_settings
from ..db import SessionLocal, get_db
from ..deps import solo_profe
from ..llm import estado_ia
from ..models import Caso, Profesor
from ..schemas import Token
from ..security import crear_token, hash_secreto

router = APIRouter(prefix="/api", tags=["puesta en marcha"])

RAIZ = Path(__file__).resolve().parent.parent.parent
ARCHIVO_CODIGO = RAIZ / "CODIGO_CONFIGURACION.txt"
_codigo: str | None = None


def ip_local() -> str | None:
    """IP de este equipo en la red del centro (no envía nada a internet)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None
    finally:
        s.close()


def direcciones() -> list[str]:
    puerto = get_settings().puerto
    ip = ip_local()
    return [f"http://{ip}:{puerto}"] if ip else []


def preparar() -> None:
    """Se ejecuta al arrancar: carga los casos de ejemplo la primera vez y,
    si aún no hay profesorado, genera el código de configuración."""
    global _codigo
    with SessionLocal() as db:
        if not db.scalar(select(func.count()).select_from(Caso)):
            semilla = RAIZ / "seed" / "casos.json"
            if semilla.exists():
                for d in json.loads(semilla.read_text(encoding="utf-8")):
                    db.add(Caso(id=d["id"], titulo=d["titulo"], modulo=d.get("modulo", ""), situacion=d.get("situacion", ""),
                                personaje=d.get("personaje", ""), saludo=d.get("saludo", ""), rubrica=d["rubrica"],
                                rubrica_visible=d.get("rubricaVisible", True), publicado=d.get("publicado", True)))
                db.commit()
        hay_profes = db.scalar(select(func.count()).select_from(Profesor)) > 0
    if hay_profes:
        _codigo = None
        ARCHIVO_CODIGO.unlink(missing_ok=True)
        return
    if ARCHIVO_CODIGO.exists():
        _codigo = ARCHIVO_CODIGO.read_text(encoding="utf-8").split()[-1].strip()
    else:
        _codigo = "".join(secrets.choice("23456789") for _ in range(6))
        ARCHIVO_CODIGO.write_text(
            "Código para la configuración inicial de Mostrador (se borra solo al usarlo):\n" + _codigo + "\n",
            encoding="utf-8")
    print(f"Mostrador: código de configuración inicial {_codigo}", flush=True)


def codigo_configuracion() -> str | None:
    return _codigo


class Configuracion(BaseModel):
    codigo: str
    nombre: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=10, max_length=200)


class NuevoProfesor(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=10, max_length=200)


@router.get("/estado")
def estado(db: Session = Depends(get_db)):
    sin_profes = db.scalar(select(func.count()).select_from(Profesor)) == 0
    ultima = copias.ultima()
    return {"necesita_configuracion": sin_profes, "ia": estado_ia(), "direcciones": direcciones(),
            "proveedor": get_settings().llm_provider,
            "copias": {"activas": copias.ruta_bd() is not None and get_settings().copias_horas > 0,
                       "ultima": ultima.isoformat(timespec="minutes") if ultima else None,
                       "carpeta": str(copias.carpeta())}}


@router.post("/copias")
def copia_ahora(_: Profesor = Depends(solo_profe)):
    try:
        ruta = copias.hacer_copia()
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"archivo": ruta.name}


@router.post("/configuracion-inicial", response_model=Token)
def configuracion_inicial(d: Configuracion, db: Session = Depends(get_db)):
    global _codigo
    if db.scalar(select(func.count()).select_from(Profesor)):
        raise HTTPException(409, "Mostrador ya está configurado. Entra con tu cuenta de profesor.")
    if not _codigo or not secrets.compare_digest(d.codigo.strip(), _codigo):
        raise HTTPException(403, "El código no es correcto. Lo encontrarás en la ventana donde se está ejecutando Mostrador "
                                 "o en el archivo CODIGO_CONFIGURACION.txt de la carpeta del programa.")
    p = Profesor(email=d.email.strip().lower(), nombre=d.nombre.strip(), password_hash=hash_secreto(d.password))
    db.add(p)
    db.commit()
    _codigo = None
    ARCHIVO_CODIGO.unlink(missing_ok=True)
    return Token(token=crear_token("profe", p.id), rol="profe", nombre=p.nombre)


@router.get("/profesores")
def listar_profesores(_: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    return [{"id": p.id, "nombre": p.nombre, "email": p.email} for p in db.scalars(select(Profesor).order_by(Profesor.nombre))]


@router.post("/profesores")
def crear_profesor(d: NuevoProfesor, _: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    email = d.email.strip().lower()
    if db.scalar(select(Profesor).where(func.lower(Profesor.email) == email)):
        raise HTTPException(409, "Ya existe una cuenta con ese correo.")
    p = Profesor(email=email, nombre=d.nombre.strip(), password_hash=hash_secreto(d.password))
    db.add(p)
    db.commit()
    return {"id": p.id, "nombre": p.nombre, "email": p.email}
