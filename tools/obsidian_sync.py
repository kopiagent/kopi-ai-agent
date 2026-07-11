#!/usr/bin/env python3
"""Obsidian sync — sediment KOPI memory & skills into the vault as linked notes.

One-way export (KOPI → vault). The files under ``~/.kopi/memories/`` and
``~/.kopi/skills/`` remain the source of truth; this writes a derived,
human-browsable, graph-linked view into ``~/kopi-vault/kopi/`` so the agent's
accumulated knowledge shows up in Obsidian's graph and search.

Design:
  - Idempotent: each source entry maps to a stable ``kopi_id`` (content hash),
    which is also its filename, so re-export overwrites in place — no dupes.
  - Direct filesystem writes via ``utils.atomic_replace`` (no MCP round-trip);
    the vault is a KOPI-managed directory so we own it.
  - ``created`` is preserved across re-exports; ``updated`` refreshes.

Actions: export_all, export_memory, export_skills, status.
"""

import datetime
import hashlib
import logging
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kopi_constants import get_kopi_home
from tools.registry import registry, tool_error, tool_result
from tools.obsidian_index import get_vault_dir, _parse_frontmatter
from utils import atomic_replace

logger = logging.getLogger(__name__)

ENTRY_DELIMITER = "\n§\n"  # matches tools/memory_tool.py


def _kopi_dir() -> Path:
    return get_vault_dir() / "kopi"


def _today() -> str:
    return datetime.date.today().isoformat()


def _short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def _title_from_entry(text: str) -> str:
    """First non-empty line, trimmed to a note-title length."""
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return (line[:80]).strip()
    return "untitled"


def _read_entries(path: Path) -> List[str]:
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return [e.strip() for e in raw.split(ENTRY_DELIMITER) if e.strip()]


def _existing_created(path: Path) -> Optional[str]:
    """Preserve a note's original ``created`` date across re-exports."""
    if not path.exists():
        return None
    try:
        fm, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    val = fm.get("created")
    return str(val) if val else None


