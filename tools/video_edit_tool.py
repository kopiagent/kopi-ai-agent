#!/usr/bin/env python3
"""
Local Video Editing Tool
========================

``video_edit`` — cut, join, caption and score video files that already exist
on disk, using the local ffmpeg. This is the missing half of ``video_generate``:
generation backends return one clip at a time, so assembling a finished piece
(three generated shots joined, trimmed to length, captioned, with a music bed)
previously meant hand-writing shell commands.

Design notes
------------
- **Local only.** No provider, no API key, no network. If ffmpeg is present the
  tool works; otherwise every operation fails with the same clear message.
- **Re-encode on concat, always.** ffmpeg's fast concat *demuxer* requires
  byte-identical codec parameters. Clips from different generators (or even the
  same generator at different resolutions) silently produce corrupt or
  audio-desynced output. We take the slower ``concat`` *filter* path and
  normalize every input to one resolution / fps / sample rate first, so joining
  mixed sources just works.
- **Silent inputs get silence.** The concat filter needs every segment to have
  the same stream layout. Generated clips frequently have no audio track, so a
  missing one is synthesized rather than rejected.
- **Operations, not a filtergraph DSL.** The model picks an ``operation`` and
  fills a handful of typed fields. Exposing raw ffmpeg arguments would be a
  command-injection surface and a support burden.
- **Caption survives freetype-less ffmpeg builds.** ``drawtext`` needs
  libfreetype, and common builds ship without it (Homebrew's ffmpeg 8.x
  formula dropped it). When the filter is missing, the caption is rendered
  to a PNG with Pillow (already a core dependency) and composited with the
  ``overlay`` filter, which is built into every ffmpeg.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

from kopi_cli._subprocess_compat import windows_hide_flags


# Long enough for a multi-minute re-encode on a laptop CPU, short enough that a
# wedged ffmpeg does not hang the agent turn forever.
_FFMPEG_TIMEOUT_S = 900
_PROBE_TIMEOUT_S = 60

_DEFAULT_FPS = 30
_DEFAULT_WIDTH = 1920
_DEFAULT_HEIGHT = 1080
_AUDIO_RATE = 48000

# Vertical social formats are the common case for generated clips, so the
# presets cover them rather than only 16:9.
_RESOLUTION_PRESETS: Dict[str, Tuple[int, int]] = {
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "480p": (854, 480),
    "1080p_vertical": (1080, 1920),
    "720p_vertical": (720, 1280),
    "square": (1080, 1080),
}


def _find_binary(name: str) -> Optional[str]:
    """Locate ``name``, falling back to the usual Homebrew/local prefixes.

    A GUI-launched desktop app inherits a minimal PATH that often omits
    /opt/homebrew/bin, so `shutil.which` alone reports ffmpeg missing on
    machines where it is plainly installed.
    """
    found = shutil.which(name)
    if found:
        return found
    for prefix in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/snap/bin"):
        candidate = Path(prefix) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def check_video_edit_requirements() -> bool:
    """The tool is available exactly when ffmpeg is."""
    return _find_binary("ffmpeg") is not None


def _missing_ffmpeg_error() -> str:
    return tool_error(
        "ffmpeg was not found on PATH. Install it (macOS: `brew install ffmpeg`, "
        "Debian/Ubuntu: `apt install ffmpeg`) and retry.",
        error_type="ffmpeg_missing",
    )


def _run(command: List[str], timeout: int) -> Tuple[bool, str]:
    """Run ``command``, returning ``(ok, stderr_tail)``.

    ffmpeg writes progress to stderr, so only the tail is kept — the last lines
    carry the actual error when it fails.
    """
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            creationflags=windows_hide_flags(),
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    except Exception as exc:  # pragma: no cover - OS-level failures
        return False, str(exc)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-8:])
        return False, tail or f"exit code {proc.returncode}"
    return True, proc.stdout or ""


def _probe(path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Return ffprobe metadata for ``path`` as a dict, or an error string."""
    ffprobe = _find_binary("ffprobe")
    if not ffprobe:
        return None, "ffprobe was not found on PATH (it ships with ffmpeg)."
    ok, out = _run(
        [
            ffprobe, "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            path,
        ],
        _PROBE_TIMEOUT_S,
    )
    if not ok:
        return None, out
    try:
        return json.loads(out), None
    except json.JSONDecodeError as exc:
        return None, f"could not parse ffprobe output: {exc}"


