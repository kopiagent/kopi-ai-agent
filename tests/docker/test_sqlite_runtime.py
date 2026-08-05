"""Runtime qualification for SQLite in the published Docker image."""

from __future__ import annotations

import json
import subprocess


_SQLITE_PROBE = r"""
import json
import sqlite3

from kopi_cli.sqlite_runtime import is_sqlite_wal_reset_vulnerable

db = sqlite3.connect(":memory:")
try:
    db.execute("CREATE VIRTUAL TABLE docs USING fts5(content, tokenize='trigram')")
    db.execute("INSERT INTO docs VALUES ('kopi')")
    # 'opi' must be a real trigram of the inserted value. Upstream inserts
    # 'hermes' and matches 'erm'; the rebrand rewrote the value to 'kopi' but
    # left 'erm' alone (it contains no "hermes" substring to rewrite), so the
    # probe asked for a trigram that cannot exist and always returned 0.
    matches = db.execute(
        "SELECT count(*) FROM docs WHERE docs MATCH 'opi'"
    ).fetchone()[0]
finally:
    db.close()

print(json.dumps({
    "sqlite_version": sqlite3.sqlite_version,
    "wal_reset_vulnerable": is_sqlite_wal_reset_vulnerable(
        sqlite3.sqlite_version_info
    ),
    "trigram_matches": matches,
}))
"""


def test_image_links_fixed_sqlite_with_fts5_trigram(built_image: str) -> None:
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            "kopi",
            "--entrypoint",
            "/opt/kopi/.venv/bin/python",
            built_image,
            "-c",
            _SQLITE_PROBE,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"SQLite runtime probe failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    payload = json.loads(result.stdout)
    assert payload["wal_reset_vulnerable"] is False, payload
    assert payload["trigram_matches"] == 1, payload
