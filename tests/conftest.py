import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["SECRET_KEY"] = "clave-de-pruebas-suficientemente-larga-1234"
os.environ["LIMITE_DIARIO_ALUMNO"] = "50"
os.environ["COPIAS_CARPETA"] = f"{_tmp}/copias"
sys.path.insert(0, str(Path(__file__).parent.parent))