def _summarize_probe(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce ffprobe's firehose to the fields an editing decision needs."""
    streams = raw.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = raw.get("format") or {}

    fps = None
    if video:
        # ffprobe reports frame rate as the string "30000/1001".
        rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or ""
        if "/" in rate:
            num, _, den = rate.partition("/")
            try:
                fps = round(int(num) / int(den), 3) if int(den) else None
            except (ValueError, ZeroDivisionError):
                fps = None

    try:
        duration = round(float(fmt.get("duration", 0.0)), 3)
    except (TypeError, ValueError):
        duration = None

    return {
        "duration_seconds": duration,
        "has_video": video is not None,
        "has_audio": audio is not None,
        "width": video.get("width") if video else None,
        "height": video.get("height") if video else None,
        "fps": fps,
        "video_codec": video.get("codec_name") if video else None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "size_bytes": int(fmt["size"]) if str(fmt.get("size", "")).isdigit() else None,
    }


def _resolve_inputs(paths: Any) -> Tuple[List[str], Optional[str]]:
    """Validate a list of input paths, returning absolute paths or an error."""
    if not isinstance(paths, list) or not paths:
        return [], "`input_paths` must be a non-empty list of file paths."
    resolved: List[str] = []
    for entry in paths:
        if not isinstance(entry, str) or not entry.strip():
            return [], "every entry in `input_paths` must be a non-empty string."
        candidate = Path(entry).expanduser()
        if not candidate.is_file():
            return [], f"input file not found: {entry}"
        resolved.append(str(candidate.resolve()))
    return resolved, None


def _resolve_output(path: Any, default_name: str) -> Tuple[Optional[str], Optional[str]]:
    if path is None:
        return str((Path.cwd() / default_name).resolve()), None
    if not isinstance(path, str) or not path.strip():
        return None, "`output_path` must be a non-empty string when provided."
    out = Path(path).expanduser()
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return None, f"cannot create output directory {out.parent}: {exc}"
    return str(out.resolve()), None


def _target_geometry(args: Dict[str, Any]) -> Tuple[int, int, int]:
    """Resolve the normalization target as ``(width, height, fps)``."""
    preset = args.get("resolution")
    width, height = _RESOLUTION_PRESETS.get(
        preset if isinstance(preset, str) else "", (_DEFAULT_WIDTH, _DEFAULT_HEIGHT)
    )
    fps = args.get("fps")
    if not isinstance(fps, int) or not 1 <= fps <= 120:
        fps = _DEFAULT_FPS
    return width, height, fps


def _normalize_chain(index: int, width: int, height: int, fps: int) -> str:
    """Filter chain putting input ``index`` into the common format.

    ``scale`` with ``force_original_aspect_ratio=decrease`` then ``pad``
    letterboxes rather than distorting — a 9:16 shot dropped into a 16:9
    sequence keeps its proportions instead of being squashed.
    """
    return (
        f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"setsar=1,fps={fps},format=yuv420p[v{index}]"
    )


def _handle_probe(args: Dict[str, Any]) -> str:
    inputs, err = _resolve_inputs(args.get("input_paths"))
    if err:
        return tool_error(err)
    clips = []
    for path in inputs:
        raw, probe_err = _probe(path)
        if probe_err:
            return tool_error(f"could not probe {path}: {probe_err}")
        clips.append({"path": path, **_summarize_probe(raw)})
    return tool_result(operation="probe", clips=clips)


def _handle_concat(args: Dict[str, Any]) -> str:
    inputs, err = _resolve_inputs(args.get("input_paths"))
    if err:
        return tool_error(err)
    if len(inputs) < 2:
        return tool_error("`concat` needs at least two clips in `input_paths`.")
    output, err = _resolve_output(args.get("output_path"), "joined.mp4")
    if err:
        return tool_error(err)

    width, height, fps = _target_geometry(args)

    # Probe first: a clip with no audio needs a synthesized silent track, and
    # the concat filter has to be told the exact stream count up front.
    audio_flags: List[bool] = []
    for path in inputs:
        raw, probe_err = _probe(path)
        if probe_err:
            return tool_error(f"could not probe {path}: {probe_err}")
        summary = _summarize_probe(raw)
        if not summary["has_video"]:
            return tool_error(f"{path} has no video stream, so it cannot be joined.")
        audio_flags.append(bool(summary["has_audio"]))

    command: List[str] = [_find_binary("ffmpeg"), "-y"]
    for path in inputs:
        command += ["-i", path]

    # One silent source feeds every audio-less clip; `-shortest` is not usable
    # here (the concat filter drives length), so each segment trims its own
    # silence via atrim in the filter chain below.
    silent_index = len(inputs)
    if not all(audio_flags):
        command += [
            "-f", "lavfi",
            "-t", "0.1",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate={_AUDIO_RATE}",
        ]

    chains = [_normalize_chain(i, width, height, fps) for i in range(len(inputs))]
    for i, has_audio in enumerate(audio_flags):
        source = f"[{i}:a]" if has_audio else f"[{silent_index}:a]"
        chains.append(
            f"{source}aresample={_AUDIO_RATE},aformat=channel_layouts=stereo[a{i}]"
        )

    pairs = "".join(f"[v{i}][a{i}]" for i in range(len(inputs)))
    chains.append(f"{pairs}concat=n={len(inputs)}:v=1:a=1[outv][outa]")

    command += [
        "-filter_complex", ";".join(chains),
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output,
    ]

    ok, stderr = _run(command, _FFMPEG_TIMEOUT_S)
    if not ok:
        return tool_error(f"ffmpeg concat failed: {stderr}", error_type="ffmpeg_failed")

    raw, _ = _probe(output)
    return tool_result(
        operation="concat",
        output_path=output,
        clips_joined=len(inputs),
        silent_clips_padded=sum(1 for flag in audio_flags if not flag),
        result=_summarize_probe(raw) if raw else None,
    )


def _handle_trim(args: Dict[str, Any]) -> str:
    inputs, err = _resolve_inputs(args.get("input_paths"))
    if err:
        return tool_error(err)
    if len(inputs) != 1:
        return tool_error("`trim` takes exactly one clip in `input_paths`.")
    output, err = _resolve_output(args.get("output_path"), "trimmed.mp4")
    if err:
        return tool_error(err)

    start = args.get("start_seconds")
    end = args.get("end_seconds")
    start = float(start) if isinstance(start, (int, float)) else 0.0
    if start < 0:
        return tool_error("`start_seconds` cannot be negative.")
    if end is not None:
        if not isinstance(end, (int, float)):
            return tool_error("`end_seconds` must be a number when provided.")
        if float(end) <= start:
            return tool_error("`end_seconds` must be greater than `start_seconds`.")

    # -ss before -i seeks on keyframes (fast but imprecise); after -i it decodes
    # to the exact frame. Editing wants the accurate cut.
    command = [_find_binary("ffmpeg"), "-y", "-i", inputs[0], "-ss", f"{start}"]
    if end is not None:
        command += ["-to", f"{float(end)}"]
    command += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output,
    ]

    ok, stderr = _run(command, _FFMPEG_TIMEOUT_S)
    if not ok:
        return tool_error(f"ffmpeg trim failed: {stderr}", error_type="ffmpeg_failed")

    raw, _ = _probe(output)
    return tool_result(
        operation="trim",
        output_path=output,
        start_seconds=start,
        end_seconds=float(end) if end is not None else None,
        result=_summarize_probe(raw) if raw else None,
    )


