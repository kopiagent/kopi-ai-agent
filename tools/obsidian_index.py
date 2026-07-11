#!/usr/bin/env python3
"""Obsidian vault index — the shared scanner behind obsidian_sync and obsidian_query.

Obsidian's desktop "magic" (backlink graph, Dataview queries, ranked search)
is not stored anywhere outside the vault files — the app rebuilds it by scanning
the markdown on launch. This module does the same thing headless: it walks
``~/kopi-vault/**/*.md``, parses frontmatter, tags, and ``[[wikilinks]]``, and
builds an in-memory index (link graph + frontmatter table + BM25 corpus) that
both the exporter and the query tool read.

The index is cached to ``~/.kopi/obsidian-index.json`` and refreshed
incrementally by mtime — only changed/new files are re-parsed, so a query pays
almost nothing when the vault is unchanged.

Source of truth is always the vault files themselves; this cache is a derived
accelerator and is safe to delete.
"""

import datetime
import json
import logging
import math
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kopi_constants import get_kopi_home

logger = logging.getLogger(__name__)

# Vault location — resolved to match the bundled upstream `obsidian` skill
# (skills/note-taking/obsidian) and scripts/kopi-bootstrap-config.py so the
# index, mcpvault, and the file-level skill all point at ONE vault.
#
# Precedence follows upstream Hermes: OBSIDIAN_VAULT_PATH is the canonical env
# var. KOPI_OBSIDIAN_VAULT is a backward-compatible alias. The fallback matches
# the skill's documented default.
def get_vault_dir() -> Path:
    path = os.environ.get("OBSIDIAN_VAULT_PATH") or os.environ.get("KOPI_OBSIDIAN_VAULT")
    if path:
        return Path(path).expanduser()
    return Path.home() / "Documents" / "Obsidian Vault"


def _index_cache_path() -> Path:
    return get_kopi_home() / "obsidian-index.json"


# Staging folder for two-way import (obsidian_sync action=import). Excluded from
# the index so unimported/quarantined notes never appear in queries.
_INBOX_REL = os.path.join("kopi", "inbox")


# ── Parsing helpers ─────────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
# [[target]] or [[target|alias]] or [[target#heading]] — capture the target.
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
# Inline #tag (word chars, slash, hyphen). Excludes bare '#' headings via \w start.
_INLINE_TAG_RE = re.compile(r"(?:^|\s)#([\w/][\w/\-]*)")
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
# Latin/digit words. CJK, kana, and Hangul have no word breaks, so they are
# tokenized per-character (unigram) below — otherwise `[a-z0-9]+` would drop
# every Chinese/Japanese/Korean character and CJK content could never match.
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[一-鿿㐀-䶿぀-ヿ가-힯]")


def _json_safe(value: Any) -> Any:
    """Coerce YAML-parsed scalars (date/datetime) into JSON-serializable forms.

    ``yaml.safe_load`` turns ``created: 2026-07-11`` into a ``datetime.date``,
    which breaks both the JSON index cache and tool_result serialization.
    Normalize the whole frontmatter tree once, here, so everything downstream
    is JSON-safe.
    """
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Split YAML frontmatter from the body. Returns (frontmatter_dict, body)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    import yaml
    try:
        fm = yaml.safe_load(m.group(1)) or {}
        if not isinstance(fm, dict):
            fm = {}
    except yaml.YAMLError:
        fm = {}
    return _json_safe(fm), text[m.end():]


def _extract_tags(frontmatter: Dict[str, Any], body: str) -> List[str]:
    tags: List[str] = []
    fm_tags = frontmatter.get("tags")
    if isinstance(fm_tags, str):
        tags.extend(t.strip() for t in fm_tags.replace(",", " ").split())
    elif isinstance(fm_tags, list):
        tags.extend(str(t).strip() for t in fm_tags)
    tags.extend(_INLINE_TAG_RE.findall(body))
    # De-dup, preserve order.
    seen = set()
    out = []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _title_of(path: Path, frontmatter: Dict[str, Any], body: str) -> str:
    """Obsidian resolves [[links]] by note title: H1 → filename stem."""
    m = _H1_RE.search(body)
    if m:
        return m.group(1).strip()
    return path.stem


