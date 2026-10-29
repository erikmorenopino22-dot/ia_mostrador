from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import prompts
from ..config import get_settings
from ..db import get_db
from ..deps import Usuario, solo_alumno, solo_profe, usuario_actual
from ..limites import consumir_mensaje_ia
from ..llm import get_ia
from ..models import Alumno, Caso, Grupo, Profesor, Sesion
from ..schemas import NotaProfe, NuevaSesion, NuevoMensaje, SesionOut, SesionResumen

router = APIRouter(prefix="/api", tags=["prácticas"])
NIVELES = {"logrado", "parcial", "no_logrado"}


def _max(s: Sesion) -> float:
    return sum(float(r["puntos"]) for r in s.rubrica)


def _total_ia(s: Sesion) -> float | None:
    return sum(c["puntos"] for c in s.propuesta_ia["criterios"]) if s.propuesta_ia else None


def _total_profe(s: Sesion) -> float | None:
    if not s.evaluacion_profe:
        return None
    return sum(float(s.evaluacion_profe["puntos"].get(r["id"], 0)) for r in s.rubrica)


def _out(s: Sesion, para_profe: bool) -> SesionOut:
    ver_rubrica = para_profe or s.caso.rubrica_visible or s.estado != "en_curso"
    return SesionOut(
        id=s.id, caso_id=s.caso_id, caso_titulo=s.caso_titulo, modulo=s.caso.modulo, situacion=s.caso.situacion,
        rubrica=s.rubrica if ver_rubrica else [], estado=s.estado, idioma=s.idioma, pistas=s.pistas,
        mensajes=s.mensajes, propuesta_ia=s.propuesta_ia, evaluacion_profe=s.evaluacion_profe,
        inicio=s.inicio, fin=s.fin,
        alias=s.alumno.alias if para_profe else None, grupo=s.alumno.grupo.nombre if para_profe else None,
    )


def _resumen(s: Sesion, para_profe: bool) -> SesionResumen:
    return SesionResumen(
        id=s.id, caso_titulo=s.caso_titulo, estado=s.estado, inicio=s.inicio,
        puntos_ia=_total_ia(s), puntos_profe=_total_profe(s), puntos_max=_max(s),
        alias=s.alumno.alias if para_profe else None, grupo=s.alumno.grupo.nombre if para_profe else None,
    )


def _sesion_visible(db: Session, sesion_id: int, u: Usuario) -> Sesion:
    s = db.get(Sesion, sesion_id)
    if s:
        if u.rol == "alumno" and s.alumno_id == u.alumno.id:
            return s
        if u.rol == "profe" and s.alumno.grupo.profesor_id == u.profesor.id:
            return s
    raise HTTPException(404, "Práctica no encontrada.")


def _sesion_propia_en_curso(db: Session, sesion_id: int, alumno: Alumno) -> Sesion:
    s = db.get(Sesion, sesion_id)
    if not s or s.alumno_id != alumno.id:
        raise HTTPException(404, "Práctica no encontrada.")
    if s.estado != "en_curso":
        raise HTTPException(409, "Esta práctica ya está terminada.")
    return s


# ---------- alumnado ----------

@router.post("/sesiones", response_model=SesionOut)
def empezar(d: NuevaSesion, alumno: Alumno = Depends(solo_alumno), db: Session = Depends(get_db)):
    caso = db.get(Caso, d.caso_id)
    if not caso or not caso.publicado:
        raise HTTPException(404, "Ese caso no está disponible.")
    s = Sesion(alumno_id=alumno.id, caso_id=caso.id, caso_titulo=caso.titulo, rubrica=list(caso.rubrica),
               idioma=d.idioma, mensajes=[{"r": "cliente", "t": caso.saludo or "Hola, buenos días."}])
    db.add(s)
    db.commit()
    return _out(s, False)


@router.get("/sesiones", response_model=list[SesionResumen])
def mis_sesiones(alumno: Alumno = Depends(solo_alumno), db: Session = Depends(get_db)):
    q = select(Sesion).where(Sesion.alumno_id == alumno.id).order_by(Sesion.inicio.desc())
    return [_resumen(s, False) for s in db.scalars(q)]