def _escape_drawtext(value: str) -> str:
    """Escape text for ffmpeg's drawtext filter.

    drawtext parses its own mini-syntax, so a colon or apostrophe in a caption
    otherwise breaks the filtergraph — the backslash must be doubled first or
    the later escapes get mangled.
    """
    out = value.replace("\\", "\\\\")
    for char in (":", "'", "%", ",", "[", "]", ";"):
        out = out.replace(char, "\\" + char)
    return out


# Per-process cache of `ffmpeg -filters` lookups; a binary's filter set
# cannot change while we are running.
_FILTER_SUPPORT: Dict[str, bool] = {}


def _ffmpeg_has_filter(name: str) -> bool:
    cached = _FILTER_SUPPORT.get(name)
    if cached is not None:
        return cached
    ffmpeg = _find_binary("ffmpeg")
    ok, listing = _run([ffmpeg, "-hide_banner", "-filters"], _PROBE_TIMEOUT_S)
    supported = ok and any(
        len(parts) > 1 and parts[1] == name
        for parts in (line.split() for line in listing.splitlines())
    )
    _FILTER_SUPPORT[name] = supported
    return supported


# Fonts tried for the Pillow caption fallback, split by script coverage:
# CJK captions must land on a CJK-capable font or they render as tofu boxes
# (a font FILE existing says nothing about its glyph coverage, so selection
# is by text content, not just path availability). Recent macOS no longer
# exposes PingFang.ttc under /System/Library/Fonts — Hiragino Sans GB and
# the Supplemental fonts are the reliable on-disk CJK faces there.
_CJK_FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",                       # older macOS
    "/System/Library/Fonts/Hiragino Sans GB.ttc",               # macOS
    "/System/Library/Fonts/STHeiti Medium.ttc",                 # macOS
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",     # macOS
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",   # Debian/Ubuntu
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",        # Fedora
    "C:\\Windows\\Fonts\\msyh.ttc",                             # Windows
)
_LATIN_FONT_CANDIDATES = (
    "/System/Library/Fonts/Helvetica.ttc",                      # macOS
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",     # Debian/Ubuntu
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",              # Fedora
    "C:\\Windows\\Fonts\\arial.ttf",                            # Windows
)


