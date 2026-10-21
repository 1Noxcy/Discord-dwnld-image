#!/usr/bin/env python3
"""Télécharge automatiquement les images reçues en message privé sur Discord.

Fonctionne sur Android via Termux. L'outil est en lecture seule : il écoute
tes conversations privées et enregistre les images dans la galerie, il
n'envoie jamais de message.

Commandes :
    setup     configure le token, le dossier et les conversations à suivre
    select    choisit les conversations à suivre
    dms       liste tes conversations privées
    watch     télécharge en temps réel les nouvelles images
    backfill  télécharge les images déjà présentes dans l'historique
"""

import argparse
import getpass
import hashlib
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
import websocket

API = "https://discord.com/api/v10"
GATEWAY = "wss://gateway.discord.gg"
GATEWAY_QUERY = "/?v=10&encoding=json"
DISCORD_EPOCH_MS = 1420070400000
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"
)

CHANNEL_DM = 1
CHANNEL_GROUP_DM = 3

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif", ".avif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}

# Codes de fermeture du gateway après lesquels il ne sert à rien de réessayer.
FATAL_CLOSE_CODES = {
    4004: "token invalide (il a peut-être changé : reconnecte-toi et récupère-le à nouveau)",
    4010: "shard invalide",
    4011: "sharding requis",
    4012: "version d'API invalide",
    4013: "intents invalides",
    4014: "intents non autorisés",
}

DEFAULT_CONFIG = {
    "token": "",
    "download_dir": "/storage/emulated/0/Pictures/Discord",
    "channels": [],
    "include_group_dms": True,
    "include_own_messages": False,
    "include_videos": False,
    "include_embeds": True,
    "subfolder_per_conversation": True,
    "media_scan": True,
}

log = logging.getLogger("discord-images")


class FatalError(Exception):
    pass


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def load_config(path):
    cfg = dict(DEFAULT_CONFIG)
    if path.exists():
        with path.open(encoding="utf-8") as f:
            cfg.update(json.load(f))
    if os.environ.get("DISCORD_TOKEN"):
        cfg["token"] = os.environ["DISCORD_TOKEN"]
    cfg["channels"] = [str(c) for c in cfg.get("channels", [])]
    return cfg


def save_config(path, cfg):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def require_token(cfg):
    token = cfg.get("token", "").strip()
    if not token:
        raise FatalError("Aucun token configuré. Lance d'abord : python discord_images.py setup")
    return token


# --------------------------------------------------------------------------
# Fonctions utilitaires (sans réseau, testées dans tests/)
# --------------------------------------------------------------------------

def snowflake_time(snowflake):
    ms = (int(snowflake) >> 22) + DISCORD_EPOCH_MS
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def sanitize(name, max_len=80):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(" .")
    return name[:max_len] or "sans_nom"


def display_name(user):
    return user.get("global_name") or user.get("username") or user.get("id", "inconnu")


def conversation_name(channel):
    if channel.get("name"):
        return channel["name"]
    recipients = channel.get("recipients") or []
    if recipients:
        return ", ".join(display_name(u) for u in recipients)
    return channel.get("id", "inconnu")


def media_kind(filename, content_type=None):
    """Renvoie "image", "video" ou None."""
    if content_type:
        if content_type.startswith("image/"):
            return "image"
        if content_type.startswith("video/"):
            return "video"
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return None


def _wanted(kind, cfg):
    return kind == "image" or (kind == "video" and cfg.get("include_videos"))


