@echo off
rem Installe les dépendances puis lance la configuration (Windows).
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% --version >nul 2>nul || (
  echo Python n'est pas installé. Installe-le depuis https://www.python.org/downloads/
  echo en cochant "Add python.exe to PATH", puis relance ce fichier.
  pause
  exit /b 1
)
%PY% -m pip install --disable-pip-version-check -r requirements.txt || (pause & exit /b 1)
%PY% discord_images.py setup
pause
