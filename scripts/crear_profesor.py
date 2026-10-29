"""Crea (o actualiza) una cuenta de profesor.

Uso:  python -m scripts.crear_profesor correo@centro.es "Nombre Apellido"
"""
import getpass
import sys

from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import Profesor
from app.security import hash_secreto


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    email, nombre = sys.argv[1].strip().lower(), sys.argv[2].strip()
    pw = getpass.getpass("Contraseña (mínimo 10 caracteres): ")
    if len(pw) < 10 or pw != getpass.getpass("Repítela: "):
        print("Las contraseñas no coinciden o son demasiado cortas.")
        sys.exit(1)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        p = db.scalar(select(Profesor).where(Profesor.email == email))
        if p:
            p.nombre, p.password_hash = nombre, hash_secreto(pw)
            print("Cuenta actualizada.")
        else:
            db.add(Profesor(email=email, nombre=nombre, password_hash=hash_secreto(pw)))
            print("Cuenta creada.")
        db.commit()


if __name__ == "__main__":
    main()
