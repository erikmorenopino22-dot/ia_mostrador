from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---------- IA propia ----------
    # "local": la IA de Mostrador, ejecutándose en este equipo.
    # "fake":  respuestas simuladas, solo para pruebas.
    llm_provider: str = "local"

    # Nombre con el que se crea la IA propia en este equipo.
    ia_nombre: str = "mostrador"
    # Modelo abierto sobre el que se construye. Puede ser uno descargable
    # (gemma3:4b, gemma3:12b, gemma3:27b...) o uno entrenado por el centro
    # y cargado en el equipo (ver ENTRENAR_IA.md).
    ia_modelo_base: str = "gemma3:12b"
    ia_centro: str = "CIPFP Ausiàs March (València)"

    ollama_url: str = "http://localhost:11434"
    ollama_timeout: int = 240

    # ---------- Servidor ----------
    puerto: int = 8000
    database_url: str = "sqlite:///./mostrador.db"
    secret_key: str = "cambia-esto"
    token_horas: int = 12
    limite_diario_alumno: int = 150

    # Copias de seguridad automáticas (solo SQLite). COPIAS_HORAS=0 las desactiva.
    copias_carpeta: str = "copias"
    copias_horas: int = 24
    copias_conservar: int = 30

    max_caracteres_mensaje: int = 1200
    max_mensajes_sesion: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
