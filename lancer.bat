@echo off
rem Télécharge les images des 3 derniers jours puis les nouvelles en temps réel.
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% discord_images.py watch --backfill-days 3
pause
