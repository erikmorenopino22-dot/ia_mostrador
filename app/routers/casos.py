import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Usuario, solo_profe, usuario_actual
from ..models import Caso, Profesor, Sesion
from ..schemas import CasoAlumno, CasoCompleto, CasoEntrada

router = APIRouter(prefix="/api", tags=["casos"])


def completo(c: Caso) -> CasoCompleto:
    return CasoCompleto(id=c.id, titulo=c.titulo, modulo=c.modulo, situacion=c.situacion, personaje=c.personaje,
                        saludo=c.saludo, rubrica=c.rubrica, rubricaVisible=c.rubrica_visible, publicado=c.publicado)


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60] or "caso"


def _aplicar(c: Caso, d: CasoEntrada) -> None:
    c.titulo, c.modulo, c.situacion = d.titulo.strip(), d.modulo.strip(), d.situacion.strip()
    c.personaje, c.saludo = d.personaje.strip(), d.saludo.strip()
    c.rubrica = [r.model_dump() for r in d.rubrica]
    c.rubrica_visible, c.publicado = d.rubricaVisible, d.publicado


@router.get("/casos")
def listar(u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    casos = db.scalars(select(Caso).order_by(Caso.titulo)).all()
    if u.rol == "profe":
        return [completo(c) for c in casos]
    return [CasoAlumno(id=c.id, titulo=c.titulo, modulo=c.modulo, situacion=c.situacion) for c in casos if c.publicado]


@router.post("/casos", response_model=CasoCompleto)
def crear(d: CasoEntrada, _: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    base = d.id or _slug(d.titulo)
    cid, n = base, 2
    while db.get(Caso, cid):
        cid, n = f"{base}-{n}", n + 1
    c = Caso(id=cid)
    _aplicar(c, d)
    db.add(c)
    db.commit()
    return completo(c)


@router.put("/casos/{caso_id}", response_model=CasoCompleto)
def editar(caso_id: str, d: CasoEntrada, _: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    c = db.get(Caso, caso_id)
    if not c:
        raise HTTPException(404, "Caso no encontrado.")
    _aplicar(c, d)
    db.commit()
    return completo(c)


@router.delete("/casos/{caso_id}")
def eliminar(caso_id: str, _: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    c = db.get(Caso, caso_id)
    if not c:
        raise HTTPException(404, "Caso no encontrado.")
    if db.scalar(select(Sesion.id).where(Sesion.caso_id == caso_id).limit(1)):
        # Hay prácticas hechas con este caso: se oculta en vez de borrarlo.
        c.publicado = False
        db.commit()
        return {"archivado": True}
    db.delete(c)
    db.commit()
    return {"eliminado": True}