def _text_needs_cjk(text: str) -> bool:
    return any(
        0x2E80 <= ord(ch) <= 0x9FFF      # CJK radicals … unified ideographs
        or 0x3040 <= ord(ch) <= 0x30FF   # kana
        or 0xAC00 <= ord(ch) <= 0xD7AF   # hangul
        or 0xF900 <= ord(ch) <= 0xFAFF   # CJK compatibility ideographs
        for ch in text
    )


def _load_caption_font(size: int, text: str) -> Any:
    from PIL import ImageFont

    if _text_needs_cjk(text):
        candidates = _CJK_FONT_CANDIDATES + _LATIN_FONT_CANDIDATES
    else:
        candidates = _LATIN_FONT_CANDIDATES + _CJK_FONT_CANDIDATES
    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 has no size kwarg
        return ImageFont.load_default()


def _render_caption_png(text: str, size: int) -> Tuple[Optional[str], Optional[str]]:
    """Render ``text`` on a semi-transparent black box (matching the drawtext
    styling) to a temp PNG. Returns (path, error)."""
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        return None, (
            "this ffmpeg build lacks the drawtext filter and the Pillow "
            f"fallback is unavailable ({exc}); install an ffmpeg built with "
            "libfreetype or `pip install Pillow`."
        )
    font = _load_caption_font(size, text)
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    pad = 12  # mirrors boxborderw=12 on the drawtext path
    image = Image.new(
        "RGBA", (right - left + 2 * pad, bottom - top + 2 * pad), (0, 0, 0, 128)
    )
    ImageDraw.Draw(image).text(
        (pad - left, pad - top), text, font=font, fill=(255, 255, 255, 255)
    )
    fd, path = tempfile.mkstemp(prefix="kopi-caption-", suffix=".png")
    os.close(fd)
    image.save(path)
    return path, None


