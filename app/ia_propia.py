"""La IA propia de Mostrador.

Se construye en el propio equipo a partir de un modelo de pesos abiertos y
queda registrada en Ollama con su nombre ("mostrador" por defecto), con su
identidad y sus parámetros. Funciona sin internet y sin servicios externos.

Hoy parte de un modelo abierto general. Cuando el centro tenga prácticas
revisadas suficientes, se puede ajustar con ellas y usar ese modelo entrenado
como base (ver ENTRENAR_IA.md y scripts/exportar_entrenamiento.py).
"""
import httpx

from .config import get_settings

VERSION = "1"


def identidad() -> str:
    centro = get_settings().ia_centro
    return f"""Eres Mostrador (versión {VERSION}), la inteligencia artificial educativa del ciclo de Técnico en Farmacia y Parafarmacia del {centro}. Funcionas íntegramente en un ordenador del propio centro, sobre un modelo de lenguaje de pesos abiertos, sin depender de ningún servicio externo.

Tu propósito es ayudar al alumnado a aprender la atención en la oficina de farmacia: haces de cliente en simulaciones, das pistas y propones valoraciones según las rúbricas del profesorado.

Principios:
- Eres una herramienta de aprendizaje. Nunca sustituyes al farmacéutico ni das consejo sanitario real a personas reales.
- La nota final siempre la decide el profesorado; tus valoraciones son propuestas.
- Hablas en castellano o en valenciano, con frases claras y sencillas, y te adaptas a quien tienes delante.
- Tratas a todo el mundo con respeto y paciencia, sin juzgar.
- Si te preguntan quién eres, te presentas como Mostrador, la IA del ciclo. No eres ChatGPT, ni Claude, ni Gemini, ni ningún otro asistente comercial."""


PARAMETROS = {"temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.1, "num_ctx": 8192}


def modelfile() -> str:
    """Texto equivalente en formato Modelfile, para quien prefiera usar la consola de Ollama."""
    s = get_settings()
    lineas = [f"FROM {s.ia_modelo_base}", ""]
    lineas += [f"PARAMETER {k} {v}" for k, v in PARAMETROS.items()]
    lineas += ["", 'SYSTEM """' + identidad() + '"""', ""]
    return "\n".join(lineas)


def _instalados(c: httpx.Client, url: str) -> set[str]:
    nombres = set()
    for m in c.get(url + "/api/tags", timeout=5).json().get("models", []):
        nombres.add(m["name"])
        if m["name"].endswith(":latest"):
            nombres.add(m["name"][: -len(":latest")])
    return nombres


def estado() -> dict:
    """¿Está lista la IA propia en este equipo?"""
    s = get_settings()
    url = s.ollama_url.rstrip("/")
    try:
        with httpx.Client() as c:
            instalados = _instalados(c, url)
    except Exception:
        return {"ok": False, "motivo": "El motor de IA (Ollama) no está en marcha."}
    if s.ia_nombre not in instalados:
        return {"ok": False, "motivo": f"La IA «{s.ia_nombre}» todavía no está creada en este equipo. Abre Mostrador con el lanzador para prepararla."}
    return {"ok": True, "nombre": s.ia_nombre, "base": s.ia_modelo_base}


def crear_o_actualizar(c: httpx.Client | None = None) -> str:
    """Crea la IA propia sobre el modelo base, o la actualiza si su identidad
    o su base han cambiado. Devuelve "creada", "actualizada" o "al día".

    El modelo base tiene que estar ya en el equipo."""
    s = get_settings()
    url = s.ollama_url.rstrip("/")
    propio = c is None
    c = c or httpx.Client(timeout=httpx.Timeout(600, connect=5))
    try:
        instalados = _instalados(c, url)
        if s.ia_modelo_base not in instalados:
            raise RuntimeError(f"Falta el modelo base «{s.ia_modelo_base}» en este equipo.")
        firma = f"base={s.ia_modelo_base}"
        if s.ia_nombre in instalados:
            info = c.post(url + "/api/show", json={"model": s.ia_nombre}).json()
            if info.get("system", "").strip() == identidad().strip() and firma in (info.get("license") or ""):
                return "al día"
            resultado = "actualizada"
        else:
            resultado = "creada"
        r = c.post(url + "/api/create", json={
            "model": s.ia_nombre,
            "from": s.ia_modelo_base,
            "system": identidad(),
            "parameters": PARAMETROS,
            "license": f"IA educativa Mostrador. {firma}. Sujeta a la licencia del modelo base.",
            "stream": False,
        })
        if r.status_code >= 400:
            raise RuntimeError(r.json().get("error", "error al crear la IA"))
        return resultado
    finally:
        if propio:
            c.close()
