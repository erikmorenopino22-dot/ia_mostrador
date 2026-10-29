"""Prepara la IA propia de Mostrador sin abrir la aplicación.

Uso:
  python -m scripts.preparar_ia               descarga la base si falta y crea o actualiza la IA
  python -m scripts.preparar_ia --modelfile   muestra la IA en formato Modelfile de Ollama

Lo usa la instalación con Docker; con los lanzadores de doble clic no hace falta.
"""
import json
import sys

import httpx

from app import ia_propia
from app.config import get_settings


def main():
    if "--modelfile" in sys.argv:
        print(ia_propia.modelfile())
        return
    s = get_settings()
    url = s.ollama_url.rstrip("/")
    with httpx.Client(timeout=httpx.Timeout(None, connect=10)) as c:
        nombres = {m["name"].removesuffix(":latest") for m in c.get(url + "/api/tags").json().get("models", [])}
        if s.ia_modelo_base not in nombres:
            print(f"Descargando el modelo base «{s.ia_modelo_base}»…")
            with c.stream("POST", url + "/api/pull", json={"model": s.ia_modelo_base}) as r:
                for linea in r.iter_lines():
                    if linea and (d := json.loads(linea)).get("error"):
                        sys.exit("Error: " + d["error"])
        print(f"IA «{s.ia_nombre}»: {ia_propia.crear_o_actualizar(c)}")


if __name__ == "__main__":
    main()
