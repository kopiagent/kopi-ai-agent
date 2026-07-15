#!/usr/bin/env python3
"""Obsidian query — headless replication of Obsidian desktop's read intelligence.

Obsidian's desktop app derives its graph, backlinks, Dataview tables, and
ranked search entirely from the vault's markdown files. This tool rebuilds the
same index headless (see tools/obsidian_index.py) and exposes those capabilities
as a single ``obsidian_query`` tool — so the agent gets "desktop-like" vault
intelligence without a running Obsidian app or the Local REST API plugin.

Actions:
  search         BM25 full-text search
  backlinks      notes linking to a given note
  outlinks       notes a given note links to
  dataview       filter/sort notes by frontmatter fields or tag
  orphans        notes with no links in or out
  broken_links   [[wikilinks]] that resolve to nothing
  graph          the link neighborhood of a note
"""

import logging

from tools.registry import registry, tool_error, tool_result
from tools.obsidian_index import VaultIndex, get_vault_dir

logger = logging.getLogger(__name__)


def _handle_obsidian_query(args: dict, **kwargs) -> str:
    action = (args.get("action") or "search").strip()
    vault = get_vault_dir()
    if not vault.exists():
        return tool_error(f"Vault not found at {vault}. Nothing indexed yet.")

    idx = VaultIndex.load(vault)
    limit = int(args.get("limit") or 10)

    try:
        if action == "search":
            query = (args.get("query") or "").strip()
            if not query:
                return tool_error("search requires 'query'")
            return tool_result(success=True, action=action, results=idx.search(query, limit))

        if action in ("backlinks", "outlinks", "graph"):
            note = (args.get("note") or "").strip()
            if not note:
                return tool_error(f"{action} requires 'note' (title or path)")
            if action == "backlinks":
                return tool_result(success=True, action=action, note=note, backlinks=idx.backlinks(note))
            if action == "outlinks":
                return tool_result(success=True, action=action, note=note, outlinks=idx.outlinks(note))
            depth = int(args.get("depth") or 1)
            return tool_result(success=True, action=action, note=note, graph=idx.graph(note, depth))

        if action == "dataview":
            return tool_result(
                success=True,
                action=action,
                rows=idx.dataview(
                    where=args.get("where") or {},
                    sort=args.get("sort"),
                    limit=int(args.get("limit") or 50),
                ),
            )

        if action == "orphans":
            return tool_result(success=True, action=action, orphans=idx.orphans())

        if action == "broken_links":
            return tool_result(success=True, action=action, broken_links=idx.broken_links())

        return tool_error(f"Unknown action: {action}")
    except (OSError, ValueError) as exc:
        return tool_error(f"Obsidian query failed: {exc}")


OBSIDIAN_QUERY_SCHEMA = {
    "name": "obsidian_query",
    "description": (
        "THE tool for searching the user's notes, vault, knowledge base, wiki, or "
        "memory notes. Use this whenever the user asks to search, find, look up, or "
        "recall something in their notes/vault/knowledge base — prefer it over "
        "generic file search (search_files/grep) because it RANKS results (BM25), "
        "handles Chinese/CJK text (plain grep does not), and understands links. "
        "Queries the Obsidian vault with desktop-like intelligence, headless (no "
        "Obsidian app needed): full-text search, backlinks/outlinks, a Dataview-"
        "style frontmatter query, orphan and broken-link detection, and link-graph "
        "traversal. Only fall back to search_files for exact filename listing or a "
        "raw regex sweep where ranking is not wanted."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "search", "backlinks", "outlinks",
                    "dataview", "orphans", "broken_links", "graph",
                ],
                "description": "Which query to run (default: search).",
            },
            "query": {"type": "string", "description": "Search text (action=search)."},
            "note": {
                "type": "string",
                "description": "Note title or path (backlinks/outlinks/graph).",
            },
            "where": {
                "type": "object",
                "description": (
                    "Frontmatter equality filters for action=dataview. Special key "
                    "'tag' matches tag membership. e.g. {\"kopi_type\": \"skill\"}."
                ),
            },
            "sort": {"type": "string", "description": "Frontmatter field to sort by (dataview)."},
            "depth": {"type": "integer", "description": "Graph traversal depth (default 1)."},
            "limit": {"type": "integer", "description": "Max results (default 10; dataview 50)."},
        },
        "required": [],
    },
}


registry.register(
    name="obsidian_query",
    toolset="obsidian",
    schema=OBSIDIAN_QUERY_SCHEMA,
    handler=_handle_obsidian_query,
    requires_env=[],
    is_async=False,
    description="Query the Obsidian vault (search, backlinks, dataview, graph)",
    emoji="\U0001f50d",
)