def _tokenize(text: str) -> List[str]:
    lowered = text.lower()
    # Latin/digit words plus per-character CJK/kana/Hangul unigrams, so a query
    # like "咖啡" matches a note containing "深烘咖啡豆".
    return _TOKEN_RE.findall(lowered) + _CJK_RE.findall(lowered)


def _parse_note(vault: Path, path: Path) -> Optional[Dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    frontmatter, body = _parse_frontmatter(text)
    rel = str(path.relative_to(vault))
    return {
        "path": rel,
        "title": _title_of(path, frontmatter, body),
        "frontmatter": frontmatter,
        "tags": _extract_tags(frontmatter, body),
        "outlinks": _WIKILINK_RE.findall(body),  # raw target titles
        "body": body,
        "mtime": path.stat().st_mtime,
    }


# ── Index ───────────────────────────────────────────────────────────────────

class VaultIndex:
    """Parsed vault + link graph. Load via ``VaultIndex.load()``."""

    def __init__(self, notes: Dict[str, Dict[str, Any]]):
        self.notes = notes  # rel_path -> note dict
        self._title_to_path: Dict[str, str] = {}
        self._backlinks: Dict[str, List[str]] = defaultdict(list)
        self._rebuild_graph()

    def _rebuild_graph(self) -> None:
        self._title_to_path = {}
        for rel, note in self.notes.items():
            # Later note with same title loses; first-write wins (stable).
            self._title_to_path.setdefault(note["title"], rel)
        self._backlinks = defaultdict(list)
        for rel, note in self.notes.items():
            for target_title in note["outlinks"]:
                target_rel = self._title_to_path.get(target_title.strip())
                if target_rel and rel not in self._backlinks[target_rel]:
                    self._backlinks[target_rel].append(rel)

    # ---- construction / caching ----

    @classmethod
    def load(cls, vault: Optional[Path] = None) -> "VaultIndex":
        """Load the index, refreshing changed files incrementally against cache."""
        vault = vault or get_vault_dir()
        cached = cls._read_cache()
        on_disk = {}
        if vault.exists():
            for path in vault.rglob("*.md"):
                if not path.is_file():
                    continue
                rel = str(path.relative_to(vault))
                # kopi/inbox/ is a staging area for two-way import, not part of
                # the knowledge graph. Excluding it keeps unimported (and
                # quarantined/rejected) notes out of search, orphans, and links.
                if rel == _INBOX_REL or rel.startswith(_INBOX_REL + os.sep):
                    continue
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                prev = cached.get(rel)
                if prev and prev.get("mtime") == mtime:
                    on_disk[rel] = prev  # unchanged — reuse parsed entry
                else:
                    parsed = _parse_note(vault, path)
                    if parsed:
                        on_disk[rel] = parsed
        idx = cls(on_disk)
        idx._write_cache()
        return idx

    @staticmethod
    def _read_cache() -> Dict[str, Dict[str, Any]]:
        p = _index_cache_path()
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("notes", {})
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_cache(self) -> None:
        p = _index_cache_path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                json.dumps({"notes": self.notes}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Could not write obsidian index cache: %s", exc)

    # ---- queries (the desktop "思路", headless) ----

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """BM25-ranked full-text search across note bodies + titles."""
        q_terms = _tokenize(query)
        if not q_terms:
            return []
        docs = list(self.notes.items())
        N = len(docs)
        if N == 0:
            return []
        # Doc term frequencies + lengths.
        doc_tokens = {rel: _tokenize(n["title"] + " " + n["body"]) for rel, n in docs}
        doc_len = {rel: len(toks) or 1 for rel, toks in doc_tokens.items()}
        avgdl = sum(doc_len.values()) / N
        df: Dict[str, int] = defaultdict(int)
        tf: Dict[str, Dict[str, int]] = {}
        for rel, toks in doc_tokens.items():
            counts: Dict[str, int] = defaultdict(int)
            for t in toks:
                counts[t] += 1
            tf[rel] = counts
            for t in set(toks):
                df[t] += 1
        k1, b = 1.5, 0.75
        scored = []
        for rel, _note in docs:
            score = 0.0
            for t in q_terms:
                if t not in tf[rel]:
                    continue
                idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
                freq = tf[rel][t]
                denom = freq + k1 * (1 - b + b * doc_len[rel] / avgdl)
                score += idf * (freq * (k1 + 1)) / denom
            if score > 0:
                scored.append((score, rel))
        scored.sort(reverse=True)
        return [
            {"path": rel, "title": self.notes[rel]["title"], "score": round(score, 4)}
            for score, rel in scored[:limit]
        ]

    def _resolve(self, note_ref: str) -> Optional[str]:
        """Resolve a note reference (path or title) to a rel path."""
        if note_ref in self.notes:
            return note_ref
        return self._title_to_path.get(note_ref.strip())

    def backlinks(self, note_ref: str) -> List[str]:
        rel = self._resolve(note_ref)
        return list(self._backlinks.get(rel, [])) if rel else []

    def outlinks(self, note_ref: str) -> List[str]:
        rel = self._resolve(note_ref)
        if not rel:
            return []
        out = []
        for target_title in self.notes[rel]["outlinks"]:
            resolved = self._title_to_path.get(target_title.strip())
            out.append(resolved or target_title)  # unresolved: keep raw
        return out

    def orphans(self) -> List[str]:
        """Notes with no incoming and no (resolvable) outgoing links."""
        result = []
        for rel, note in self.notes.items():
            has_out = any(
                self._title_to_path.get(t.strip()) for t in note["outlinks"]
            )
            has_in = bool(self._backlinks.get(rel))
            if not has_out and not has_in:
                result.append(rel)
        return result

    def broken_links(self) -> List[Dict[str, str]]:
        """[[links]] that don't resolve to any note."""
        broken = []
        for rel, note in self.notes.items():
            for target in note["outlinks"]:
                if not self._title_to_path.get(target.strip()):
                    broken.append({"from": rel, "target": target})
        return broken

    def dataview(
        self,
        where: Optional[Dict[str, Any]] = None,
        sort: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Filter/sort notes by frontmatter fields — Dataview's core, headless.

        ``where`` matches frontmatter equality; the special key ``tag`` matches
        membership in a note's tag set.
        """
        where = where or {}
        rows = []
        for rel, note in self.notes.items():
            fm = note["frontmatter"]
            ok = True
            for key, val in where.items():
                if key == "tag":
                    if val not in note["tags"]:
                        ok = False
                        break
                elif fm.get(key) != val:
                    ok = False
                    break
            if ok:
                rows.append({"path": rel, "title": note["title"], **fm})
        if sort:
            rows.sort(key=lambda r: r.get(sort, ""))
        return rows[:limit]

    def graph(self, note_ref: str, depth: int = 1) -> Dict[str, List[str]]:
        """Neighborhood: connected notes up to ``depth`` hops (both directions)."""
        start = self._resolve(note_ref)
        if not start:
            return {}
        result: Dict[str, List[str]] = {}
        frontier = {start}
        seen = {start}
        for _ in range(max(1, depth)):
            next_frontier = set()
            for rel in frontier:
                neighbors = set(self.backlinks(rel))
                for t in self.notes[rel]["outlinks"]:
                    r = self._title_to_path.get(t.strip())
                    if r:
                        neighbors.add(r)
                result[rel] = sorted(neighbors)
                next_frontier |= neighbors - seen
            seen |= next_frontier
            frontier = next_frontier
            if not frontier:
                break
        return result
