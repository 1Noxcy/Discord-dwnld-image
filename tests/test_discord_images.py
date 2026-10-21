import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import discord_images as di  # noqa: E402

CFG = dict(di.DEFAULT_CONFIG, download_dir="/tmp/dl")
ME = "100"


def msg(**kw):
    base = {"id": "1290000000000000000", "channel_id": "42", "author": {"id": "200"},
            "attachments": [], "embeds": []}
    base.update(kw)
    return base


def test_snowflake_time():
    assert di.snowflake_time("175928847299117063").year == 2016


def test_sanitize():
    assert di.sanitize('a/b:c*?.png') == "a_b_c__.png"
    assert di.sanitize("...") == "sans_nom"


def test_conversation_name():
    assert di.conversation_name({"recipients": [{"username": "bob", "global_name": "Bob"}]}) == "Bob"
    assert di.conversation_name({"name": "Les potes", "recipients": []}) == "Les potes"


def test_should_handle_filters():
    assert di.should_handle(msg(), di.CHANNEL_DM, CFG, ME)
    assert not di.should_handle(msg(guild_id="9"), None, CFG, ME)
    assert not di.should_handle(msg(author={"id": ME}), di.CHANNEL_DM, CFG, ME)
    assert di.should_handle(msg(author={"id": ME}), di.CHANNEL_DM, dict(CFG, include_own_messages=True), ME)
    assert not di.should_handle(msg(), di.CHANNEL_GROUP_DM, dict(CFG, include_group_dms=False), ME)
    assert not di.should_handle(msg(), 0, CFG, ME)  # salon texte de serveur


def test_should_handle_selection():
    selected = dict(CFG, channels=["42"])
    assert di.should_handle(msg(), di.CHANNEL_DM, selected, ME)
    assert not di.should_handle(msg(channel_id="43"), di.CHANNEL_DM, selected, ME)


def test_extract_attachments():
    m = msg(attachments=[
        {"id": "1", "filename": "photo.JPG", "url": "https://cdn/1"},
        {"id": "2", "filename": "doc.pdf", "url": "https://cdn/2", "content_type": "application/pdf"},
        {"id": "3", "filename": "clip.mp4", "url": "https://cdn/3", "content_type": "video/mp4"},
        {"id": "4", "filename": "image", "url": "https://cdn/4", "content_type": "image/png"},
    ])
    assert [k for _, k, _ in di.extract_media(m, CFG)] == ["1", "4"]
    assert [k for _, k, _ in di.extract_media(m, dict(CFG, include_videos=True))] == ["1", "3", "4"]


def test_extract_embeds():
    m = msg(embeds=[
        {"type": "image", "thumbnail": {"url": "https://ex.com/a.png?x=1"}},
        {"type": "rich", "image": {"url": "https://ex.com/b.jpg"}},
        {"type": "link", "title": "pas d'image"},
    ])
    found = di.extract_media(m, CFG)
    assert [f for _, _, f in found] == ["a.png", "b.jpg"]
    assert di.extract_media(m, dict(CFG, include_embeds=False)) == []
    # La clé ne dépend pas des paramètres signés de l'URL (évite les doublons).
    m2 = msg(embeds=[{"type": "image", "thumbnail": {"url": "https://ex.com/a.png?x=2"}}])
    assert di.extract_media(m2, CFG)[0][1] == found[0][1]


def test_build_path():
    p = di.build_path(CFG, "Bob/Alice", "1290000000000000000", "1", "photo.jpg")
    assert p.parent == Path("/tmp/dl/Bob_Alice")
    assert p.name.endswith("_1_photo.jpg")
    flat = di.build_path(dict(CFG, subfolder_per_conversation=False), "Bob", "1290000000000000000", "1", "x.png")
    assert flat.parent == Path("/tmp/dl")


def test_handle_message_skips_existing(tmp_path, monkeypatch):
    cfg = dict(CFG, download_dir=str(tmp_path), token="t", media_scan=False)
    app = di.App(cfg)
    app.my_id = ME
    app.channels = {"42": {"id": "42", "type": di.CHANNEL_DM, "recipients": [{"username": "bob"}]}}
    app.channels_refreshed = float("inf")
    submitted = []
    monkeypatch.setattr(app.downloader, "_download", lambda url, path: submitted.append(path))

    m = msg(attachments=[{"id": "7", "filename": "a.png", "url": "https://cdn/7"}])
    assert app.handle_message(m) == 1
    app.downloader.close()
    assert submitted[0].parent == tmp_path / "bob"

    submitted[0].parent.mkdir(parents=True)
    submitted[0].touch()
    app.downloader = di.Downloader(cfg)
    assert app.handle_message(m) == 0


def test_update_without_author_follows_create():
    cfg = dict(CFG, token="t", media_scan=False)
    app = di.App(cfg)
    app.my_id = ME
    app.channels = {"42": {"id": "42", "type": di.CHANNEL_DM}}
    app.channels_refreshed = float("inf")
    app.downloader.submit = lambda url, path: True
    own = msg(author={"id": ME})
    app.handle_message(own)
    update = {"id": own["id"], "channel_id": "42",
              "embeds": [{"type": "image", "thumbnail": {"url": "https://ex.com/a.png"}}]}
    assert app.handle_message(update, is_update=True) == 0
