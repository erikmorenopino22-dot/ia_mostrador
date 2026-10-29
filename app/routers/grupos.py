import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import solo_profe
from ..models import Alumno, Grupo, Profesor, Sesion
from ..schemas import GrupoEntrada, GrupoOut, ResetPin
from ..security import hash_secreto

router = APIRouter(prefix="/api", tags=["grupos"])
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I para evitar confusiones


def _out(g: Grupo) -> GrupoOut:
    return GrupoOut(id=g.id, nombre=g.nombre, codigo=g.codigo, activo=g.activo, alumnos=len(g.alumnos))


def _grupo_propio(db: Session, grupo_id: int, profe: Profesor) -> Grupo:
    g = db.get(Grupo, grupo_id)
    if not g or g.profesor_id != profe.id:
        raise HTTPException(404, "Grupo no encontrado.")
    return g


@router.get("/grupos", response_model=list[GrupoOut])
def listar(profe: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    return [_out(g) for g in db.scalars(select(Grupo).where(Grupo.profesor_id == profe.id).order_by(Grupo.creado.desc()))]


@router.post("/grupos", response_model=GrupoOut)
def crear(datos: GrupoEntrada, profe: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    while True:
        codigo = "".join(secrets.choice(ALFABETO) for _ in range(6))
        if not db.scalar(select(Grupo).where(Grupo.codigo == codigo)):
            break
    g = Grupo(nombre=datos.nombre.strip(), codigo=codigo, profesor_id=profe.id)
    db.add(g)
    db.commit()
    return _out(g)


@router.post("/grupos/{grupo_id}/activo", response_model=GrupoOut)
def cambiar_activo(grupo_id: int, activo: bool, profe: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    g = _grupo_propio(db, grupo_id, profe)
    g.activo = activo
    db.commit()
    return _out(g)


@router.delete("/grupos/{grupo_id}")
def eliminar(grupo_id: int, profe: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    """Borra el grupo con su alumnado y todas sus prácticas. Solo grupos cerrados,
    para evitar borrados por error con la clase en marcha."""
    g = _grupo_propio(db, grupo_id, profe)
    if g.activo:
        raise HTTPException(409, "Cierra el grupo antes de eliminarlo.")
    ids = [a.id for a in g.alumnos]
    practicas = db.execute(delete(Sesion).where(Sesion.alumno_id.in_(ids))).rowcount if ids else 0
    db.execute(delete(Alumno).where(Alumno.grupo_id == g.id))
    db.delete(g)
    db.commit()
    return {"eliminado": True, "alumnos": len(ids), "practicas": practicas}


@router.get("/grupos/{grupo_id}/alumnos")
def alumnos(grupo_id: int, profe: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    g = _grupo_propio(db, grupo_id, profe)
    return [{"id": a.id, "alias": a.alias} for a in sorted(g.alumnos, key=lambda a: a.alias.lower())]


@router.post("/alumnos/{alumno_id}/pin")
def cambiar_pin(alumno_id: int, datos: ResetPin, profe: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    a = db.get(Alumno, alumno_id)
    if not a or a.grupo.profesor_id != profe.id:
        raise HTTPException(404, "Alumno no encontrado.")
    a.pin_hash = hash_secreto(datos.pin)
    db.commit()
    return {"ok": True}
