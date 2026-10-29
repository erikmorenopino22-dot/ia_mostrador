"""Prueba de carga: simula a una clase practicando a la vez y mide si el
servidor responde a tiempo.

Uso (con Mostrador abierto, en el propio servidor o desde otro equipo de la red):

  .venv/bin/python -m scripts.prueba_carga --email profe@centro.es              (Linux / Mac)
  .venv\\Scripts\\python -m scripts.prueba_carga --email profe@centro.es         (Windows)

Opciones:
  --servidor URL     dirección de Mostrador (por defecto http://localhost:8000)
  --alumnos N        alumnado simulado a la vez (por defecto 25)
  --mensajes N       mensajes que envía cada uno (por defecto 4)
  --pausa S          segundos de media entre mensajes, lo que tarda en escribir (por defecto 15)
  --sin-valoracion   no pedir la valoración final (la parte que más carga la IA)
  --conservar        no borrar el grupo de prueba al terminar

Crea un grupo temporal «Prueba de carga», lo usa con alumnado ficticio y al
terminar lo borra con todas sus prácticas. Pide la contraseña del profesor
(o la lee de la variable MOSTRADOR_PASSWORD). Guarda el informe en un archivo.
"""
import argparse
import asyncio
import getpass
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import httpx

MENSAJES = [
    "Hola, buenos días. ¿En qué puedo ayudarle?",
    "¿Desde cuándo le pasa? ¿Tiene algún otro síntoma?",
    "¿Toma alguna otra medicación o tiene alguna alergia o enfermedad?",
    "Un momento, que lo consulto con el farmacéutico.",
    "Le explico: si en unos días no mejora o empeora, vaya a su médico. ¿Lo ha entendido bien?",
    "Muchas gracias por venir. Que se mejore.",
]

# Umbrales en segundos (percentil 90): (bien, aceptable)
UMBRAL_MENSAJE = (8, 20)
UMBRAL_VALORACION = (45, 90)


class Fallo(Exception):
    pass


async def peticion(cliente, metodo, ruta, token=None, **kw):
    cab = {"Authorization": f"Bearer {token}"} if token else {}
    r = await cliente.request(metodo, "/api" + ruta, headers=cab, **kw)
    if r.status_code >= 400:
        try:
            detalle = r.json().get("detail")
        except ValueError:
            detalle = None
        raise Fallo(f"{r.status_code}: {detalle or r.text[:120]}")
    return r.json()


async def alumno(n, cliente, args, codigo, casos, medidas, errores, avance):
    await asyncio.sleep(random.uniform(0, 10))  # no llegan todos en el mismo segundo
    try:
        tok = (await peticion(cliente, "POST", "/alumno/entrar",
                              json={"codigo": codigo, "alias": f"prueba-{n:02d}", "pin": "0000"}))["token"]
        caso = casos[n % len(casos)]
        sesion = await peticion(cliente, "POST", "/sesiones", tok, json={"caso_id": caso, "idioma": "es"})
    except Exception as e:
        errores["entrar"].append(str(e))
        return
    for i in range(args.mensajes):
        await asyncio.sleep(args.pausa * random.uniform(0.5, 1.5))
        t = time.perf_counter()
        try:
            await peticion(cliente, "POST", f"/sesiones/{sesion['id']}/mensajes", tok,
                           json={"texto": MENSAJES[i % len(MENSAJES)]})
            medidas["mensaje"].append(time.perf_counter() - t)
        except Exception as e:
            errores["mensaje"].append(str(e))
        avance["hechas"] += 1
    if not args.sin_valoracion:
        t = time.perf_counter()
        try:
            await peticion(cliente, "POST", f"/sesiones/{sesion['id']}/terminar", tok)
            medidas["valoracion"].append(time.perf_counter() - t)
        except Exception as e:
            errores["valoracion"].append(str(e))
        avance["hechas"] += 1


def percentil(valores, p):
    if not valores:
        return None
    v = sorted(valores)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


def veredicto(p90, total, fallos, umbral):
    if total == 0:
        return "SIN DATOS", "No se ha completado ninguna petición."
    if fallos / (total + fallos) > 0.05:
        return "INSUFICIENTE", f"Han fallado {fallos} de {total + fallos} peticiones."
    if p90 <= umbral[0]:
        return "BIEN", "El alumnado apenas notará la espera."
    if p90 <= umbral[1]:
        return "ACEPTABLE", "Se nota la espera, pero se puede trabajar."
    return "INSUFICIENTE", "Las esperas son demasiado largas para una clase."


