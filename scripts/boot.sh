#!/data/data/com.termux/files/usr/bin/sh
# Lancé par Termux:Boot au démarrage du téléphone.
termux-wake-lock
cd "__APP_DIR__" || exit 1
exec python discord_images.py watch >> "$HOME/discord-images.log" 2>&1
