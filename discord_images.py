#!/usr/bin/env python3
"""Discord Images : enregistre les images de tes conversations privées Discord.

Double-clique sur l'application, connecte-toi avec ton token, choisis les
conversations et éventuellement une période, puis clique sur « Télécharger ».
L'outil est en lecture seule : il n'envoie jamais de message.
"""

import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

API = "https://discord.com/api/v10"
DISCORD_EPOCH_MS = 1420070400000
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
CONFIG_PATH = Path.home() / ".discord_images.json"

CHANNEL_GROUP_DM = 3

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif", ".avif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}

DEFAULT_OPTIONS = {
    "download_dir": str(Path.home() / "Pictures" / "Discord"),
    "include_own_messages": False,
    "include_videos": False,
    "include_embeds": True,
    "subfolder_per_conversation": True,
}


class FatalError(Exception):
    pass


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def load_config(path=CONFIG_PATH):
    cfg = dict(DEFAULT_OPTIONS, token="", selected=[])
    try:
        with path.open(encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg, path=CONFIG_PATH):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.chmod(tmp, 0o600)
    tmp.replace(path)


# --------------------------------------------------------------------------
# Fonctions utilitaires (sans réseau, testées dans tests/)
# --------------------------------------------------------------------------

def snowflake_time(snowflake):
    ms = (int(snowflake) >> 22) + DISCORD_EPOCH_MS
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def snowflake_from_time(when):
    ms = int(when.timestamp() * 1000) - DISCORD_EPOCH_MS
    return max(ms, 0) << 22


def parse_date(text):
    """« JJ/MM/AAAA » -> datetime locale à minuit, ou None si vide."""
    text = text.strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).astimezone()
        except ValueError:
            pass
    raise ValueError(f"Date invalide : « {text} » (format attendu : JJ/MM/AAAA)")


def date_bounds(date_from, date_to):
    """Convertit une période (dates incluses) en bornes after/before de l'API."""
    after = snowflake_from_time(date_from) - 1 if date_from else None
    before = snowflake_from_time(date_to + timedelta(days=1)) if date_to else None
    return after, before


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


def _wanted(kind, opts):
    return kind == "image" or (kind == "video" and opts.get("include_videos"))


def extract_media(msg, opts):
    """Liste des médias d'un message : tuples (url, clé unique, nom de fichier)."""
    items = []
    for att in msg.get("attachments") or []:
        filename = att.get("filename", "fichier")
        if _wanted(media_kind(filename, att.get("content_type")), opts):
            # Les images avec spoiler sont des pièces jointes nommées SPOILER_xxx.
            clean = filename[len("SPOILER_"):] if filename.startswith("SPOILER_") else filename
            items.append((att.get("url") or att.get("proxy_url"), att["id"], clean or filename))

    if not opts.get("include_embeds"):
        return items
    for embed in msg.get("embeds") or []:
        candidates = []
        if embed.get("image"):
            candidates.append(embed["image"])
        if embed.get("type") == "image" and embed.get("thumbnail"):
            candidates.append(embed["thumbnail"])
        if embed.get("type") == "gifv" and embed.get("video") and opts.get("include_videos"):
            candidates.append(embed["video"])
        for media in candidates:
            url = media.get("url") or media.get("proxy_url")
            if not url:
                continue
            filename = Path(urlparse(url).path).name or "embed"
            kind = media_kind(filename, media.get("content_type")) or "image"
            if not _wanted(kind, opts):
                continue
            key = hashlib.sha1(url.split("?")[0].encode()).hexdigest()[:12]
            items.append((url, key, filename))
            break  # une seule version (image ou miniature) par lien
    return items


def build_path(opts, conversation, message_id, key, filename):
    when = snowflake_time(message_id).astimezone()
    name = f"{when:%Y-%m-%d_%H%M%S}_{key}_{sanitize(filename, 60)}"
    base = Path(opts["download_dir"])
    if opts.get("subfolder_per_conversation"):
        base = base / sanitize(conversation)
    return base / name


# --------------------------------------------------------------------------
# Réseau
# --------------------------------------------------------------------------

