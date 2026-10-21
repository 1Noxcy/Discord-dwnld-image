@echo off
rem Lance Discord Images en arrière-plan à chaque démarrage de Windows.
chcp 65001 >nul
cd /d "%~dp0"
where pyw >nul 2>nul && (set PYW=pyw) || (set PYW=pythonw)
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
(
  echo @echo off
  echo cd /d "%CD%"
  echo start "" %PYW% discord_images.py --log-file discord-images.log watch --backfill-days 3
) > "%STARTUP%\discord-images.bat"
start "" %PYW% discord_images.py --log-file discord-images.log watch --backfill-days 3
echo Discord Images tourne maintenant en arrière-plan et démarrera avec Windows.
echo Journal : %CD%\discord-images.log
echo Pour désactiver : supprime "%STARTUP%\discord-images.bat"
pause