@router.get("/sesiones/{sesion_id}", response_model=SesionOut)
def ver(sesion_id: int, u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return _out(_sesion_visible(db, sesion_id, u), u.rol == "profe")


@router.post("/sesiones/{sesion_id}/mensajes", response_model=SesionOut)
def enviar(sesion_id: int, d: NuevoMensaje, alumno: Alumno = Depends(solo_alumno), db: Session = Depends(get_db)):
    cfg = get_settings()
    s = _sesion_propia_en_curso(db, sesion_id, alumno)
    texto = d.texto.strip()
    if len(texto) > cfg.max_caracteres_mensaje:
        raise HTTPException(422, f"El mensaje es demasiado largo (máximo {cfg.max_caracteres_mensaje} caracteres).")
    if len(s.mensajes) >= cfg.max_mensajes_sesion:
        raise HTTPException(409, "La conversación ya es muy larga. Termina la práctica para ver la valoración.")
    consumir_mensaje_ia(alumno.id)

    turnos = [{"role": "user", "content": prompts.INICIO_ESCENA}]
    for m in s.mensajes:
        if m["r"] != "pista":
            turnos.append({"role": "assistant" if m["r"] == "cliente" else "user", "content": m["t"]})
    turnos.append({"role": "user", "content": texto})

    respuesta = get_ia().responder_cliente(prompts.sistema_cliente(s.caso.personaje, s.caso.situacion, s.idioma), turnos)
    s.mensajes = [*s.mensajes, {"r": "alumno", "t": texto}, {"r": "cliente", "t": respuesta}]
    db.commit()
    return _out(s, False)


@router.post("/sesiones/{sesion_id}/pista", response_model=SesionOut)
def pedir_pista(sesion_id: int, alumno: Alumno = Depends(solo_alumno), db: Session = Depends(get_db)):
    s = _sesion_propia_en_curso(db, sesion_id, alumno)
    consumir_mensaje_ia(alumno.id)
    texto = get_ia().pista(prompts.pista(s.rubrica, s.mensajes, s.idioma))
    s.mensajes = [*s.mensajes, {"r": "pista", "t": texto}]
    s.pistas += 1
    db.commit()
    return _out(s, False)


@router.post("/sesiones/{sesion_id}/terminar", response_model=SesionOut)
def terminar(sesion_id: int, alumno: Alumno = Depends(solo_alumno), db: Session = Depends(get_db)):
    s = _sesion_propia_en_curso(db, sesion_id, alumno)
    if not any(m["r"] == "alumno" for m in s.mensajes):
        raise HTTPException(409, "Escribe al menos una respuesta al cliente antes de terminar.")
    consumir_mensaje_ia(alumno.id)
    bruto = get_ia().evaluar(prompts.evaluacion(s.rubrica, s.mensajes, s.idioma))

    recibidos = {c.get("id"): c for c in bruto.get("criterios", []) if isinstance(c, dict)}
    criterios = []
    for r in s.rubrica:
        c = recibidos.get(r["id"], {})
        maximo = float(r["puntos"])
        try:
            p = max(0.0, min(maximo, float(c.get("puntos", 0))))
        except (TypeError, ValueError):
            p = 0.0
        nivel = c.get("nivel") if c.get("nivel") in NIVELES else ("logrado" if p >= maximo else "parcial" if p > 0 else "no_logrado")
        criterios.append({"id": r["id"], "nivel": nivel, "puntos": p, "evidencia": str(c.get("evidencia", ""))[:500]})

    s.propuesta_ia = {
        "criterios": criterios,
        "fortalezas": str(bruto.get("fortalezas", ""))[:800],
        "mejorar": str(bruto.get("mejorar", ""))[:800],
        "modelo": f"{get_settings().ia_nombre} sobre {get_settings().ia_modelo_base}",
        "fecha": datetime.now(timezone.utc).isoformat(),
    }
    s.estado = "entregada"
    s.fin = datetime.now(timezone.utc)
    db.commit()
    return _out(s, False)


# ---------- profesorado ----------

@router.get("/entregas", response_model=list[SesionResumen])
def entregas(estado: str | None = None, grupo_id: int | None = None,
             profe: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    q = (select(Sesion).join(Alumno).join(Grupo).where(Grupo.profesor_id == profe.id)
         .order_by(Sesion.inicio.desc()).limit(500))
    if estado:
        q = q.where(Sesion.estado == estado)
    if grupo_id:
        q = q.where(Grupo.id == grupo_id)
    return [_resumen(s, True) for s in db.scalars(q)]


@router.put("/sesiones/{sesion_id}/nota", response_model=SesionOut)
def poner_nota(sesion_id: int, d: NotaProfe, profe: Profesor = Depends(solo_profe), db: Session = Depends(get_db)):
    s = _sesion_visible(db, sesion_id, Usuario("profe", profesor=profe))
    if s.estado == "en_curso":
        raise HTTPException(409, "El alumno todavía no ha terminado esta práctica.")
    puntos = {}
    for r in s.rubrica:
        v = float(d.puntos.get(r["id"], 0))
        puntos[r["id"]] = max(0.0, min(float(r["puntos"]), v))
    s.evaluacion_profe = {"puntos": puntos, "comentario": d.comentario.strip(), "profesor": profe.nombre,
                          "fecha": datetime.now(timezone.utc).isoformat()}
    s.estado = "revisada"
    db.commit()
    return _out(s, True)
