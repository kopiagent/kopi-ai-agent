"""KOPI Memory provider — MemoryProvider interface for kopi-agent-memory.

Production-grade multi-layer memory with Hot/Warm/Cold tiers:
- Hot: Redis (session state, <1ms)
- Warm: PostgreSQL + pgvector (semantic search, ~5ms)
- Cold: S3/MinIO (archive, ~100ms)

Config via environment variables:
  KOPI_MEMORY_API_URL    — kopi-memory service URL (default: http://localhost:8900)
  KOPI_MEMORY_API_KEY    — JWT auth key (optional, for authenticated endpoints)
  KOPI_MEMORY_USER_ID    — user/agent identifier (default: "kopi")
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "http://localhost:8900"
_TIMEOUT = 30  # seconds


def _config(key: str, default: str = "") -> str:
    """Read config from env var, falling back to default."""
    return os.environ.get(f"KOPI_MEMORY_{key}", default)


class KopiMemoryProvider(MemoryProvider):
    """Memory provider backed by kopi-agent-memory REST API."""

    @property
    def name(self) -> str:
        return "kopi"

    # ----------------------------------------------------------------
    # Core lifecycle
    # ----------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if the kopi-memory API is reachable.

        Lightweight check — just verifies the URL env var is set or
        fallback is usable. No network call.
        """
        self._api_url = _config("API_URL", _DEFAULT_API_URL)
        self._api_key = _config("API_KEY", "")
        self._user_id = _config("USER_ID", "kopi")
        return bool(self._api_url)  # URL is always set (has default)

    def initialize(self, session_id: str, **kwargs) -> None:
        """Initialize the provider for a session.

        Sets up the HTTP client and records session metadata.
        """
        self._session_id = session_id
        self._headers = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            self._headers["Authorization"] = f"Bearer {self._api_key}"

        # Session metadata from kwargs
        self._platform = kwargs.get("platform", "cli")
        self._agent_context = kwargs.get("agent_context", "primary")
        self._agent_identity = kwargs.get("agent_identity", "")

        logger.info(
            "KopiMemory: initialized for session %s (platform=%s, context=%s)",
            session_id[:8], self._platform, self._agent_context,
        )

    def system_prompt_block(self) -> str:
        """Return system prompt instructions for the model."""
        return (
            "## KOPI Memory\n"
            "You have access to a persistent multi-layer memory system.\n"
            "You can search past conversations and store important facts.\n"
            "Use the `memory_search` tool to recall relevant context.\n"
            "Use the `memory_save` tool to store important information.\n"
            "Important facts and user preferences should be saved explicitly."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Recall relevant memories for the upcoming turn.

        Calls the kopi-memory search endpoint to find semantically
        relevant context from past sessions.
        """
        sid = session_id or self._session_id
        if not query.strip():
            return ""

        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(
                    f"{self._api_url}/v1/memories/search",
                    headers=self._headers,
                    json={
                        "query": query,
                        "user_id": self._user_id,
                        "limit": 5,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    memories = data.get("results", [])
                    if memories:
                        lines = []
                        for m in memories[:5]:
                            content = m.get("content", "")
                            category = m.get("category", "general")
                            importance = m.get("importance", "medium")
                            lines.append(
                                f"[{category}] ({importance}) {content}"
                            )
                        return "## KOPI Memory Recall\n" + "\n".join(lines)
        except httpx.RequestError as e:
            logger.warning("KopiMemory prefetch failed: %s", e)

        return ""

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: List[Dict[str, Any]] | None = None,
    ) -> None:
        """Persist the current turn to memory.

        Stores the user-assistant exchange in the warm tier for
        future retrieval.
        """
        sid = session_id or self._session_id
        if not user_content.strip():
            return

        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                # Store user message
                client.post(
                    f"{self._api_url}/v1/memories",
                    headers=self._headers,
                    json={
                        "content": user_content,
                        "user_id": self._user_id,
                        "category": "conversation",
                        "metadata": {
                            "session_id": sid,
                            "platform": self._platform,
                            "role": "user",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    },
                )
                # Store assistant response (if non-trivial)
                if len(assistant_content) > 20:
                    client.post(
                        f"{self._api_url}/v1/memories",
                        headers=self._headers,
                        json={
                            "content": assistant_content[:500],  # truncate
                            "user_id": self._user_id,
                            "category": "conversation",
                            "importance": "low",
                            "metadata": {
                                "session_id": sid,
                                "platform": self._platform,
                                "role": "assistant",
                                "timestamp": datetime.now(
                                    timezone.utc
                                ).isoformat(),
                            },
                        },
                    )
        except httpx.RequestError as e:
            logger.debug("KopiMemory sync_turn skipped: %s", e)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Expose memory tools to the model."""
        return [
            {
                "name": "memory_search",
                "description": (
                    "Search past memories and conversations using semantic "
                    "search. Results are ranked by relevance."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (1-20)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "memory_save",
                "description": (
                    "Save an important fact, preference, or insight "
                    "to persistent memory. Saved items are available "
                    "across future sessions."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The fact or insight to save",
                        },
                        "category": {
                            "type": "string",
                            "description": (
                                "Category: preference, fact, instruction, "
                                "relationship, project, or general"
                            ),
                            "enum": [
                                "preference",
                                "fact",
                                "instruction",
                                "relationship",
                                "project",
                                "general",
                            ],
                            "default": "general",
                        },
                        "importance": {
                            "type": "string",
                            "description": "Importance level",
                            "enum": ["low", "medium", "high", "critical"],
                            "default": "medium",
                        },
                    },
                    "required": ["content"],
                },
            },
            {
                "name": "memory_forget",
                "description": "Remove a specific memory by its ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "string",
                            "description": "The memory ID to delete",
                        },
                    },
                    "required": ["memory_id"],
                },
            },
        ]

    def handle_tool_call(
        self, tool_name: str, args: Dict[str, Any], **kwargs
    ) -> str:
        """Dispatch tool calls to the kopi-memory API."""
        handlers = {
            "memory_search": self._handle_search,
            "memory_save": self._handle_save,
            "memory_forget": self._handle_forget,
        }
        handler = handlers.get(tool_name)
        if not handler:
            raise NotImplementedError(
                f"KopiMemory: unknown tool {tool_name}"
            )
        return handler(args, **kwargs)

    def shutdown(self) -> None:
        """Clean shutdown."""
        logger.info("KopiMemory: shut down")

    # ----------------------------------------------------------------
    # Optional hooks
    # ----------------------------------------------------------------

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """Extract key insights when a session ends.

        Summarizes the conversation and stores it as a high-level
        memory for future retrieval.
        """
        if len(messages) < 4:
            return  # too short to summarize

        try:
            # Send to timeline endpoint for session summarization
            with httpx.Client(timeout=_TIMEOUT) as client:
                client.post(
                    f"{self._api_url}/v1/timeline/{self._user_id}",
                    headers=self._headers,
                    json={
                        "event_type": "session_end",
                        "content": (
                            f"End of session {self._session_id[:8]} "
                            f"({len(messages)} messages)"
                        ),
                        "metadata": {
                            "session_id": self._session_id,
                            "platform": self._platform,
                            "message_count": len(messages),
                        },
                    },
                )
        except httpx.RequestError as e:
            logger.debug("KopiMemory on_session_end skipped: %s", e)

    def on_delegation(
        self,
        task: str,
        result: str,
        *,
        child_session_id: str = "",
        **kwargs,
    ) -> None:
        """Record delegation events as memories."""
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                client.post(
                    f"{self._api_url}/v1/memories",
                    headers=self._headers,
                    json={
                        "content": f"Delegated: {task[:200]}",
                        "user_id": self._user_id,
                        "category": "delegation",
                        "importance": "low",
                        "metadata": {
                            "session_id": self._session_id,
                            "child_session_id": child_session_id,
                            "result_preview": result[:200],
                        },
                    },
                )
        except httpx.RequestError as e:
            logger.debug("KopiMemory on_delegation skipped: %s", e)

    # ----------------------------------------------------------------
    # Tool handlers
    # ----------------------------------------------------------------

    def _handle_search(
        self, args: Dict[str, Any], **kwargs
    ) -> str:
        query = args.get("query", "")
        limit = min(args.get("limit", 5), 20)

        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(
                    f"{self._api_url}/v1/memories/search",
                    headers=self._headers,
                    json={
                        "query": query,
                        "user_id": self._user_id,
                        "limit": limit,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    memories = data.get("results", [])
                    if not memories:
                        return json.dumps({
                            "status": "no_results",
                            "message": "No relevant memories found.",
                        })

                    results = []
                    for m in memories:
                        results.append({
                            "id": m.get("id", ""),
                            "content": m.get("content", ""),
                            "category": m.get("category", "general"),
                            "importance": m.get("importance", "medium"),
                            "similarity": m.get("similarity", 0),
                        })
                    return json.dumps({
                        "status": "success",
                        "count": len(results),
                        "memories": results,
                    })
                else:
                    return json.dumps({
                        "status": "error",
                        "message": f"Search failed: {resp.status_code}",
                    })
        except httpx.RequestError as e:
            return json.dumps({
                "status": "error",
                "message": f"KOPI Memory unavailable: {e}",
            })

    def _handle_save(
        self, args: Dict[str, Any], **kwargs
    ) -> str:
        content = args.get("content", "")
        category = args.get("category", "general")
        importance = args.get("importance", "medium")

        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(
                    f"{self._api_url}/v1/memories",
                    headers=self._headers,
                    json={
                        "content": content,
                        "user_id": self._user_id,
                        "category": category,
                        "importance": importance,
                        "metadata": {
                            "session_id": self._session_id,
                            "platform": self._platform,
                            "saved_at": datetime.now(
                                timezone.utc
                            ).isoformat(),
                        },
                    },
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return json.dumps({
                        "status": "saved",
                        "memory_id": data.get("id", ""),
                        "message": f"Memory saved ({category}, {importance})",
                    })
                else:
                    return json.dumps({
                        "status": "error",
                        "message": f"Save failed: {resp.status_code}",
                    })
        except httpx.RequestError as e:
            return json.dumps({
                "status": "error",
                "message": f"KOPI Memory unavailable: {e}",
            })

    def _handle_forget(
        self, args: Dict[str, Any], **kwargs
    ) -> str:
        memory_id = args.get("memory_id", "")

        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.delete(
                    f"{self._api_url}/v1/memories/{memory_id}",
                    headers=self._headers,
                )
                if resp.status_code in (200, 204):
                    return json.dumps({
                        "status": "deleted",
                        "memory_id": memory_id,
                    })
                else:
                    return json.dumps({
                        "status": "error",
                        "message": (
                            f"Delete failed: {resp.status_code}"
                        ),
                    })
        except httpx.RequestError as e:
            return json.dumps({
                "status": "error",
                "message": f"KOPI Memory unavailable: {e}",
            })

    # ----------------------------------------------------------------
    # Config schema (for 'kopi memory setup')
    # ----------------------------------------------------------------

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "api_url",
                "description": "KOPI Memory API URL",
                "required": True,
                "default": _DEFAULT_API_URL,
                "url": "https://github.com/LINYIQ66/kopi-agent-memory",
            },
            {
                "key": "api_key",
                "description": "KOPI Memory API key (JWT)",
                "secret": True,
                "required": False,
                "env_var": "KOPI_MEMORY_API_KEY",
            },
            {
                "key": "user_id",
                "description": "User/agent identifier",
                "required": False,
                "default": "kopi",
            },
        ]

    def save_config(self, values: Dict[str, Any], kopi_home: str) -> None:
        """Write non-secret config to a JSON file in the profile."""
        import json as _json
        from pathlib import Path

        config_dir = Path(kopi_home) / "kopi-memory"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "config.json"

        existing = {}
        if config_file.exists():
            existing = _json.loads(config_file.read_text())

        existing.update(values)
        config_file.write_text(
            _json.dumps(existing, indent=2, ensure_ascii=False)
        )
        logger.info(
            "KopiMemory: config written to %s", config_file
        )

    def backup_paths(self) -> List[str]:
        """Include any local config stored outside KOPI_HOME."""
        return []


# Plugin entry point — the discovery system looks for this function
def create_provider() -> MemoryProvider:
    """Create a KopiMemoryProvider instance."""
    return KopiMemoryProvider()