async def principal(args, password):
    limites = httpx.Limits(max_connections=args.alumnos + 10)
    async with httpx.AsyncClient(base_url=args.servidor.rstrip("/"), timeout=300, limits=limites) as cliente:
        try:
            estado = await peticion(cliente, "GET", "/estado")
        except (httpx.HTTPError, Fallo) as e:
            sys.exit(f"No se puede conectar con Mostrador en {args.servidor}: {e}")
        if not estado["ia"].get("ok", False):
            sys.exit("La IA no está lista: " + estado["ia"].get("motivo", "") + "\nArréglalo antes de lanzar la prueba.")
        try:
            tp = (await peticion(cliente, "POST", "/profe/login", json={"email": args.email, "password": password}))["token"]
        except Fallo as e:
            sys.exit(f"No se ha podido entrar como profesor: {e}")

        casos = [c["id"] for c in await peticion(cliente, "GET", "/casos", tp) if c.get("publicado", True)]
        if not casos:
            sys.exit("No hay casos publicados para practicar.")
        grupo = await peticion(cliente, "POST", "/grupos", tp,
                               json={"nombre": f"Prueba de carga {datetime.now():%d/%m %H:%M}"})

        medidas, errores, avance = defaultdict(list), defaultdict(list), {"hechas": 0}
        total = args.alumnos * (args.mensajes + (0 if args.sin_valoracion else 1))
        print(f"\nSimulando {args.alumnos} alumnos con {args.mensajes} mensajes cada uno"
              f"{'' if args.sin_valoracion else ' y la valoración final'}.")
        print(f"Durará unos {int(args.mensajes * args.pausa / 60) + 1} a {int(args.mensajes * args.pausa * 1.5 / 60) + 3} minutos. No cierres esta ventana.\n")
        inicio = time.perf_counter()
        tareas = [asyncio.create_task(alumno(n, cliente, args, grupo["codigo"], casos, medidas, errores, avance))
                  for n in range(1, args.alumnos + 1)]
        try:
            while not all(t.done() for t in tareas):
                await asyncio.sleep(5)
                print(f"  {avance['hechas']} de {total} peticiones completadas…", end="\r", flush=True)
            await asyncio.gather(*tareas)
        finally:
            if not args.conservar:
                try:
                    await peticion(cliente, "POST", f"/grupos/{grupo['id']}/activo?activo=false", tp)
                    await peticion(cliente, "DELETE", f"/grupos/{grupo['id']}", tp)
                except Exception as e:
                    print(f"\nNo se ha podido borrar el grupo de prueba ({e}). Bórralo a mano desde la pestaña Grupos.")
        duracion = time.perf_counter() - inicio

    lineas = [f"Prueba de carga de Mostrador, {datetime.now():%d/%m/%Y %H:%M}",
              f"Servidor: {args.servidor}   IA: {estado['ia'].get('nombre', '?')} sobre {estado['ia'].get('base', '?')}",
              f"Alumnado simulado: {args.alumnos}   Mensajes por alumno: {args.mensajes}   Pausa media: {args.pausa} s",
              f"Duración total: {duracion / 60:.1f} min", ""]
    peor = "BIEN"
    orden = ["BIEN", "ACEPTABLE", "SIN DATOS", "INSUFICIENTE"]
    apartados = [("mensaje", "Respuesta del cliente", UMBRAL_MENSAJE)]
    if not args.sin_valoracion:
        apartados.append(("valoracion", "Valoración final", UMBRAL_VALORACION))
    for clave, nombre, umbral in apartados:
        v = medidas[clave]
        fallos = len(errores[clave])
        p50, p90 = percentil(v, 50), percentil(v, 90)
        nota, explicacion = veredicto(p90 or 0, len(v), fallos, umbral)
        if orden.index(nota) > orden.index(peor):
            peor = nota
        lineas.append(f"{nombre}: {nota}. {explicacion}")
        if v:
            lineas.append(f"  Normalmente {p50:.1f} s; 9 de cada 10 en menos de {p90:.1f} s; la más lenta {max(v):.1f} s"
                          f" (objetivo: menos de {umbral[0]} s; aceptable hasta {umbral[1]} s).")
        lineas.append(f"  Correctas: {len(v)}   Fallidas: {fallos}")
    if errores["entrar"]:
        lineas.append(f"Alumnos que no pudieron entrar: {len(errores['entrar'])}")
        peor = "INSUFICIENTE"
    todos = Counter(e for lista in errores.values() for e in lista)
    if todos:
        lineas += ["", "Errores más frecuentes:"] + [f"  {n} × {e}" for e, n in todos.most_common(5)]

    lineas += ["", "CONCLUSIÓN: " + {
        "BIEN": "el servidor aguanta esta carga. Se puede usar con un grupo de este tamaño.",
        "ACEPTABLE": "se puede usar, pero el alumnado notará esperas. Valora usar un modelo más pequeño o un equipo con tarjeta gráfica.",
        "INSUFICIENTE": "el servidor no aguanta esta carga. Prueba con menos alumnos a la vez (--alumnos), con el modelo gemma3:4b "
                        "(IA_MODELO_BASE en el archivo .env) o con un equipo con tarjeta gráfica.",
        "SIN DATOS": "la prueba no ha llegado a medir nada. Revisa los errores.",
    }[peor]]
    informe = "\n".join(lineas)
    print("\n\n" + informe)
    archivo = Path(f"prueba_carga_{datetime.now():%Y%m%d_%H%M}.txt")
    archivo.write_text(informe + "\n", encoding="utf-8")
    print(f"\nInforme guardado en {archivo.resolve()}")
    return peor


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="Simula a una clase usando Mostrador a la vez.")
    p.add_argument("--servidor", default="http://localhost:8000")
    p.add_argument("--email", required=True, help="correo de una cuenta de profesor")
    p.add_argument("--alumnos", type=int, default=25)
    p.add_argument("--mensajes", type=int, default=4)
    p.add_argument("--pausa", type=float, default=15)
    p.add_argument("--sin-valoracion", action="store_true")
    p.add_argument("--conservar", action="store_true")
    args = p.parse_args()
    password = os.environ.get("MOSTRADOR_PASSWORD") or getpass.getpass("Contraseña del profesor: ")
    resultado = asyncio.run(principal(args, password))
    sys.exit(0 if resultado in ("BIEN", "ACEPTABLE") else 1)


if __name__ == "__main__":
    main()