def _handle_caption(args: Dict[str, Any]) -> str:
    inputs, err = _resolve_inputs(args.get("input_paths"))
    if err:
        return tool_error(err)
    if len(inputs) != 1:
        return tool_error("`caption` takes exactly one clip in `input_paths`.")
    text = args.get("text")
    if not isinstance(text, str) or not text.strip():
        return tool_error("`caption` needs a non-empty `text`.")
    output, err = _resolve_output(args.get("output_path"), "captioned.mp4")
    if err:
        return tool_error(err)

    position = args.get("position") if isinstance(args.get("position"), str) else "bottom"
    size = args.get("font_size")
    size = size if isinstance(size, int) and 8 <= size <= 200 else 48

    caption_png: Optional[str] = None
    if _ffmpeg_has_filter("drawtext"):
        renderer = "drawtext"
        y_expr = {
            "top": "h*0.08",
            "middle": "(h-text_h)/2",
            "bottom": "h*0.86",
        }.get(position, "h*0.86")
        filter_args = [
            "-vf",
            (
                f"drawtext=text='{_escape_drawtext(text.strip())}'"
                f":fontcolor=white:fontsize={size}"
                f":box=1:boxcolor=black@0.5:boxborderw=12"
                f":x=(w-text_w)/2:y={y_expr}"
            ),
        ]
        extra_inputs: List[str] = []
    else:
        renderer = "overlay_png"
        caption_png, render_err = _render_caption_png(text.strip(), size)
        if render_err:
            return tool_error(render_err)
        y_expr = {
            "top": "main_h*0.08",
            "middle": "(main_h-overlay_h)/2",
            "bottom": "main_h*0.86",
        }.get(position, "main_h*0.86")
        extra_inputs = ["-i", caption_png]
        filter_args = [
            "-filter_complex",
            f"[0:v][1:v]overlay=x=(main_w-overlay_w)/2:y={y_expr}",
        ]

    command = [
        _find_binary("ffmpeg"), "-y", "-i", inputs[0], *extra_inputs,
        *filter_args,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output,
    ]

    try:
        ok, stderr = _run(command, _FFMPEG_TIMEOUT_S)
        if not ok:
            # `-c:a copy` fails on a clip with no audio stream; retry without it
            # rather than making the caller probe first.
            retry = [arg for arg in command if arg not in ("-c:a", "copy")]
            ok, stderr = _run(retry, _FFMPEG_TIMEOUT_S)
    finally:
        if caption_png:
            try:
                os.unlink(caption_png)
            except OSError:
                pass
    if not ok:
        return tool_error(f"ffmpeg caption failed: {stderr}", error_type="ffmpeg_failed")

    raw, _ = _probe(output)
    return tool_result(
        operation="caption",
        output_path=output,
        text=text.strip(),
        position=position,
        renderer=renderer,
        result=_summarize_probe(raw) if raw else None,
    )


def _handle_add_audio(args: Dict[str, Any]) -> str:
    inputs, err = _resolve_inputs(args.get("input_paths"))
    if err:
        return tool_error(err)
    if len(inputs) != 1:
        return tool_error("`add_audio` takes exactly one clip in `input_paths`.")
    audio_path = args.get("audio_path")
    if not isinstance(audio_path, str) or not Path(audio_path).expanduser().is_file():
        return tool_error(f"audio file not found: {audio_path}")
    output, err = _resolve_output(args.get("output_path"), "scored.mp4")
    if err:
        return tool_error(err)

    volume = args.get("audio_volume")
    volume = float(volume) if isinstance(volume, (int, float)) and volume >= 0 else 1.0

    raw, probe_err = _probe(inputs[0])
    if probe_err:
        return tool_error(f"could not probe {inputs[0]}: {probe_err}")
    keeps_original = bool(_summarize_probe(raw)["has_audio"]) and bool(
        args.get("keep_original_audio")
    )

    command = [
        _find_binary("ffmpeg"), "-y",
        "-i", inputs[0],
        "-i", str(Path(audio_path).expanduser().resolve()),
    ]
    if keeps_original:
        # Mix the bed under the existing dialogue; `duration=first` keeps the
        # video's length authoritative so a long music file cannot extend it.
        command += [
            "-filter_complex",
            f"[1:a]volume={volume}[bed];[0:a][bed]amix=inputs=2:duration=first[outa]",
            "-map", "0:v", "-map", "[outa]",
        ]
    else:
        command += [
            "-filter_complex", f"[1:a]volume={volume}[outa]",
            "-map", "0:v", "-map", "[outa]",
            "-shortest",
        ]
    command += [
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output,
    ]

    ok, stderr = _run(command, _FFMPEG_TIMEOUT_S)
    if not ok:
        return tool_error(f"ffmpeg add_audio failed: {stderr}", error_type="ffmpeg_failed")

    result_raw, _ = _probe(output)
    return tool_result(
        operation="add_audio",
        output_path=output,
        mixed_with_original=keeps_original,
        audio_volume=volume,
        result=_summarize_probe(result_raw) if result_raw else None,
    )