def extract_media(msg, cfg):
    """Liste des médias d'un message : tuples (url, clé unique, nom de fichier)."""
    items = []
    for att in msg.get("attachments") or []:
        filename = att.get("filename", "fichier")
        if _wanted(media_kind(filename, att.get("content_type")), cfg):
            items.append((att.get("url") or att.get("proxy_url"), att["id"], filename))

    if not cfg.get("include_embeds"):
        return items
    for embed in msg.get("embeds") or []:
        candidates = []
        if embed.get("image"):
            candidates.append(embed["image"])
        if embed.get("type") == "image" and embed.get("thumbnail"):
            candidates.append(embed["thumbnail"])
        if embed.get("type") == "gifv" and embed.get("video") and cfg.get("include_videos"):
            candidates.append(embed["video"])
        for media in candidates:
            url = media.get("url") or media.get("proxy_url")
            if not url:
                continue
            filename = Path(urlparse(url).path).name or "embed"
            kind = media_kind(filename, media.get("content_type")) or "image"
            if not _wanted(kind, cfg):
                continue
            key = hashlib.sha1(url.split("?")[0].encode()).hexdigest()[:12]
            items.append((url, key, filename))
            break  # une seule version (image ou miniature) par embed
    return items


def should_handle(msg, channel_type, cfg, my_id):
    """Décide si un message doit être traité selon la configuration."""
    if msg.get("guild_id"):
        return False  # message de serveur, pas un MP
    if channel_type not in (None, CHANNEL_DM, CHANNEL_GROUP_DM):
        return False
    if channel_type == CHANNEL_GROUP_DM and not cfg.get("include_group_dms"):
        return False
    if cfg.get("channels") and str(msg.get("channel_id")) not in cfg["channels"]:
        return False
    author = msg.get("author") or {}
    if my_id and author.get("id") == my_id and not cfg.get("include_own_messages"):
        return False
    return True


def build_path(cfg, conversation, message_id, key, filename):
    when = snowflake_time(message_id).astimezone()
    name = f"{when:%Y-%m-%d_%H%M%S}_{key}_{sanitize(filename, 60)}"
    base = Path(cfg["download_dir"])
    if cfg.get("subfolder_per_conversation"):
        base = base / sanitize(conversation)
    return base / name


# --------------------------------------------------------------------------
# API REST
# --------------------------------------------------------------------------

class DiscordAPI:
    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": token, "User-Agent": USER_AGENT})

    def get(self, path, params=None):
        for _ in range(10):
            r = self.session.get(API + path, params=params, timeout=30)
            if r.status_code == 429:
                wait = float(r.json().get("retry_after", 1))
                log.debug("Limite de requêtes atteinte, pause de %.1fs", wait)
                time.sleep(wait + 0.25)
                continue
            if r.status_code == 401:
                raise FatalError("Token refusé par Discord (401). Relance : python discord_images.py setup")
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"Trop de limitations de requêtes sur {path}")

    def me(self):
        return self.get("/users/@me")

    def private_channels(self):
        channels = self.get("/users/@me/channels")
        channels.sort(key=lambda c: int(c.get("last_message_id") or 0), reverse=True)
        return channels

    def messages(self, channel_id, after=None):
        """Parcourt l'historique d'un salon, du plus récent au plus ancien."""
        before = None
        while True:
            params = {"limit": 100}
            if before:
                params["before"] = before
            batch = self.get(f"/channels/{channel_id}/messages", params)
            if not batch:
                return
            for msg in batch:
                if after and int(msg["id"]) <= after:
                    return
                yield msg
            before = batch[-1]["id"]


# --------------------------------------------------------------------------
# Téléchargement
# --------------------------------------------------------------------------

