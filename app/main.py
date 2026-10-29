from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import copias
from .db import Base, engine
from .llm import ErrorIA
from .routers import auth, casos, grupos, inicio, sesiones

@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    copias.iniciar()
    yield


app = FastAPI(title="Mostrador", description="Simulador de atención en farmacia para FP", version="1.2.0",
              lifespan=ciclo_de_vida)

# Crea las tablas si no existen y prepara el primer arranque.
Base.metadata.create_all(engine)
inicio.preparar()

for r in (inicio.router, auth.router, grupos.router, casos.router, sesiones.router):
    app.include_router(r)


@app.exception_handler(ErrorIA)
def error_ia(_: Request, e: ErrorIA):
    return JSONResponse(status_code=502, content={"detail": str(e)})


@app.get("/api/salud")
def salud():
    return {"ok": True}


app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "static", html=True), name="static")