_OPERATIONS = {
    "probe": _handle_probe,
    "concat": _handle_concat,
    "trim": _handle_trim,
    "caption": _handle_caption,
    "add_audio": _handle_add_audio,
}


VIDEO_EDIT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": sorted(_OPERATIONS),
            "description": (
                "probe: read duration/resolution/streams. concat: join clips in "
                "order (re-encodes and normalizes, so mixed sources are fine). "
                "trim: cut one clip to a time range. caption: burn a text "
                "overlay. add_audio: lay a music or voiceover track under one clip."
            ),
        },
        "input_paths": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Video files to operate on, in order. `concat` takes two or "
                "more; every other operation takes exactly one."
            ),
        },
        "output_path": {
            "type": "string",
            "description": "Where to write the result. Defaults to a name in the CWD.",
        },
        "resolution": {
            "type": "string",
            "enum": sorted(_RESOLUTION_PRESETS),
            "description": "concat only — the frame size every clip is fitted into (default 1080p).",
        },
        "fps": {
            "type": "integer",
            "description": "concat only — frame rate for the joined output (default 30).",
        },
        "start_seconds": {"type": "number", "description": "trim only — cut in point."},
        "end_seconds": {
            "type": "number",
            "description": "trim only — cut out point. Omit to run to the end.",
        },
        "text": {"type": "string", "description": "caption only — the overlay text."},
        "position": {
            "type": "string",
            "enum": ["top", "middle", "bottom"],
            "description": "caption only — vertical placement (default bottom).",
        },
        "font_size": {
            "type": "integer",
            "description": "caption only — point size (default 48).",
        },
        "audio_path": {
            "type": "string",
            "description": "add_audio only — the music or voiceover file.",
        },
        "audio_volume": {
            "type": "number",
            "description": "add_audio only — gain for the added track, 1.0 = unchanged.",
        },
        "keep_original_audio": {
            "type": "boolean",
            "description": (
                "add_audio only — mix under the clip's existing audio instead "
                "of replacing it. Ignored when the clip is silent."
            ),
        },
    },
    "required": ["operation", "input_paths"],
    "additionalProperties": False,
}


def _handle_video_edit(args: Dict[str, Any], **_kwargs: Any) -> str:
    if not check_video_edit_requirements():
        return _missing_ffmpeg_error()
    operation = args.get("operation")
    handler = _OPERATIONS.get(operation if isinstance(operation, str) else "")
    if handler is None:
        return tool_error(
            f"unknown operation {operation!r}; expected one of {sorted(_OPERATIONS)}."
        )
    try:
        return handler(args)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("video_edit %s failed", operation)
        return tool_error(f"video_edit {operation} failed: {exc}")


registry.register(
    name="video_edit",
    toolset="video_gen",
    schema=VIDEO_EDIT_SCHEMA,
    handler=_handle_video_edit,
    check_fn=check_video_edit_requirements,
    requires_env=[],
    is_async=False,
    emoji="✂️",
)