class Downloader:
    def __init__(self, cfg, workers=3):
        self.cfg = cfg
        self.http = requests.Session()
        self.http.headers["User-Agent"] = USER_AGENT
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self.can_scan = bool(cfg.get("media_scan")) and shutil.which("termux-media-scan")
        self.saved = 0

    def submit(self, url, path):
        if path.exists():
            return None
        return self.pool.submit(self._download, url, path)

    def _download(self, url, path):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            part = path.with_name(path.name + ".part")
            with self.http.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with part.open("wb") as f:
                    for chunk in r.iter_content(64 * 1024):
                        f.write(chunk)
            part.replace(path)
            self.saved += 1
            log.info("Enregistré : %s", path)
            if self.can_scan:
                # Fait apparaître l'image dans la galerie immédiatement.
                subprocess.run(["termux-media-scan", str(path)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            log.warning("Échec du téléchargement de %s : %s", url, e)

    def close(self):
        self.pool.shutdown(wait=True)


# --------------------------------------------------------------------------
# Gateway (temps réel)
# --------------------------------------------------------------------------

class Gateway:
    def __init__(self, token, on_dispatch):
        self.token = token
        self.on_dispatch = on_dispatch
        self.session_id = None
        self.resume_url = None
        self.seq = None
        self.ws = None
        self.send_lock = threading.Lock()

    def run_forever(self):
        backoff = 1
        while True:
            started = time.monotonic()
            try:
                self._connect_once()
            except FatalError:
                raise
            except Exception as e:
                log.warning("Connexion perdue : %s", e)
            if time.monotonic() - started > 60:
                backoff = 1
            delay = backoff + random.random()
            log.info("Reconnexion dans %.0fs…", delay)
            time.sleep(delay)
            backoff = min(backoff * 2, 60)

    def _send(self, op, d):
        with self.send_lock:
            self.ws.send(json.dumps({"op": op, "d": d}))

    def _connect_once(self):
        url = (self.resume_url if self.session_id else GATEWAY) + GATEWAY_QUERY
        self.ws = websocket.create_connection(url, header=[f"User-Agent: {USER_AGENT}"], timeout=30)
        self.ws.settimeout(None)
        hello = json.loads(self.ws.recv())
        interval = hello["d"]["heartbeat_interval"] / 1000
        stop = threading.Event()
        state = {"acked": True}
        threading.Thread(target=self._heartbeat, args=(interval, stop, state), daemon=True).start()

        if self.session_id and self.seq is not None:
            self._send(6, {"token": self.token, "session_id": self.session_id, "seq": self.seq})
        else:
            self._identify()

        try:
            while True:
                opcode, data = self.ws.recv_data()
                if opcode == websocket.ABNF.OPCODE_CLOSE:
                    code = int.from_bytes(data[:2], "big") if len(data) >= 2 else None
                    if code in FATAL_CLOSE_CODES:
                        raise FatalError(f"Discord a fermé la connexion : {FATAL_CLOSE_CODES[code]}")
                    log.info("Discord a fermé la connexion (code %s)", code)
                    return
                payload = json.loads(data)
                op = payload["op"]
                if op == 0:
                    self.seq = payload["s"]
                    if payload["t"] == "READY":
                        self.session_id = payload["d"]["session_id"]
                        self.resume_url = payload["d"].get("resume_gateway_url", GATEWAY)
                    try:
                        self.on_dispatch(payload["t"], payload["d"])
                    except FatalError:
                        raise
                    except Exception:
                        log.exception("Erreur pendant le traitement de %s", payload["t"])
                elif op == 1:
                    self._send(1, self.seq)
                elif op == 7:
                    log.info("Discord demande une reconnexion")
                    return
                elif op == 9:
                    if not payload["d"]:
                        self.session_id = None
                        self.seq = None
                    time.sleep(1 + random.random() * 4)
                    return
                elif op == 11:
                    state["acked"] = True
        finally:
            stop.set()
            try:
                self.ws.close()
            except Exception:
                pass

    def _identify(self):
        self._send(2, {
            "token": self.token,
            "capabilities": 0,
            "properties": {
                "os": "Android",
                "browser": "Chrome",
                "device": "",
                "browser_user_agent": USER_AGENT,
            },
            "presence": {"status": "unknown", "since": 0, "activities": [], "afk": False},
            "compress": False,
        })

    def _heartbeat(self, interval, stop, state):
        if stop.wait(interval * random.random()):
            return
        while not stop.is_set():
            if not state["acked"]:
                log.warning("Pas de réponse de Discord, reconnexion")
                try:
                    self.ws.close()
                except Exception:
                    pass
                return
            state["acked"] = False
            try:
                self._send(1, self.seq)
            except Exception:
                return
            stop.wait(interval)


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------

class App:
    def __init__(self, cfg):
        self.cfg = cfg
        self.token = require_token(cfg)
        self.api = DiscordAPI(self.token)
        self.downloader = Downloader(cfg)
        self.my_id = None
        self.channels = {}  # id -> objet salon
        self.channels_refreshed = 0.0
        self.accepted = {}  # id de message -> bool (pour MESSAGE_UPDATE)

    def refresh_channels(self, force=False):
        if not force and time.monotonic() - self.channels_refreshed < 30:
            return
        self.channels_refreshed = time.monotonic()
        try:
            self.channels = {c["id"]: c for c in self.api.private_channels()}
        except FatalError:
            raise
        except Exception as e:
            log.warning("Impossible de récupérer la liste des conversations : %s", e)

    def conversation(self, channel_id, msg=None):
        channel = self.channels.get(channel_id)
        if channel is None:
            self.refresh_channels()
            channel = self.channels.get(channel_id)
        if channel is not None:
            return channel.get("type"), conversation_name(channel)
        author = (msg or {}).get("author")
        return None, display_name(author) if author else channel_id

    def handle_message(self, msg, is_update=False):
        if msg.get("guild_id"):
            return 0
        channel_type, name = self.conversation(msg["channel_id"], msg)
        if is_update and not msg.get("author"):
            if not self.accepted.get(msg["id"]):
                return 0
        elif not should_handle(msg, channel_type, self.cfg, self.my_id):
            self.accepted[msg["id"]] = False
            return 0
        self.accepted[msg["id"]] = True
        if len(self.accepted) > 2000:
            for key in list(self.accepted)[:1000]:
                del self.accepted[key]

        count = 0
        for url, key, filename in extract_media(msg, self.cfg):
            path = build_path(self.cfg, name, msg["id"], key, filename)
            if self.downloader.submit(url, path):
                count += 1
        return count

    def on_dispatch(self, event, data):
        if event == "READY":
            self.my_id = data["user"]["id"]
            self.refresh_channels(force=True)
            suivi = f"{len(self.cfg['channels'])} conversation(s)" if self.cfg["channels"] else "toutes les conversations"
            log.info("Connecté en tant que %s — suivi : %s", display_name(data["user"]), suivi)
        elif event == "RESUMED":
            log.info("Connexion reprise")
        elif event == "CHANNEL_CREATE" and data.get("type") in (CHANNEL_DM, CHANNEL_GROUP_DM):
            self.channels[data["id"]] = data
        elif event == "MESSAGE_CREATE":
            self.handle_message(data)
        elif event == "MESSAGE_UPDATE" and data.get("embeds"):
            # Les aperçus de liens arrivent souvent dans une mise à jour du message.
            self.handle_message(data, is_update=True)

    def watch(self):
        log.info("Démarrage… (Ctrl+C pour arrêter)")
        Gateway(self.token, self.on_dispatch).run_forever()

    def backfill(self, channel_ids=None, days=None):
        self.my_id = self.api.me()["id"]
        self.refresh_channels(force=True)
        targets = channel_ids or self.cfg["channels"] or list(self.channels)
        after = None
        if days:
            cutoff_ms = int((time.time() - days * 86400) * 1000) - DISCORD_EPOCH_MS
            after = max(cutoff_ms, 0) << 22
        for cid in targets:
            channel = self.channels.get(cid)
            if channel is None:
                log.warning("Conversation %s introuvable dans tes MP, ignorée", cid)
                continue
            if channel.get("type") == CHANNEL_GROUP_DM and not self.cfg["include_group_dms"] and not channel_ids:
                continue
            name = conversation_name(channel)
            log.info("Historique de « %s »…", name)
            found = 0
            for msg in self.api.messages(cid, after=after):
                msg.setdefault("channel_id", cid)
                found += self.handle_message(msg)
            log.info("  %d nouveau(x) fichier(s) à télécharger", found)
        self.downloader.close()
        log.info("Terminé : %d fichier(s) enregistré(s) dans %s", self.downloader.saved, self.cfg["download_dir"])


# --------------------------------------------------------------------------
# Commandes
# --------------------------------------------------------------------------

def print_channels(channels, selected=()):
    for i, c in enumerate(channels, 1):
        kind = "groupe" if c.get("type") == CHANNEL_GROUP_DM else "MP"
        mark = "*" if c["id"] in selected else " "
        print(f"{mark} {i:3d}. [{kind:6s}] {conversation_name(c)}  (id {c['id']})")


def cmd_dms(cfg, args):
    channels = DiscordAPI(require_token(cfg)).private_channels()
    print_channels(channels, set(cfg["channels"]))
    if cfg["channels"]:
        print("\n* = conversation suivie")


def cmd_select(cfg, args):
    channels = DiscordAPI(require_token(cfg)).private_channels()
    if not channels:
        print("Aucune conversation privée trouvée.")
        return
    print_channels(channels, set(cfg["channels"]))
    print("\nTape les numéros des conversations à suivre, séparés par des virgules (ex : 1,3,5).")
    print("Tape « tout » pour suivre toutes les conversations, y compris les futures.")
    answer = input("> ").strip().lower()
    if answer in ("tout", "toutes", "all", "*", ""):
        cfg["channels"] = []
        print("OK : toutes les conversations privées seront suivies.")
    else:
        picked = []
        for part in re.split(r"[,\s]+", answer):
            if not part:
                continue
            if not part.isdigit() or not 1 <= int(part) <= len(channels):
                raise FatalError(f"Numéro invalide : {part}")
            picked.append(channels[int(part) - 1]["id"])
        cfg["channels"] = picked
        names = [conversation_name(c) for c in channels if c["id"] in picked]
        print("OK, conversations suivies : " + ", ".join(names))
    save_config(args.config, cfg)


def cmd_setup(cfg, args):
    print("Configuration de Discord Images\n")
    print("Colle ton token Discord (il ne s'affichera pas). Voir le README pour le récupérer.")
    token = getpass.getpass("Token : ").strip().strip('"')
    if token:
        cfg["token"] = token
    me = DiscordAPI(require_token(cfg)).me()
    print(f"Token valide : connecté en tant que {display_name(me)}\n")

    folder = input(f"Dossier de destination [{cfg['download_dir']}] : ").strip()
    if folder:
        cfg["download_dir"] = folder
    save_config(args.config, cfg)
    print()
    cmd_select(cfg, args)
    print("\nC'est prêt. Lance : python discord_images.py watch")


def cmd_watch(cfg, args):
    app = App(cfg)
    if args.backfill_days:
        app.backfill(days=args.backfill_days)
        app.downloader = Downloader(cfg)
    app.watch()


def cmd_backfill(cfg, args):
    App(cfg).backfill(channel_ids=args.channel, days=args.days)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Télécharge automatiquement les images de tes MP Discord.")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"),
                        help="fichier de configuration (défaut : config.json à côté du script)")
    parser.add_argument("-v", "--verbose", action="store_true", help="affiche plus de détails")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="configure le token, le dossier et les conversations")
    sub.add_parser("select", help="choisit les conversations à suivre")
    sub.add_parser("dms", help="liste tes conversations privées")
    p = sub.add_parser("watch", help="télécharge les nouvelles images en temps réel")
    p.add_argument("--backfill-days", type=int, metavar="N",
                   help="récupère d'abord les images des N derniers jours")
    p = sub.add_parser("backfill", help="télécharge les images de l'historique")
    p.add_argument("--channel", action="append", metavar="ID",
                   help="id de conversation (répétable ; défaut : celles de la config)")
    p.add_argument("--days", type=int, metavar="N", help="seulement les N derniers jours")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    cfg = load_config(args.config)
    commands = {"setup": cmd_setup, "select": cmd_select, "dms": cmd_dms,
                "watch": cmd_watch, "backfill": cmd_backfill}
    try:
        commands[args.command](cfg, args)
    except FatalError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nArrêté.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
