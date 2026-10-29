from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Usuario, usuario_actual
from ..limites import comprobar_bloqueo, limpiar_fallos, registrar_fallo
from ..models import Alumno, Grupo, Profesor
from ..schemas import EntrarAlumno, LoginProfe, Token
from ..security import crear_token, hash_secreto, verificar_secreto

router = APIRouter(prefix="/api", tags=["acceso"])


@router.post("/profe/login", response_model=Token)
def login_profe(datos: LoginProfe, db: Session = Depends(get_db)):
    clave = "profe:" + datos.email.lower()
    comprobar_bloqueo(clave)
    p = db.scalar(select(Profesor).where(func.lower(Profesor.email) == datos.email.lower()))
    if not p or not verificar_secreto(datos.password, p.password_hash):
        registrar_fallo(clave)
        raise HTTPException(401, "El correo o la contraseña no son correctos.")
    limpiar_fallos(clave)
    return Token(token=crear_token("profe", p.id), rol="profe", nombre=p.nombre)


@router.post("/alumno/entrar", response_model=Token)
def entrar_alumno(datos: EntrarAlumno, db: Session = Depends(get_db)):
    """Entra con el código del grupo, un alias y un PIN.

    La primera vez que se usa un alias en un grupo, se crea con ese PIN.
    Las siguientes veces, el PIN tiene que coincidir.
    """
    codigo = datos.codigo.strip().upper()
    grupo = db.scalar(select(Grupo).where(Grupo.codigo == codigo, Grupo.activo.is_(True)))
    if not grupo:
        raise HTTPException(404, "No existe ningún grupo activo con ese código. Revísalo con tu profesora.")
    clave = f"alumno:{grupo.id}:{datos.alias.lower()}"
    comprobar_bloqueo(clave)
    alumno = db.scalar(select(Alumno).where(Alumno.grupo_id == grupo.id, func.lower(Alumno.alias) == datos.alias.lower()))
    if alumno is None:
        alumno = Alumno(alias=datos.alias, pin_hash=hash_secreto(datos.pin), grupo_id=grupo.id)
        db.add(alumno)
        db.commit()
    elif not verificar_secreto(datos.pin, alumno.pin_hash):
        registrar_fallo(clave)
        raise HTTPException(401, "Ese alias ya existe en el grupo y el PIN no coincide. Si lo has olvidado, tu profesora puede cambiarlo.")
    limpiar_fallos(clave)
    return Token(token=crear_token("alumno", alumno.id), rol="alumno", nombre=alumno.alias, grupo=grupo.nombre)


@router.get("/yo", response_model=Token)
def yo(u: Usuario = Depends(usuario_actual)):
    if u.rol == "profe":
        return Token(token="", rol="profe", nombre=u.profesor.nombre)
    return Token(token="", rol="alumno", nombre=u.alumno.alias, grupo=u.alumno.grupo.nombre)
