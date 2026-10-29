"""Acceso a la IA de Mostrador.

Toda la IA se ejecuta en el equipo del centro (ver ia_propia.py). Para las
pruebas automáticas hay una versión simulada (LLM_PROVIDER=fake).
"""
import json
import re
from functools import lru_cache

from . import ia_propia
from .config import get_settings
from .prompts import ESQUEMA_VALORACION


class ErrorIA(Exception):
    """El modelo no ha podido responder."""


class IALocal:
    """La IA propia de Mostrador, servida por el motor local Ollama.

    Todo se ejecuta en el ordenador del centro: las conversaciones no salen
    de la red local, no hace falta internet y no tiene coste por uso.
    """

    def __init__(self):
        import httpx

        s = get_settings()
        self._httpx = httpx
        self.url = s.ollama_url.rstrip("/")
        self.modelo_chat = s.ia_nombre
        self.modelo_eval = s.ia_nombre
        self.c = httpx.Client(timeout=httpx.Timeout(s.ollama_timeout, connect=5))

    def _chat(self, modelo: str, mensajes: list[dict], formato: dict | None = None, max_tokens: int = 400) -> str:
        cuerpo = {
            "model": modelo,
            "messages": mensajes,
            "stream": False,
            "keep_alive": "30m",  # mantiene el modelo cargado entre mensajes
            "options": {"temperature": 0.2 if formato else 0.7, "num_predict": max_tokens, "num_ctx": 8192},
        }
        if formato:
            cuerpo["format"] = formato
        try:
            r = self.c.post(self.url + "/api/chat", json=cuerpo)
        except self._httpx.ConnectError as e:
            raise ErrorIA("La IA de Mostrador no está en marcha. Pide a quien administra el equipo que vuelva a abrir Mostrador.") from e
        except self._httpx.TimeoutException as e:
            raise ErrorIA("La IA está tardando demasiado. Puede que haya mucha gente a la vez: espera un momento y vuelve a intentarlo.") from e
        if r.status_code == 404:
            raise ErrorIA(f"La IA «{modelo}» no está preparada en este equipo. Cierra Mostrador y vuelve a abrirlo con el lanzador.")
        if r.status_code >= 400:
            raise ErrorIA("La IA ha dado un error. Inténtalo de nuevo.")
        texto = (r.json().get("message") or {}).get("content", "")
        # Algunos modelos "razonan" antes de responder; esa parte no se muestra.
        texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.S).strip()
        return texto

    def responder_cliente(self, sistema: str, mensajes: list[dict]) -> str:
        texto = self._chat(self.modelo_chat, [{"role": "system", "content": sistema}, *mensajes])
        texto = re.sub(r"^\s*(Cliente|Clienta)\s*:\s*", "", texto)
        if not texto:
            raise ErrorIA("El cliente no ha respondido. Prueba a escribir tu mensaje de otra forma.")
        return texto

    def pista(self, prompt: str) -> str:
        texto = self._chat(self.modelo_chat, [{"role": "user", "content": prompt}], max_tokens=250)
        return texto or "Piensa qué más necesitas saber del cliente antes de recomendar nada."

    def evaluar(self, prompt: str) -> dict:
        esquema = ESQUEMA_VALORACION
        prompt += "\n\nResponde solo con un objeto JSON con los campos: criterios (lista con id, nivel, puntos, evidencia), fortalezas y mejorar."
        for _ in range(2):  # los modelos pequeños a veces fallan el formato: se reintenta una vez
            texto = self._chat(self.modelo_eval, [{"role": "user", "content": prompt}], formato=esquema, max_tokens=2500)
            try:
                datos = json.loads(texto[texto.find("{"): texto.rfind("}") + 1])
                if isinstance(datos.get("criterios"), list):
                    return datos
            except ValueError:
                pass
        raise ErrorIA("La valoración no ha llegado completa. Pulsa otra vez en Terminar.")

    def estado(self) -> dict:
        return ia_propia.estado()


class FakeIA:
    """Respuestas simuladas: para pruebas y para enseñar la app sin gastar."""

    def responder_cliente(self, sistema: str, mensajes: list[dict]) -> str:
        n = sum(1 for m in mensajes if m["role"] == "user")
        return f"(Cliente simulado) Vale, entiendo. ¿Y qué más me recomiendas? [{n}]"

    def pista(self, prompt: str) -> str:
        return "(Pista simulada) Pregunta al cliente si toma alguna otra medicación."

    def evaluar(self, prompt: str) -> dict:
        ids = [l.split(" | ")[0] for l in prompt.splitlines() if " | " in l and not l.startswith("Rúbrica")]
        return {
            "criterios": [{"id": i, "nivel": "parcial", "puntos": 1, "evidencia": "Valoración simulada."} for i in ids],
            "fortalezas": "Has atendido con amabilidad.",
            "mejorar": "Haz más preguntas antes de recomendar un producto.",
        }


@lru_cache
def get_ia():
    return FakeIA() if get_settings().llm_provider == "fake" else IALocal()


def estado_ia() -> dict:
    ia = get_ia()
    return ia.estado() if hasattr(ia, "estado") else {"ok": True}
