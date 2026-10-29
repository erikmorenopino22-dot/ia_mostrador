"""Contraseñas y PIN (scrypt, librería estándar) y tokens JWT."""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from .config import get_settings

_N, _R, _P = 2**14, 8, 1


def hash_secreto(secreto: str) -> str:
    sal = os.urandom(16)
    h = hashlib.scrypt(secreto.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt$" + base64.b64encode(sal).decode() + "$" + base64.b64encode(h).decode()


def verificar_secreto(secreto: str, guardado: str) -> bool:
    try:
        _, sal_b64, h_b64 = guardado.split("$")
        sal, esperado = base64.b64decode(sal_b64), base64.b64decode(h_b64)
    except ValueError:
        return False
    h = hashlib.scrypt(secreto.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return hmac.compare_digest(h, esperado)


def crear_token(rol: str, sujeto_id: int) -> str:
    s = get_settings()
    ahora = datetime.now(timezone.utc)
    datos = {"rol": rol, "sub": str(sujeto_id), "iat": ahora, "exp": ahora + timedelta(hours=s.token_horas)}
    return jwt.encode(datos, s.secret_key, algorithm="HS256")


def leer_token(token: str) -> dict:
    return jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
