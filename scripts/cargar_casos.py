"""Carga o actualiza los casos de seed/casos.json en la base de datos.

Uso:  python -m scripts.cargar_casos [ruta.json]
"""
import json
import sys
from pathlib import Path

from app.db import Base, SessionLocal, engine
from app.models import Caso


def main():
    ruta = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent.parent / "seed" / "casos.json")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for d in datos:
            c = db.get(Caso, d["id"]) or Caso(id=d["id"])
            c.titulo, c.modulo, c.situacion = d["titulo"], d.get("modulo", ""), d.get("situacion", "")
            c.personaje, c.saludo, c.rubrica = d.get("personaje", ""), d.get("saludo", ""), d["rubrica"]
            c.rubrica_visible, c.publicado = d.get("rubricaVisible", True), d.get("publicado", True)
            db.merge(c)
        db.commit()
    print(f"{len(datos)} casos cargados.")


if __name__ == "__main__":
    main()
