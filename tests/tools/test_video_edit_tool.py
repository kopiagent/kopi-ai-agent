"""Caption must work on ffmpeg builds without libfreetype.

Homebrew's ffmpeg 8.x formula ships without the drawtext filter, which made
`video_edit caption` the only operation of five that failed on a stock Mac.
These tests pin the renderer selection (drawtext when available, Pillow PNG +
overlay when not), the PNG fallback's temp-file hygiene, and the CJK-aware
font pick that keeps Chinese captions from rendering as tofu boxes.
"""

import json
import os

import pytest

from tools import video_edit_tool
from tools.video_edit_tool import (
    _handle_video_edit,
    _render_caption_png,
    _text_needs_cjk,
)


@pytest.fixture
def clip(tmp_path):
    """A fake input clip plus stubs so no real ffmpeg runs."""
    path = tmp_path / "in.mp4"
    path.write_bytes(b"\x00" * 64)
    return str(path)


@pytest.fixture
def ffmpeg_stub(monkeypatch):
    """Capture ffmpeg invocations; success without running anything."""
    calls = []

    def fake_run(command, timeout):
        calls.append(command)
        return True, ""

    monkeypatch.setattr(video_edit_tool, "_run", fake_run)
    monkeypatch.setattr(video_edit_tool, "_find_binary", lambda name: name)
    monkeypatch.setattr(video_edit_tool, "_probe", lambda path: ({"format": {}, "streams": []}, None))
    monkeypatch.setattr(video_edit_tool, "check_video_edit_requirements", lambda: True)
    return calls


def _caption(clip_path, out_dir, **extra):
    args = {
        "operation": "caption",
        "input_paths": [clip_path],
        "text": extra.pop("text", "hello"),
        "output_path": os.path.join(out_dir, "out.mp4"),
        **extra,
    }
    return json.loads(_handle_video_edit(args))


def test_caption_uses_drawtext_when_available(clip, tmp_path, ffmpeg_stub, monkeypatch):
    monkeypatch.setattr(video_edit_tool, "_ffmpeg_has_filter", lambda name: True)
    result = _caption(clip, str(tmp_path))
    assert result["renderer"] == "drawtext"
    command = ffmpeg_stub[0]
    assert "-vf" in command
    assert any("drawtext=" in arg for arg in command)


def test_caption_falls_back_to_overlay_png(clip, tmp_path, ffmpeg_stub, monkeypatch):
    monkeypatch.setattr(video_edit_tool, "_ffmpeg_has_filter", lambda name: False)
    result = _caption(clip, str(tmp_path), text="考比演示")
    assert result["renderer"] == "overlay_png"
    command = ffmpeg_stub[0]
    assert "-filter_complex" in command
    assert any("overlay=" in arg for arg in command)
    # The rendered PNG was passed as a second input and cleaned up after.
    png = command[command.index("-i", command.index("-i") + 1) + 1]
    assert png.endswith(".png")
    assert not os.path.exists(png)


def test_render_caption_png_produces_image(tmp_path):
    path, err = _render_caption_png("KOPI 考比", 48)
    assert err is None
    try:
        from PIL import Image

        with Image.open(path) as img:
            assert img.mode == "RGBA"
            assert img.width > img.height > 0
    finally:
        os.unlink(path)


def test_cjk_detection():
    assert _text_needs_cjk("考比智能体")
    assert _text_needs_cjk("mixed 字幕 caption")
    assert _text_needs_cjk("カタカナ")
    assert _text_needs_cjk("한글")
    assert not _text_needs_cjk("plain ASCII caption 123")


def test_filter_listing_parse(monkeypatch):
    listing = (
        " ... overlay            VV->V      Overlay a video source on top\n"
        " T.. drawtext           V->V       Draw text on top of video frames\n"
    )
    monkeypatch.setattr(video_edit_tool, "_run", lambda cmd, t: (True, listing))
    monkeypatch.setattr(video_edit_tool, "_find_binary", lambda name: name)
    video_edit_tool._FILTER_SUPPORT.clear()
    assert video_edit_tool._ffmpeg_has_filter("drawtext") is True
    video_edit_tool._FILTER_SUPPORT.clear()
    monkeypatch.setattr(
        video_edit_tool, "_run", lambda cmd, t: (True, " ... overlay  VV->V  x\n")
    )
    assert video_edit_tool._ffmpeg_has_filter("drawtext") is False
    video_edit_tool._FILTER_SUPPORT.clear()
