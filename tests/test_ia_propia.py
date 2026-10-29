"""La IA propia: capa de uso y creación en el motor local, contra un Ollama simulado."""
import json

import httpx
import pytest

from app import ia_propia
from app.llm import ErrorIA, IALocal


def ia_con(manejador):
    ia = IALocal()
    ia.c = httpx.Client(transport=httpx.MockTransport(manejador))
    return ia


def test_usa_la_ia_propia_y_limpia_la_respuesta():
    def h(req):
        cuerpo = json.loads(req.content)
        assert cuerpo["model"] == "mostrador"
        assert cuerpo["messages"][0]["role"] == "system" and cuerpo["stream"] is False
        return httpx.Response(200, json={"message": {"content": "<think>pienso</think>Cliente: Pues tomo enalapril."}})
    assert ia_con(h).responder_cliente("sistema", [{"role": "user", "content": "¿Toma algo?"}]) == "Pues tomo enalapril."


def test_valoracion_con_esquema_y_reintento():
    llamadas = []

    def h(req):
        assert json.loads(req.content)["format"]["type"] == "object"
        llamadas.append(1)
        if len(llamadas) == 1:
            return httpx.Response(200, json={"message": {"content": "no es json"}})
        return httpx.Response(200, json={"message": {"content": json.dumps(
            {"criterios": [{"id": "c1", "nivel": "logrado", "puntos": 1, "evidencia": "Saluda"}], "fortalezas": "a", "mejorar": "b"})}})
    assert ia_con(h).evaluar("rúbrica...")["criterios"][0]["id"] == "c1" and len(llamadas) == 2


def test_errores_claros():
    with pytest.raises(ErrorIA, match="no está preparada"):
        ia_con(lambda req: httpx.Response(404, json={"error": "model not found"})).pista("x")

    def caido(req):
        raise httpx.ConnectError("no")
    with pytest.raises(ErrorIA, match="no está en marcha"):
        ia_con(caido).pista("x")


class OllamaSimulado:
    def __init__(self, modelos):
        self.modelos = {m: {} for m in modelos}
        self.creaciones = []

    def __call__(self, req):
        if req.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": m + ":latest" if ":" not in m else m} for m in self.modelos]})
        cuerpo = json.loads(req.content)
        if req.url.path == "/api/show":
            return httpx.Response(200, json=self.modelos[cuerpo["model"]])
        if req.url.path == "/api/create":
            self.creaciones.append(cuerpo)
            self.modelos[cuerpo["model"]] = {"system": cuerpo["system"], "license": cuerpo["license"]}
            return httpx.Response(200, json={"status": "success"})
        return httpx.Response(404)


def test_crea_y_mantiene_la_ia_propia():
    ollama = OllamaSimulado(["gemma3:12b"])
    c = httpx.Client(transport=httpx.MockTransport(ollama))
    assert ia_propia.crear_o_actualizar(c) == "creada"
    creada = ollama.creaciones[0]
    assert creada["model"] == "mostrador" and creada["from"] == "gemma3:12b"
    assert "Eres Mostrador" in creada["system"] and "No eres ChatGPT, ni Claude" in creada["system"]
    assert ia_propia.crear_o_actualizar(c) == "al día" and len(ollama.creaciones) == 1

    ollama.modelos["mostrador"]["system"] = "identidad antigua"
    assert ia_propia.crear_o_actualizar(c) == "actualizada"


def test_sin_modelo_base():
    c = httpx.Client(transport=httpx.MockTransport(OllamaSimulado([])))
    with pytest.raises(RuntimeError, match="modelo base"):
        ia_propia.crear_o_actualizar(c)


def test_modelfile():
    texto = ia_propia.modelfile()
    assert texto.startswith("FROM gemma3:12b") and 'SYSTEM """Eres Mostrador' in texto
