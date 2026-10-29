"""Modelo de datos.

Principio de minimización (RGPD): del alumnado solo se guarda un alias elegido
por el propio alumno y un PIN cifrado. Nada de correos, DNI ni necesidades
educativas: las adaptaciones de lectura se eligen en el navegador y no se
envían al servidor.
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class Profesor(Base):
    __tablename__ = "profesores"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(300))
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    grupos: Mapped[list["Grupo"]] = relationship(back_populates="profesor")


class Grupo(Base):
    __tablename__ = "grupos"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    codigo: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    profesor_id: Mapped[int] = mapped_column(ForeignKey("profesores.id"))
    profesor: Mapped[Profesor] = relationship(back_populates="grupos")
    alumnos: Mapped[list["Alumno"]] = relationship(back_populates="grupo")
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class Alumno(Base):
    __tablename__ = "alumnos"
    __table_args__ = (UniqueConstraint("grupo_id", "alias"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    alias: Mapped[str] = mapped_column(String(40))
    pin_hash: Mapped[str] = mapped_column(String(300))
    grupo_id: Mapped[int] = mapped_column(ForeignKey("grupos.id"), index=True)
    grupo: Mapped[Grupo] = relationship(back_populates="alumnos")
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class Caso(Base):
    __tablename__ = "casos"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    modulo: Mapped[str] = mapped_column(String(200), default="")
    situacion: Mapped[str] = mapped_column(Text, default="")
    personaje: Mapped[str] = mapped_column(Text, default="")  # nunca se envía al alumno
    saludo: Mapped[str] = mapped_column(Text, default="")
    rubrica: Mapped[list] = mapped_column(JSON, default=list)
    rubrica_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    publicado: Mapped[bool] = mapped_column(Boolean, default=True)
    actualizado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class Sesion(Base):
    """Una práctica de un alumno con un caso."""
    __tablename__ = "sesiones"
    id: Mapped[int] = mapped_column(primary_key=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("alumnos.id"), index=True)
    alumno: Mapped[Alumno] = relationship()
    caso_id: Mapped[str] = mapped_column(ForeignKey("casos.id"))
    caso: Mapped[Caso] = relationship()
    caso_titulo: Mapped[str] = mapped_column(String(200), default="")
    # Copia de la rúbrica al empezar: si la profesora la cambia después,
    # la práctica se sigue valorando con la rúbrica original.
    rubrica: Mapped[list] = mapped_column(JSON, default=list)
    idioma: Mapped[str] = mapped_column(String(4), default="es")
    estado: Mapped[str] = mapped_column(String(20), default="en_curso")  # en_curso | entregada | revisada
    mensajes: Mapped[list] = mapped_column(JSON, default=list)  # [{"r": "cliente"|"alumno"|"pista", "t": str}]
    pistas: Mapped[int] = mapped_column(Integer, default=0)
    propuesta_ia: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evaluacion_profe: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
