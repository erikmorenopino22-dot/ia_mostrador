from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LoginProfe(BaseModel):
    email: str
    password: str


class EntrarAlumno(BaseModel):
    codigo: str = Field(min_length=4, max_length=12)
    alias: str = Field(min_length=2, max_length=40)
    pin: str = Field(pattern=r"^\d{4,8}$")

    @field_validator("alias")
    @classmethod
    def limpiar_alias(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("El alias es demasiado corto.")
        return v


class Token(BaseModel):
    token: str
    rol: str
    nombre: str
    grupo: str | None = None


class CriterioRubrica(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    texto: str = Field(min_length=1, max_length=400)
    puntos: float = Field(ge=0, le=100)


class CasoEntrada(BaseModel):
    id: str | None = Field(default=None, pattern=r"^[a-z0-9\-]{2,80}$")
    titulo: str = Field(min_length=1, max_length=200)
    modulo: str = ""
    situacion: str = ""
    personaje: str = ""
    saludo: str = ""
    rubrica: list[CriterioRubrica] = Field(min_length=1)
    rubricaVisible: bool = True
    publicado: bool = True


class CasoAlumno(BaseModel):
    """Lo que ve el alumnado: sin la ficha oculta del personaje."""
    id: str
    titulo: str
    modulo: str
    situacion: str


class CasoCompleto(CasoAlumno):
    personaje: str
    saludo: str
    rubrica: list[CriterioRubrica]
    rubricaVisible: bool
    publicado: bool


class NuevaSesion(BaseModel):
    caso_id: str
    idioma: str = Field(default="es", pattern=r"^(es|va)$")


class NuevoMensaje(BaseModel):
    texto: str = Field(min_length=1)


class NotaProfe(BaseModel):
    puntos: dict[str, float]
    comentario: str = Field(default="", max_length=3000)


class SesionOut(BaseModel):
    id: int
    caso_id: str
    caso_titulo: str
    modulo: str
    situacion: str
    rubrica: list[CriterioRubrica]
    estado: str
    idioma: str
    pistas: int
    mensajes: list[dict]
    propuesta_ia: dict | None
    evaluacion_profe: dict | None
    inicio: datetime
    fin: datetime | None
    alias: str | None = None
    grupo: str | None = None


class SesionResumen(BaseModel):
    id: int
    caso_titulo: str
    estado: str
    inicio: datetime
    puntos_ia: float | None
    puntos_profe: float | None
    puntos_max: float
    alias: str | None = None
    grupo: str | None = None


class GrupoEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)


class GrupoOut(BaseModel):
    id: int
    nombre: str
    codigo: str
    activo: bool
    alumnos: int


class ResetPin(BaseModel):
    pin: str = Field(pattern=r"^\d{4,8}$")
