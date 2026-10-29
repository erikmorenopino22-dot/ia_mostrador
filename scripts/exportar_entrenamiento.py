"""Exporta las prácticas revisadas por el profesorado como datos de entrenamiento
para ajustar la IA propia del centro (ver ENTRENAR_IA.md).

Uso:  python -m scripts.exportar_entrenamiento [carpeta_destino]

Genera, en formato de conversación JSONL (compatible con las herramientas
habituales de ajuste fino):
  valoracion.jsonl  La práctica y la rúbrica como entrada; la NOTA DEL PROFESORADO
                    como respuesta esperada. Enseña a la IA a valorar como lo
                    hace el equipo docente del centro. Es el conjunto más útil.
  cliente.jsonl     Conversaciones completas con el cliente simulado, para
                    reforzar cómo interpreta los casos del centro.
  resumen.txt       Cuántos ejemplos hay y cuánto coincide hoy la IA con el profesorado.

Anonimización: no se exporta ningún alias, grupo ni identificador, y el alias
del alumno se sustituye por [alumno] si aparece dentro de los mensajes. Aun así,
revisa los archivos antes de usarlos: un alumno pudo escribir datos personales.
"""
import json
import re
import sys
from pathlib import Path

from sqlalchemy import select

from app import prompts
from app.db import Base, SessionLocal, engine
from app.models import Sesion

UMBRAL_RECOMENDADO = 300


def anonimizar(texto: str, alias: str) -> str:
    if alias and len(alias) >= 2:
        texto = re.sub(re.escape(alias), "[alumno]", texto, flags=re.I)
        for parte in alias.split():
            if len(parte) >= 3:
                texto = re.sub(rf"\b{re.escape(parte)}\b", "[alumno]", texto, flags=re.I)
    return texto


def nivel(puntos: float, maximo: float) -> str:
    return "logrado" if puntos >= maximo else "parcial" if puntos > 0 else "no_logrado"


def main():
    destino = Path(sys.argv[1] if len(sys.argv) > 1 else "datos_entrenamiento")
    destino.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)

    n_val = n_cli = criterios_total = criterios_iguales = 0
    with SessionLocal() as db, \
            open(destino / "valoracion.jsonl", "w", encoding="utf-8") as f_val, \
            open(destino / "cliente.jsonl", "w", encoding="utf-8") as f_cli:
        for s in db.scalars(select(Sesion).where(Sesion.estado == "revisada").order_by(Sesion.id)):
            alias = s.alumno.alias
            mensajes = [{"r": m["r"], "t": anonimizar(m["t"], alias)} for m in s.mensajes]
            nota = s.evaluacion_profe or {}
            ia = {c["id"]: c for c in (s.propuesta_ia or {}).get("criterios", [])}

            # --- valoración: entrada = práctica + rúbrica; salida = criterio del profesorado ---
            criterios = []
            for r in s.rubrica:
                maximo = float(r["puntos"])
                p = float(nota.get("puntos", {}).get(r["id"], 0))
                propuesta = ia.get(r["id"])
                coincide = propuesta is not None and abs(float(propuesta["puntos"]) - p) < 1e-9
                criterios_total += 1
                criterios_iguales += coincide
                criterios.append({"id": r["id"], "nivel": nivel(p, maximo), "puntos": p,
                                  # La justificación de la IA solo se conserva si el profesorado le dio la razón.
                                  "evidencia": anonimizar(propuesta.get("evidencia", ""), alias) if coincide else ""})
            comentario = anonimizar(nota.get("comentario", ""), alias)
            propuesta_ia = s.propuesta_ia or {}
            respuesta = {"criterios": criterios,
                         "fortalezas": anonimizar(propuesta_ia.get("fortalezas", ""), alias),
                         "mejorar": comentario or anonimizar(propuesta_ia.get("mejorar", ""), alias)}
            f_val.write(json.dumps({"messages": [
                {"role": "user", "content": prompts.evaluacion(s.rubrica, mensajes, s.idioma)},
                {"role": "assistant", "content": json.dumps(respuesta, ensure_ascii=False)},
            ]}, ensure_ascii=False) + "\n")
            n_val += 1

            # --- cliente: la conversación tal como ocurrió ---
            turnos = [{"role": "system", "content": prompts.sistema_cliente(s.caso.personaje, s.caso.situacion, s.idioma)},
                      {"role": "user", "content": prompts.INICIO_ESCENA}]
            for m in mensajes:
                if m["r"] == "pista":
                    continue
                turnos.append({"role": "assistant" if m["r"] == "cliente" else "user", "content": m["t"]})
            if turnos[-1]["role"] == "user":
                turnos.pop()  # cada ejemplo termina en una respuesta del cliente
            if sum(t["role"] == "assistant" for t in turnos) >= 2:
                f_cli.write(json.dumps({"messages": turnos}, ensure_ascii=False) + "\n")
                n_cli += 1

    acuerdo = f"{100 * criterios_iguales / criterios_total:.0f} %" if criterios_total else "sin datos"
    resumen = f"""Datos de entrenamiento de la IA de Mostrador

Prácticas revisadas exportadas: {n_val}
Ejemplos de valoración:          {n_val}  (recomendado para empezar: {UMBRAL_RECOMENDADO} o más)
Ejemplos de cliente:             {n_cli}

Coincidencia actual entre la IA y el profesorado: {acuerdo} de los criterios.
Cuanto más baja sea, más puede mejorar la IA si se entrena con estos datos.

Antes de usarlos, revisa que no haya datos personales en los mensajes del alumnado.
"""
    (destino / "resumen.txt").write_text(resumen, encoding="utf-8")
    print(resumen)
    print(f"Archivos guardados en: {destino.resolve()}")


if __name__ == "__main__":
    main()