class DiscordAPI:
    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": token.strip().strip('"'),
                                     "User-Agent": USER_AGENT})

    def get(self, path, params=None):
        for _ in range(10):
            r = self.session.get(API + path, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(float(r.json().get("retry_after", 1)) + 0.25)
                continue
            if r.status_code == 401:
                raise FatalError("Token refusé par Discord. Vérifie-le, ou récupère-le à nouveau.")
            if r.status_code == 403:
                raise FatalError("Accès refusé à cette conversation.")
            r.raise_for_status()
            return r.json()
        raise FatalError("Discord limite trop les requêtes, réessaie dans quelques minutes.")

    def me(self):
        return self.get("/users/@me")

    def private_channels(self):
        channels = self.get("/users/@me/channels")
        channels.sort(key=lambda c: int(c.get("last_message_id") or 0), reverse=True)
        return channels

    def messages(self, channel_id, after=None, before=None):
        """Parcourt l'historique d'un salon, du plus récent au plus ancien."""
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


def download_file(session, url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with session.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with part.open("wb") as f:
            for chunk in r.iter_content(64 * 1024):
                f.write(chunk)
    part.replace(path)


def run_download(api, channels, opts, my_id, report, cancel):
    """Télécharge les médias des conversations choisies.

    report(type, valeur) reçoit l'avancement ; cancel est un threading.Event.
    """
    after, before = date_bounds(opts.get("date_from"), opts.get("date_to"))
    stats = {"saved": 0, "skipped": 0, "failed": 0}
    lock = threading.Lock()
    http = requests.Session()
    http.headers["User-Agent"] = USER_AGENT

    def fetch(url, path):
        if cancel.is_set():
            return
        try:
            download_file(http, url, path)
            result = "saved"
        except Exception as e:
            report("log", f"Échec : {path.name} ({e})")
            result = "failed"
        with lock:
            stats[result] += 1
            snapshot = dict(stats)
        report("stats", snapshot)

    with ThreadPoolExecutor(max_workers=4) as pool:
        for channel in channels:
            if cancel.is_set():
                break
            name = conversation_name(channel)
            report("log", f"Conversation « {name} »…")
            found = 0
            for msg in api.messages(channel["id"], after=after, before=before):
                if cancel.is_set():
                    break
                author = (msg.get("author") or {}).get("id")
                if author == my_id and not opts.get("include_own_messages"):
                    continue
                for url, key, filename in extract_media(msg, opts):
                    path = build_path(opts, name, msg["id"], key, filename)
                    if path.exists():
                        with lock:
                            stats["skipped"] += 1
                        continue
                    found += 1
                    pool.submit(fetch, url, path)
            report("log", f"  {found} nouveau(x) fichier(s)")
    return stats


# --------------------------------------------------------------------------
# Interface graphique
# --------------------------------------------------------------------------

def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Discord Images")
            self.geometry("620x700")
            self.minsize(520, 580)
            self.cfg = load_config()
            self.api = None
            self.my_id = None
            self.channels = []
            self.events = queue.Queue()
            self.cancel = threading.Event()
            self.worker = None
            self._build()
            self.after(100, self._poll)

        # ---- construction de la fenêtre --------------------------------

        def _build(self):
            pad = {"padx": 10, "pady": 4}

            box = ttk.LabelFrame(self, text="1. Connexion")
            box.pack(fill="x", **pad)
            ttk.Label(box, text="Token :").grid(row=0, column=0, sticky="w", padx=6, pady=6)
            self.token = tk.StringVar(value=self.cfg.get("token", ""))
            ttk.Entry(box, textvariable=self.token, show="•").grid(row=0, column=1, sticky="ew", pady=6)
            self.login_btn = ttk.Button(box, text="Se connecter", command=self.login)
            self.login_btn.grid(row=0, column=2, padx=6)
            self.remember = tk.BooleanVar(value=bool(self.cfg.get("token")))
            ttk.Checkbutton(box, text="Se souvenir du token sur cet ordinateur",
                            variable=self.remember).grid(row=1, column=1, sticky="w")
            self.user_label = ttk.Label(box, text="")
            self.user_label.grid(row=2, column=1, sticky="w", pady=(0, 6))
            box.columnconfigure(1, weight=1)

            box = ttk.LabelFrame(self, text="2. Conversations (clique pour cocher / décocher)")
            box.pack(fill="both", expand=True, **pad)
            bar = ttk.Frame(box)
            bar.pack(fill="x", padx=6, pady=4)
            ttk.Label(bar, text="Rechercher :").pack(side="left")
            self.search = tk.StringVar()
            self.search.trace_add("write", lambda *_: self._fill_list())
            ttk.Entry(bar, textvariable=self.search).pack(side="left", fill="x", expand=True, padx=6)
            ttk.Button(bar, text="Tout", command=lambda: self._select_all(True)).pack(side="left")
            ttk.Button(bar, text="Aucune", command=lambda: self._select_all(False)).pack(side="left")
            frame = ttk.Frame(box)
            frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
            self.listbox = tk.Listbox(frame, selectmode="multiple", activestyle="none",
                                      exportselection=False, selectbackground="#2563eb",
                                      selectforeground="white")
            scroll = ttk.Scrollbar(frame, command=self.listbox.yview)
            self.listbox.configure(yscrollcommand=scroll.set)
            self.listbox.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            self.listbox.bind("<<ListboxSelect>>", self._on_select)
            self.selected = set(self.cfg.get("selected", []))
            self.shown = []

            box = ttk.LabelFrame(self, text="3. Options")
            box.pack(fill="x", **pad)
            ttk.Label(box, text="Du (JJ/MM/AAAA) :").grid(row=0, column=0, sticky="w", padx=6, pady=4)
            self.date_from = tk.StringVar()
            ttk.Entry(box, textvariable=self.date_from, width=12).grid(row=0, column=1, sticky="w")
            ttk.Label(box, text="au :").grid(row=0, column=2, sticky="e", padx=6)
            self.date_to = tk.StringVar()
            ttk.Entry(box, textvariable=self.date_to, width=12).grid(row=0, column=3, sticky="w")
            ttk.Label(box, text="(vide = tout)").grid(row=0, column=4, sticky="w", padx=6)

            ttk.Label(box, text="Dossier :").grid(row=1, column=0, sticky="w", padx=6, pady=4)
            self.folder = tk.StringVar(value=self.cfg["download_dir"])
            ttk.Entry(box, textvariable=self.folder).grid(row=1, column=1, columnspan=3, sticky="ew")
            ttk.Button(box, text="Parcourir…", command=self.browse).grid(row=1, column=4, padx=6)

            self.opt_vars = {}
            labels = [
                ("subfolder_per_conversation", "Un sous-dossier par conversation"),
                ("include_own_messages", "Inclure les images que j'ai envoyées"),
                ("include_videos", "Inclure les vidéos"),
                ("include_embeds", "Inclure les images des liens partagés"),
            ]
            for i, (key, label) in enumerate(labels):
                var = tk.BooleanVar(value=self.cfg.get(key, DEFAULT_OPTIONS[key]))
                self.opt_vars[key] = var
                ttk.Checkbutton(box, text=label, variable=var).grid(
                    row=2 + i // 2, column=(i % 2) * 2, columnspan=2 + (i % 2), sticky="w", padx=6, pady=2)
            box.columnconfigure(1, weight=1)

            bar = ttk.Frame(self)
            bar.pack(fill="x", **pad)
            self.start_btn = ttk.Button(bar, text="Télécharger", command=self.start, state="disabled")
            self.start_btn.pack(side="left")
            self.cancel_btn = ttk.Button(bar, text="Annuler", command=self.cancel.set, state="disabled")
            self.cancel_btn.pack(side="left", padx=6)
            ttk.Button(bar, text="Ouvrir le dossier", command=self.open_folder).pack(side="right")
            self.progress = ttk.Progressbar(self, mode="indeterminate")
            self.progress.pack(fill="x", padx=10)
            self.status = ttk.Label(self, text="Colle ton token puis clique sur « Se connecter ».")
            self.status.pack(fill="x", padx=10, pady=2)
            self.log = tk.Text(self, height=7, state="disabled", wrap="word")
            self.log.pack(fill="both", padx=10, pady=(0, 10))

        # ---- liste des conversations -----------------------------------

        def _fill_list(self):
            term = self.search.get().strip().lower()
            self.shown = [c for c in self.channels if term in conversation_name(c).lower()]
            self.listbox.delete(0, "end")
            for i, c in enumerate(self.shown):
                prefix = "[groupe] " if c.get("type") == CHANNEL_GROUP_DM else ""
                self.listbox.insert("end", prefix + conversation_name(c))
                if c["id"] in self.selected:
                    self.listbox.selection_set(i)
            self._update_count()

        def _on_select(self, _event=None):
            picked = set(self.listbox.curselection())
            for i, c in enumerate(self.shown):
                if i in picked:
                    self.selected.add(c["id"])
                else:
                    self.selected.discard(c["id"])
            self._update_count()

        def _select_all(self, value):
            for c in self.shown:
                if value:
                    self.selected.add(c["id"])
                else:
                    self.selected.discard(c["id"])
            self._fill_list()

        def _update_count(self):
            if self.channels and not self._busy():
                n = len(self.selected & {c["id"] for c in self.channels})
                self.status.config(text=f"{n} conversation(s) sélectionnée(s)")

        # ---- actions -----------------------------------------------------

        def _busy(self):
            return self.worker is not None and self.worker.is_alive()

        def _run(self, target):
            self.worker = threading.Thread(target=target, daemon=True)
            self.worker.start()

        def login(self):
            token = self.token.get().strip().strip('"')
            if not token:
                messagebox.showwarning("Discord Images", "Colle d'abord ton token.")
                return
            self.login_btn.config(state="disabled")
            self.status.config(text="Connexion…")

            def work():
                try:
                    api = DiscordAPI(token)
                    me = api.me()
                    self.events.put(("logged_in", (api, me, api.private_channels())))
                except FatalError as e:
                    self.events.put(("error", str(e)))
                except Exception as e:
                    self.events.put(("error", f"Connexion impossible : {e}"))
            self._run(work)

        def browse(self):
            folder = filedialog.askdirectory(initialdir=self.folder.get() or str(Path.home()))
            if folder:
                self.folder.set(folder)

        def open_folder(self):
            folder = Path(self.folder.get())
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])

        def start(self):
            channels = [c for c in self.channels if c["id"] in self.selected]
            if not channels:
                messagebox.showwarning("Discord Images", "Sélectionne au moins une conversation.")
                return
            try:
                date_from = parse_date(self.date_from.get())
                date_to = parse_date(self.date_to.get())
            except ValueError as e:
                messagebox.showwarning("Discord Images", str(e))
                return
            if date_from and date_to and date_from > date_to:
                messagebox.showwarning("Discord Images", "La date de début est après la date de fin.")
                return
            opts = {k: v.get() for k, v in self.opt_vars.items()}
            opts.update(download_dir=self.folder.get().strip() or DEFAULT_OPTIONS["download_dir"],
                        date_from=date_from, date_to=date_to)
            self._save(opts)

            self.cancel.clear()
            self.login_btn.config(state="disabled")
            self.start_btn.config(state="disabled")
            self.cancel_btn.config(state="normal")
            self.progress.start(12)
            self.status.config(text="Recherche des images…")

            def work():
                try:
                    stats = run_download(self.api, channels, opts, self.my_id,
                                         lambda kind, value: self.events.put((kind, value)),
                                         self.cancel)
                    self.events.put(("done", stats))
                except FatalError as e:
                    self.events.put(("error", str(e)))
                except Exception as e:
                    self.events.put(("error", f"Erreur : {e}"))
            self._run(work)

        def _save(self, opts):
            self.cfg.update({k: v for k, v in opts.items() if k in DEFAULT_OPTIONS})
            self.cfg["selected"] = sorted(self.selected)
            self.cfg["token"] = self.token.get().strip() if self.remember.get() else ""
            try:
                save_config(self.cfg)
            except OSError:
                pass

        # ---- événements venant des threads ------------------------------

        def _write_log(self, text):
            self.log.config(state="normal")
            self.log.insert("end", text + "\n")
            self.log.see("end")
            self.log.config(state="disabled")

        def _poll(self):
            try:
                while True:
                    kind, value = self.events.get_nowait()
                    self._handle(kind, value)
            except queue.Empty:
                pass
            self.after(100, self._poll)

        def _handle(self, kind, value):
            if kind == "logged_in":
                self.api, me, self.channels = value
                self.my_id = me["id"]
                self.user_label.config(text=f"Connecté en tant que {display_name(me)}")
                self.login_btn.config(state="normal")
                self.start_btn.config(state="normal")
                self._save({})
                self._fill_list()
            elif kind == "log":
                self._write_log(value)
            elif kind == "stats":
                self.status.config(text=f"{value['saved']} fichier(s) enregistré(s), "
                                        f"{value['failed']} échec(s)…")
            elif kind in ("done", "error"):
                self.progress.stop()
                self.login_btn.config(state="normal")
                self.start_btn.config(state="normal" if self.api else "disabled")
                self.cancel_btn.config(state="disabled")
                if kind == "error":
                    self.status.config(text=value)
                    messagebox.showerror("Discord Images", value)
                else:
                    word = "Annulé" if self.cancel.is_set() else "Terminé"
                    text = (f"{word} : {value['saved']} fichier(s) enregistré(s), "
                            f"{value['skipped']} déjà présent(s), {value['failed']} échec(s).")
                    self.status.config(text=text)
                    self._write_log(text)

    App().mainloop()


if __name__ == "__main__":
    run_gui()
