#!/data/data/com.termux/files/usr/bin/bash
# Installe Discord Images dans Termux.
set -e
cd "$(dirname "$0")/.."

pkg update -y
pkg install -y python termux-api
pip install -r requirements.txt

# Donne à Termux l'accès au stockage du téléphone (une fenêtre d'autorisation s'ouvre).
termux-setup-storage

# Démarrage automatique au lancement du téléphone (nécessite l'app Termux:Boot).
mkdir -p ~/.termux/boot
sed "s#__APP_DIR__#$PWD#" scripts/boot.sh > ~/.termux/boot/discord-images.sh
chmod +x ~/.termux/boot/discord-images.sh

echo
echo "Installation terminée. Lance maintenant : python discord_images.py setup"
