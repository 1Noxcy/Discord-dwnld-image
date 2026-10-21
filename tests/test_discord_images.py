import sys
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import discord_images as di  # noqa: E402

OPTS = dict(di.DEFAULT_OPTIONS, download_dir="/tmp/dl")


def msg(**kw):
    base = {"id": "1290000000000000000", "channel_id": "42", "author": {"id": "200"},
            "attachments": [], "embeds": []}
    base.update(kw)
    return base


def test_snowflake_roundtrip():
    when = datetime(2024, 5, 1, 12, 0).astimezone()
    assert di.snowflake_time(di.snowflake_from_time(when)) == when


def test_parse_date():
    assert di.parse_date("") is None
    assert di.parse_date("03/02/2024").strftime("%Y-%m-%d") == "2024-02-03"
    try:
        di.parse_date("31/31/2024")
        assert False
    except ValueError:
        pass


def test_date_bounds_include_whole_days():
    start, end = di.parse_date("01/05/2024"), di.parse_date("02/05/2024")
    after, before = di.date_bounds(start, end)
    first = di.snowflake_from_time(start)
    last = di.snowflake_from_time(di.parse_date("03/05/2024")) - 1
    assert after < first and last < before
    assert di.date_bounds(None, None) == (None, None)


def test_sanitize():
    assert di.sanitize('a/b:c*?.png') == "a_b_c__.png"
    assert di.sanitize("...") == "sans_nom"


def test_conversation_name():
    assert di.conversation_name({"recipients": [{"username": "bob", "global_name": "Bob"}]}) == "Bob"
    assert di.conversation_name({"name": "Les potes", "recipients": []}) == "Les potes"


def test_extract_attachments():
    m = msg(attachments=[
        {"id": "1", "filename": "photo.JPG", "url": "https://cdn/1"},
        {"id": "2", "filename": "doc.pdf", "url": "https://cdn/2", "content_type": "application/pdf"},
        {"id": "3", "filename": "clip.mp4", "url": "https://cdn/3", "content_type": "video/mp4"},
        {"id": "4", "filename": "image", "url": "https://cdn/4", "content_type": "image/png"},
    ])
    assert [k for _, k, _ in di.extract_media(m, OPTS)] == ["1", "4"]
    assert [k for _, k, _ in di.extract_media(m, dict(OPTS, include_videos=True))] == ["1", "3", "4"]


def test_extract_spoiler():
    m = msg(attachments=[{"id": "5", "filename": "SPOILER_chat.png", "url": "https://cdn/5"}])
    assert di.extract_media(m, OPTS) == [("https://cdn/5", "5", "chat.png")]


def test_extract_embeds():
    m = msg(embeds=[
        {"type": "image", "thumbnail": {"url": "https://ex.com/a.png?x=1"}},
        {"type": "rich", "image": {"url": "https://ex.com/b.jpg"}},
        {"type": "link", "title": "pas d'image"},
    ])
    found = di.extract_media(m, OPTS)
    assert [f for _, _, f in found] == ["a.png", "b.jpg"]
    assert di.extract_media(m, dict(OPTS, include_embeds=False)) == []
    m2 = msg(embeds=[{"type": "image", "thumbnail": {"url": "https://ex.com/a.png?x=2"}}])
    assert di.extract_media(m2, OPTS)[0][1] == found[0][1]


def test_build_path():
    p = di.build_path(OPTS, "Bob/Alice", "1290000000000000000", "1", "photo.jpg")
    assert p.parent == Path("/tmp/dl/Bob_Alice")
    assert p.name.endswith("_1_photo.jpg")
    flat = di.build_path(dict(OPTS, subfolder_per_conversation=False), "Bob", "1290000000000000000", "1", "x.png")
    assert flat.parent == Path("/tmp/dl")


class FakeAPI:
    def __init__(self, messages):
        self._messages = messages
        self.calls = []

    def messages(self, channel_id, after=None, before=None):
        self.calls.append((channel_id, after, before))
        return iter(self._messages)


def test_run_download(tmp_path, monkeypatch):
    saved = []

    def fake_download(session, url, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
        saved.append(path)

    monkeypatch.setattr(di, "download_file", fake_download)
    api = FakeAPI([
        msg(id="1290000000000000001", attachments=[{"id": "7", "filename": "a.png", "url": "u7"}]),
        msg(id="1290000000000000002", author={"id": "100"},
            attachments=[{"id": "8", "filename": "mine.png", "url": "u8"}]),
    ])
    channel = {"id": "42", "type": 1, "recipients": [{"username": "bob"}]}
    opts = dict(OPTS, download_dir=str(tmp_path))
    reports = []

    stats = di.run_download(api, [channel], opts, "100", lambda *a: reports.append(a), threading.Event())
    assert stats == {"saved": 1, "skipped": 0, "failed": 0}
    assert saved[0].parent == tmp_path / "bob"

    stats = di.run_download(api, [channel], opts, "100", lambda *a: None, threading.Event())
    assert stats == {"saved": 0, "skipped": 1, "failed": 0}

    stats = di.run_download(api, [channel], dict(opts, include_own_messages=True), "100",
                            lambda *a: None, threading.Event())
    assert stats["saved"] == 1
