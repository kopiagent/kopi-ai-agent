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

import atexit
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


_H1_LINE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _note_title(path: Path) -> str:
    """First H1 in a note, else its filename stem — matches how the index
    resolves titles, so MOC wikilinks resolve to real pages."""
    try:
        m = _H1_LINE_RE.search(path.read_text(encoding="utf-8"))
    except OSError:
        return path.stem
    return m.group(1).strip() if m else path.stem


def _rebuild_moc() -> None:
    """Write kopi/_MOC.md from the CURRENT vault contents (scans the kopi/
    subdirs), not just the notes touched this run — so an incremental export
    (e.g. memory-only) never drops the Skills section from the hub."""
    kopi = _kopi_dir()
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
    for subdir, label in (("memory", "Memory"), ("user", "About the User"), ("skills", "Skills")):
        d = kopi / subdir
        titles = sorted(_note_title(f) for f in d.glob("*.md")) if d.exists() else []
        lines.append(f"## {label} ({len(titles)})")
        lines.append("")
        for title in titles:
            lines.append(f"- [[{title}]]")
        lines.append("")
    path = kopi / "_MOC.md"
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


# ── Two-way import (Phase 3): vault inbox → curated memory ───────────────────
#
# Optional reverse flow. The agent normally exports memory → vault; this brings
# user-authored notes the other way. It is SAFE by construction:
#   - Source is kopi/inbox/ ONLY (never the export targets kopi/memory|user),
#     so there is no import↔export loop.
#   - Every note is routed through MemoryStore.add(), which runs the same
#     injection/exfiltration scan (_scan_memory_content) that guards the memory
#     tool, plus dedup and char-limit enforcement. Poisoned or oversized notes
#     are rejected and left in the inbox with a reason — never silently trusted.
#   - It is explicit (a tool action), never a hook and never automatic.
# Imported notes move to kopi/inbox/imported/ so they aren't re-imported and
# stay auditable.

_LEADING_H1_RE = re.compile(r"^\s*#\s+.*\n+")


def _import_from_inbox() -> Dict[str, Any]:
    inbox = _kopi_dir() / "inbox"
    if not inbox.exists():
        return {
            "success": True, "action": "import", "imported": 0, "skipped": [],
            "note": f"No inbox to import from. Create {inbox} and drop notes there.",
        }
    from tools.memory_tool import load_on_disk_store
    store = load_on_disk_store()
    done_dir = inbox / "imported"
    imported = 0
    skipped: List[Dict[str, str]] = []
    for note in sorted(inbox.glob("*.md")):
        try:
            raw = note.read_text(encoding="utf-8")
        except OSError as exc:
            skipped.append({"note": note.name, "reason": f"unreadable: {exc}"})
            continue
        fm, body = _parse_frontmatter(raw)
        body = _LEADING_H1_RE.sub("", body, count=1).strip()  # drop a title heading
        if not body:
            skipped.append({"note": note.name, "reason": "empty after frontmatter/title"})
            continue
        target = "user" if str(fm.get("kopi_target", "")).lower() == "user" else "memory"
        # add() runs the injection scan, dedup, and char-limit checks, then persists.
        result = store.add(target, body)
        if result.get("success"):
            imported += 1
            done_dir.mkdir(parents=True, exist_ok=True)
            try:
                note.rename(done_dir / note.name)
            except OSError:
                pass  # imported into memory already; leaving it in inbox is safe
        else:
            skipped.append({"note": note.name, "reason": result.get("error", "rejected")})
    return {
        "success": True, "action": "import",
        "imported": imported, "skipped": skipped,
        "vault": str(get_vault_dir()),
    }


# ── Export core (shared by tool handler and auto-sync) ───────────────────────

def _run_export(action: str) -> Optional[Dict[str, int]]:
    """Run the requested export; returns a per-category summary, or None for an
    unknown action. Rebuilds _MOC.md so wikilinks stay consistent."""
    mem_dir = get_kopi_home() / "memories"
    summary: Dict[str, int] = {}

    if action in ("export_all", "export_memory"):
        n_mem, _ = _sync_entries(
            _read_entries(mem_dir / "MEMORY.md"),
            "memory", "memory", "MEMORY.md", "mem",
        )
        n_user, _ = _sync_entries(
            _read_entries(mem_dir / "USER.md"),
            "user", "user", "USER.md", "user",
        )
        summary["memory"], summary["user"] = n_mem, n_user

    if action in ("export_all", "export_skills"):
        n_skill, _ = _sync_skills()
        summary["skills"] = n_skill

    if not summary:
        return None

    _rebuild_moc()
    return summary


def _export_pending(kinds: set) -> None:
    """Export only the groups actually touched (memory/user share one pass;
    skills another). Keeps short-lived-process exit cheap — a lone memory
    write no longer re-writes every skill note. The MOC self-rebuilds from
    full vault state, so partial exports stay consistent."""
    if kinds & {"memory", "user"}:
        _run_export("export_memory")
    if "skills" in kinds:
        _run_export("export_skills")


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

        if action == "import":
            return tool_result(_import_from_inbox())

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
        # Read-only, cached, no defensive deepcopy — this runs on every memory
        # write (to decide whether the hook fires), so keep it cheap.
        from kopi_cli.config import load_config_readonly
        return bool((load_config_readonly().get("obsidian") or {}).get("auto_sync", False))
    except Exception:
        return False


def _drain() -> None:
    time.sleep(_DEBOUNCE_SECONDS)  # coalesce a burst of writes into one export
    while True:
        with _pending_lock:
            if not _pending:
                return
            kinds = set(_pending)
            _pending.clear()
        try:
            _export_pending(kinds)
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


@atexit.register
def _flush_pending_on_exit() -> None:
    """Run any still-pending export synchronously at interpreter shutdown.

    The debounce thread is a daemon, so in short-lived processes (a `kopi -z`
    one-shot, a cron job that writes one memory and exits) it can be killed
    mid-sleep before the export runs. This flush guarantees the sediment lands
    even when the process exits within the debounce window. Best-effort.
    """
    try:
        with _pending_lock:
            if not _pending:
                return
            kinds = set(_pending)
            _pending.clear()
        _export_pending(kinds)
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
        "journal entry under kopi/daily/. action=import pulls user-authored "
        "notes from kopi/inbox/ back INTO curated memory — each note is run "
        "through the same injection scan, dedup, and char-limit checks as the "
        "memory tool; rejected notes stay in the inbox with a reason."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "export_all", "export_memory", "export_skills",
                    "append_daily", "import", "status",
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
