from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import Alumno, Profesor
from .security import leer_token


@dataclass
class Usuario:
    rol: str  # "profe" | "alumno"
    profesor: Profesor | None = None
    alumno: Alumno | None = None


def usuario_actual(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> Usuario:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Tienes que iniciar sesión.")
    try:
        datos = leer_token(authorization.split(" ", 1)[1])
    except jwt.PyJWTError:
        raise HTTPException(401, "La sesión ha caducado. Vuelve a entrar.")
    if datos.get("rol") == "profe":
        p = db.get(Profesor, int(datos["sub"]))
        if p:
            return Usuario("profe", profesor=p)
    elif datos.get("rol") == "alumno":
        a = db.get(Alumno, int(datos["sub"]))
        if a and a.grupo.activo:
            return Usuario("alumno", alumno=a)
    raise HTTPException(401, "La sesión no es válida. Vuelve a entrar.")


def solo_profe(u: Usuario = Depends(usuario_actual)) -> Profesor:
    if u.rol != "profe":
        raise HTTPException(403, "Solo el profesorado puede hacer esto.")
    return u.profesor


def solo_alumno(u: Usuario = Depends(usuario_actual)) -> Alumno:
    if u.rol != "alumno":
        raise HTTPException(403, "Esta acción es para el alumnado.")
    return u.alumno