def _write_note(path: Path, frontmatter: Dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, val in frontmatter.items():
        if isinstance(val, list):
            lines.append(f"{key}: [{', '.join(str(v) for v in val)}]")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    lines.append("")
    content = "\n".join(lines) + body.rstrip() + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".obs_", suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(content)
        atomic_replace(tmp, path)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


def _sync_entries(
    entries: List[str], subdir: str, kopi_type: str, source: str, prefix: str
) -> Tuple[int, List[str]]:
    """Write each entry to kopi/<subdir>/<id>.md; prune stale files. Returns
    (count_written, [titles])."""
    target_dir = _kopi_dir() / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    today = _today()
    written_files = set()
    titles = []
    for entry in entries:
        kopi_id = f"{prefix}-{_short_hash(entry)}"
        path = target_dir / f"{kopi_id}.md"
        title = _title_from_entry(entry)
        titles.append(title)
        created = _existing_created(path) or today
        fm = {
            "kopi_type": kopi_type,
            "kopi_id": kopi_id,
            "source": source,
            "created": created,
            "updated": today,
            "tags": [f"kopi/{kopi_type}"],
        }
        body = entry if entry.lstrip().startswith("#") else f"# {title}\n\n{entry}"
        _write_note(path, fm, body)
        written_files.add(path.name)
    # Prune notes whose source entry no longer exists.
    for existing in target_dir.glob(f"{prefix}-*.md"):
        if existing.name not in written_files:
            existing.unlink(missing_ok=True)
    return len(entries), titles


def _sync_skills() -> Tuple[int, List[str]]:
    skills_root = get_kopi_home() / "skills"
    target_dir = _kopi_dir() / "skills"
    target_dir.mkdir(parents=True, exist_ok=True)
    today = _today()
    written_files = set()
    names = []
    if skills_root.exists():
        for skill_dir in sorted(skills_root.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_dir.is_dir() or not skill_md.exists():
                continue
            try:
                raw = skill_md.read_text(encoding="utf-8")
            except OSError:
                continue
            _fm, body = _parse_frontmatter(raw)
            name = skill_dir.name
            path = target_dir / f"{name}.md"
            created = _existing_created(path) or today
            fm = {
                "kopi_type": "skill",
                "kopi_id": f"skill-{name}",
                "source": f"skills/{name}/SKILL.md",
                "created": created,
                "updated": today,
                "tags": ["kopi/skill"],
            }
            note_body = body if body.lstrip().startswith("#") else f"# {name}\n\n{body}"
            _write_note(path, fm, note_body)
            written_files.add(path.name)
            # MOC links by note title — mirror how the index resolves titles
            # (first H1 in the body, else the skill name) so links don't break.
            title = _title_from_entry(note_body) or name
            names.append(title)
    for existing in target_dir.glob("*.md"):
        if existing.name not in written_files:
            existing.unlink(missing_ok=True)
    return len(names), names


def _rebuild_moc(sections: Dict[str, List[str]]) -> None:
    """Write kopi/_MOC.md — a Map of Content hub linking every sedimented note."""
    lines = [
        "---",
        "kopi_type: moc",
        f"updated: {_today()}",
        "tags: [kopi/moc]",
        "---",
        "",
        "# KOPI Knowledge — Map of Content",
        "",
        "Auto-generated by `obsidian_sync`. Do not edit by hand.",
        "",
    ]
    labels = {"memory": "Memory", "user": "About the User", "skill": "Skills"}
    for key in ("memory", "user", "skill"):
        titles = sections.get(key, [])
        lines.append(f"## {labels[key]} ({len(titles)})")
        lines.append("")
        for title in titles:
            lines.append(f"- [[{title}]]")
        lines.append("")
    path = _kopi_dir() / "_MOC.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".obs_", suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        atomic_replace(tmp, path)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


# ── Daily notes (Phase 2) ────────────────────────────────────────────────────

_MD_HEADING_TS = re.compile(r"^#+\s")


def _append_daily(content: str, title: Optional[str] = None) -> Dict[str, Any]:
    """Append a timestamped block to kopi/daily/<YYYY-MM-DD>.md, creating it
    (with frontmatter) on first write of the day. Cron digests land here."""
    today = _today()
    path = _kopi_dir() / "daily" / f"{today}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    block = content.rstrip()
    if title:
        block = f"## {title}\n\n{block}"
    if path.exists():
        try:
            base = path.read_text(encoding="utf-8").rstrip()
        except OSError:
            base = ""
    else:
        base = "\n".join([
            "---",
            "kopi_type: daily",
            f"kopi_id: daily-{today}",
            f"created: {today}",
            f"updated: {today}",
            "tags: [kopi/daily]",
            "---",
            "",
            f"# {today}",
        ])
    new_text = base + "\n\n" + block + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".obs_", suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(new_text)
        atomic_replace(tmp, path)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise
    return {"success": True, "action": "append_daily", "note": str(path)}


# ── Export core (shared by tool handler and auto-sync) ───────────────────────

def _run_export(action: str) -> Optional[Dict[str, int]]:
    """Run the requested export; returns a per-category summary, or None for an
    unknown action. Rebuilds _MOC.md so wikilinks stay consistent."""
    mem_dir = get_kopi_home() / "memories"
    sections: Dict[str, List[str]] = {}
    summary: Dict[str, int] = {}

    if action in ("export_all", "export_memory"):
        n_mem, t_mem = _sync_entries(
            _read_entries(mem_dir / "MEMORY.md"),
            "memory", "memory", "MEMORY.md", "mem",
        )
        n_user, t_user = _sync_entries(
            _read_entries(mem_dir / "USER.md"),
            "user", "user", "USER.md", "user",
        )
        sections["memory"], sections["user"] = t_mem, t_user
        summary["memory"], summary["user"] = n_mem, n_user

    if action in ("export_all", "export_skills"):
        n_skill, t_skill = _sync_skills()
        sections["skill"] = t_skill
        summary["skills"] = n_skill

    if not summary:
        return None

    _rebuild_moc(sections)
    return summary


# ── Tool handler ────────────────────────────────────────────────────────────

def _handle_obsidian_sync(args: dict, **kwargs) -> str:
    action = (args.get("action") or "export_all").strip()

    try:
        if action == "status":
            kopi = _kopi_dir()
            counts = {
                sub: len(list((kopi / sub).glob("*.md"))) if (kopi / sub).exists() else 0
                for sub in ("memory", "user", "skills", "daily")
            }
            return tool_result(
                success=True, vault=str(get_vault_dir()),
                notes=counts, auto_sync=auto_sync_enabled(),
            )

        if action == "append_daily":
            content = (args.get("content") or "").strip()
            if not content:
                return tool_error("append_daily requires 'content'")
            return tool_result(**_append_daily(content, args.get("title")))

        summary = _run_export(action)
        if summary is None:
            return tool_error(f"Unknown action: {action}")
        return tool_result(
            success=True, action=action, vault=str(get_vault_dir()), exported=summary,
        )
    except OSError as exc:
        return tool_error(f"Obsidian sync failed: {exc}")


# ── Auto-sync hook (Phase 2) ─────────────────────────────────────────────────
#
# Memory writes and skill mutations can fire an incremental re-export so the
# vault tracks the agent's knowledge in near-real-time. This is OPT-IN
# (config obsidian.auto_sync or env KOPI_OBSIDIAN_AUTO_SYNC) and defaults OFF:
# auto-writing to the vault on every memory mutation is a side effect users
# should choose, and a default-on hook would write into ~/kopi-vault during
# unrelated test runs. Work runs on a debounced daemon thread so it never adds
# latency to the triggering write, and every failure is swallowed (sediment is
# best-effort; it must never break a memory/skill write).

_DEBOUNCE_SECONDS = 2.0
_pending: set = set()
_pending_lock = threading.Lock()
_worker: Optional["threading.Thread"] = None


def auto_sync_enabled() -> bool:
    env = os.environ.get("KOPI_OBSIDIAN_AUTO_SYNC")
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes", "on")
    try:
        from kopi_cli.config import load_config
        return bool((load_config().get("obsidian") or {}).get("auto_sync", False))
    except Exception:
        return False


def _drain() -> None:
    time.sleep(_DEBOUNCE_SECONDS)  # coalesce a burst of writes into one export
    while True:
        with _pending_lock:
            if not _pending:
                return
            _pending.clear()
        try:
            _run_export("export_all")
        except Exception as exc:  # sediment is best-effort — never propagate
            logger.debug("obsidian auto-sync export failed: %s", exc)


def trigger_auto_sync(kind: str) -> None:
    """Best-effort hook: schedule a debounced vault re-export. No-op unless
    auto-sync is enabled and the vault exists. Never raises."""
    try:
        if not auto_sync_enabled() or not get_vault_dir().exists():
            return
        with _pending_lock:
            _pending.add(kind)
            global _worker
            if _worker is not None and _worker.is_alive():
                return
            _worker = threading.Thread(
                target=_drain, name="obsidian-auto-sync", daemon=True,
            )
            _worker.start()
    except Exception:
        pass


OBSIDIAN_SYNC_SCHEMA = {
    "name": "obsidian_sync",
    "description": (
        "Export KOPI's curated memory (MEMORY.md, USER.md) and learned skills "
        "into the Obsidian vault as linked, frontmatter-tagged notes under "
        "kopi/. One-way (KOPI is source of truth), idempotent, and rebuilds a "
        "_MOC.md hub. Use to sediment accumulated knowledge into a browsable, "
        "graph-linked knowledge base. action=append_daily writes a dated "
        "journal entry under kopi/daily/ (for digests and daily notes)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "export_all", "export_memory", "export_skills",
                    "append_daily", "status",
                ],
                "description": "Which action to run (default: export_all).",
            },
            "content": {
                "type": "string",
                "description": "Markdown body to append (action=append_daily).",
            },
            "title": {
                "type": "string",
                "description": "Optional H2 heading for the daily entry (action=append_daily).",
            },
        },
        "required": [],
    },
}


registry.register(
    name="obsidian_sync",
    toolset="obsidian",
    schema=OBSIDIAN_SYNC_SCHEMA,
    handler=_handle_obsidian_sync,
    requires_env=[],
    is_async=False,
    description="Export KOPI memory & skills into the Obsidian vault",
    emoji="\U0001f5c3️",
)
