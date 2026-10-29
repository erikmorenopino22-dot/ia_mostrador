"""Arranca Mostrador en este equipo.

Lo ejecutan los lanzadores (Iniciar Mostrador.bat / iniciar.sh), que antes
preparan Python y las librerías. Hace lo siguiente:
  1. Crea el archivo .env la primera vez, con un secreto aleatorio.
  2. Comprueba que el motor de IA (Ollama) está en marcha y lo arranca si puede.
  3. Prepara la IA propia «mostrador»: descarga el modelo abierto de base
     (solo la primera vez) y crea sobre él la IA con su identidad.
  4. Muestra la dirección para el alumnado y abre el navegador.
"""
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
os.chdir(RAIZ)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def titulo(t):
    print("\n" + t)
    print("-" * len(t))


def esperar_y_salir(codigo=1):
    try:
        input("\nPulsa Intro para cerrar esta ventana.")
    except EOFError:
        pass
    sys.exit(codigo)


# ---------- 1. Configuración ----------
env = RAIZ / ".env"
if not env.exists():
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    texto = texto.replace("SECRET_KEY=cambia-esto", "SECRET_KEY=" + secrets.token_urlsafe(48))
    env.write_text(texto, encoding="utf-8")
    print("Configuración creada en el archivo .env")
else:
    # Archivos .env de versiones anteriores: se conserva el modelo elegido.
    texto = env.read_text(encoding="utf-8")
    if "IA_MODELO_BASE" not in texto:
        import re as _re
        anterior = _re.search(r"^OLLAMA_MODELO_CHAT=(\S+)", texto, _re.M)
        if anterior:
            env.write_text(texto.rstrip() + f"\nIA_MODELO_BASE={anterior.group(1)}\n", encoding="utf-8")

from app.config import get_settings  # noqa: E402  (lee el .env recién creado)

cfg = get_settings()


# ---------- 2 y 3. IA propia ----------
def ollama_get(ruta, timeout=3):
    with urllib.request.urlopen(cfg.ollama_url.rstrip("/") + ruta, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def ollama_activo():
    try:
        ollama_get("/api/tags")
        return True
    except Exception:
        return False


def instrucciones_ollama():
    print("\nNo se encuentra Ollama, el motor que ejecuta la IA de Mostrador en este equipo.")
    print("Instálalo una sola vez desde https://ollama.com/download")
    if sys.platform.startswith("linux"):
        print("En Linux también puedes escribir en una terminal:")
        print("    curl -fsSL https://ollama.com/install.sh | sh")
    print("Después vuelve a abrir Mostrador.")


def descargar_modelo(modelo):
    print(f"Descargando el modelo abierto «{modelo}». Solo pasa la primera vez y puede tardar un rato (varios GB).")
    req = urllib.request.Request(cfg.ollama_url.rstrip("/") + "/api/pull",
                                 data=json.dumps({"model": modelo, "stream": True}).encode(),
                                 headers={"Content-Type": "application/json"})
    ultimo = -1
    with urllib.request.urlopen(req, timeout=None) as r:
        for linea in r:
            if not linea.strip():
                continue
            d = json.loads(linea)
            if d.get("error"):
                raise RuntimeError(d["error"])
            total, hecho = d.get("total"), d.get("completed")
            if total and hecho:
                pct = int(hecho * 100 / total)
                if pct != ultimo and pct % 5 == 0:
                    print(f"  {pct}%", end="\r", flush=True)
                    ultimo = pct
    print("  Descargado.             ")


if cfg.llm_provider != "fake":
    titulo("Preparando la IA de Mostrador")
    if not ollama_activo():
        ejecutable = shutil.which("ollama")
        if not ejecutable and sys.platform == "win32":
            # Instalado con el instalador oficial, pero esta ventana aún no lo ve en el PATH
            posible = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
            ejecutable = str(posible) if posible.exists() else None
        if not ejecutable:
            instrucciones_ollama()
            esperar_y_salir()
        print("Arrancando el motor de IA…")
        entorno = {**os.environ, "OLLAMA_NUM_PARALLEL": os.environ.get("OLLAMA_NUM_PARALLEL", "4")}
        opciones = {"creationflags": 0x08000000} if sys.platform == "win32" else {"start_new_session": True}
        subprocess.Popen([ejecutable, "serve"], env=entorno, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **opciones)
        for _ in range(30):
            time.sleep(1)
            if ollama_activo():
                break
        else:
            print("El motor de IA no ha arrancado. Abre Ollama desde el menú de aplicaciones y vuelve a abrir Mostrador.")
            esperar_y_salir()

    instalados = set()
    for m in ollama_get("/api/tags").get("models", []):
        instalados |= {m["name"], m["name"].removesuffix(":latest")}
    if cfg.ia_modelo_base not in instalados:
        try:
            descargar_modelo(cfg.ia_modelo_base)
        except (urllib.error.URLError, RuntimeError) as e:
            print(f"\nNo se ha podido descargar el modelo base: {e}")
            print("La primera vez hace falta conexión a internet. Si usas un modelo entrenado por el centro,")
            print("comprueba que IA_MODELO_BASE en el archivo .env tiene el nombre con el que lo cargaste.")
            esperar_y_salir()

    from app import ia_propia  # noqa: E402

    try:
        resultado = ia_propia.crear_o_actualizar()
    except Exception as e:
        print(f"\nNo se ha podido preparar la IA de Mostrador: {e}")
        esperar_y_salir()
    print(f"IA «{cfg.ia_nombre}» ({resultado}), construida sobre «{cfg.ia_modelo_base}».")


# ---------- 4. Servidor ----------
import socket  # noqa: E402

with socket.socket() as prueba:
    try:
        prueba.bind(("0.0.0.0", cfg.puerto))
    except OSError:
        print(f"\nEl puerto {cfg.puerto} ya está en uso. Puede que Mostrador ya esté abierto en otra ventana:")
        print(f"prueba a abrir http://localhost:{cfg.puerto} en el navegador. Si no, cambia PUERTO en el archivo .env")
        esperar_y_salir()

from app.main import app  # noqa: E402
from app.routers.inicio import codigo_configuracion, direcciones  # noqa: E402

local = f"http://localhost:{cfg.puerto}"
red = direcciones()
print("\n" + "=" * 64)
print("  MOSTRADOR está en marcha. No cierres esta ventana mientras se use.")
print("=" * 64)
print(f"\n  En este ordenador:        {local}")
if red:
    print(f"  Alumnado (misma red):     {red[0]}")
else:
    print("  Este equipo no está conectado a ninguna red: solo funciona desde aquí.")
codigo = codigo_configuracion()
if codigo:
    print(f"\n  Primera vez: código de configuración  {codigo}")
    print("  (te lo pedirá la página para crear la cuenta de profesorado)")
print("\n  Para apagarlo, cierra esta ventana o pulsa Ctrl+C.\n")

try:
    webbrowser.open(local)
except Exception:
    pass

import uvicorn  # noqa: E402

uvicorn.run(app, host="0.0.0.0", port=cfg.puerto, log_level="warning")
