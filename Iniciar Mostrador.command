#!/usr/bin/env bash
# Arranca Mostrador en Linux o macOS. Uso: ./iniciar.sh
cd "$(dirname "$0")" || exit 1

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Falta Python 3.10 o superior."
  echo "  Ubuntu/Debian/LliureX:  sudo apt install python3 python3-venv"
  echo "  macOS:                  descárgalo de https://www.python.org/downloads/"
  read -r -p "Pulsa Intro para cerrar." _; exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Preparando Mostrador por primera vez. Puede tardar unos minutos..."
  if ! "$PY" -m venv .venv; then
    echo "No se ha podido crear el entorno de Python. En Ubuntu/Debian/LliureX: sudo apt install python3-venv"
    read -r -p "Pulsa Intro para cerrar." _; exit 1
  fi
fi
if [ ! -f .venv/instalado.txt ]; then
  .venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt \
    || { echo "No se han podido instalar las librerías. Comprueba la conexión a internet."; read -r -p "Pulsa Intro para cerrar." _; exit 1; }
  echo ok > .venv/instalado.txt
fi

exec .venv/bin/python iniciar.py
