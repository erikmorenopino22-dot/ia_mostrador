@echo off
chcp 65001 >nul
title Mostrador
cd /d "%~dp0"

rem ---- Python ----
set "PY="
rem Python portable incluido en la carpeta, si existe
if exist "%~dp0python\python.exe" set "PY="%~dp0python\python.exe""
if not defined PY ( where py >nul 2>nul && set "PY=py -3" )
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo.
  echo Falta Python en este equipo.
  echo Se va a abrir la pagina de descarga. Al instalarlo, marca la casilla
  echo "Add python.exe to PATH" y despues vuelve a abrir Mostrador.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)

rem ---- Entorno y librerias (solo la primera vez) ----
if not exist ".venv\Scripts\python.exe" (
  echo Preparando Mostrador por primera vez. Puede tardar unos minutos...
  %PY% -m venv .venv || ( echo No se ha podido crear el entorno de Python. & pause & exit /b 1 )
)
if not exist ".venv\instalado.txt" (
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || ( echo No se han podido instalar las librerias. Comprueba la conexion a internet. & pause & exit /b 1 )
  echo ok> ".venv\instalado.txt"
)

".venv\Scripts\python.exe" iniciar.py
pause
