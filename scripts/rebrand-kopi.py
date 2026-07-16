#!/usr/bin/env python3
"""
KOPI AI AGENT — Full rebrand script.
Transforms kopi-ai-agent → kopi-ai-agent with all brand references updated.
"""
import os, re, shutil, sys
from pathlib import Path

SRC = Path("/root/kopi-ai-agent")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".kopi", ".kopi"}
SKIP_EXTS = {".pyc", ".pyo", ".so", ".dll", ".dylib", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".ogg"}

BRAND = "KOPI AI AGENT"
COMPANY = "Kopi Ai Agent Pte Ltd (Singapore)"
COMPANY_OLD = "Kopi Ai Agent Pte Ltd|Kopi Ai Agent Pte Ltd"

replacements = {
    # === Brand names (order matters: most specific first) ===
    "KOPI AI AGENT": "KOPI AI AGENT",
    "kopi-ai-agent": "kopi-ai-agent",
    # === Home directory ===
    ".kopi/": ".kopi/",
    ".kopi": ".kopi",
    # === CLI / package ===
    "kopi ": "kopi ",
    # === Env vars (case-sensitive) ===
    "KOPI_HOME": "KOPI_HOME",
    "KOPI_CONFIG": "KOPI_CONFIG",
    "KOPI_": "KOPI_",
    # === URLs ===
    "github.com/kopiagent/kopi-ai-agent": "github.com/kopiagent/kopi-ai-agent",
    "github.com/LINYIQ66": "github.com/LINYIQ66",
    "nousresearch/kopi-ai-agent": "kopiagent/kopi-ai-agent",
    # === Module names ===
    "from kopi": "from kopi",
    "import kopi": "import kopi",
    "kopi/": "kopi/",
}

# These paths should be skipped (binary, third-party, etc.)
def should_skip(path):
    rel = path.relative_to(SRC)
    for part in rel.parts:
        if part in SKIP_DIRS:
            return True
    if path.suffix in SKIP_EXTS:
        return True
    return False

def rebrand_file(filepath):
    """Rebrand text content in a single file."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except (UnicodeDecodeError, PermissionError):
        return 0

    original = content
    for old, new in replacements.items():
        content = content.replace(old, new)

    # Special: Kopi Ai Agent Pte Ltd / Kopi Ai Agent Pte Ltd → Company name
    content = re.sub(r'Nous\s*Research', 'Kopi Ai Agent Pte Ltd', content)

    # Special: KOPI AI AGENT (double-branding fix)
    content = content.replace("KOPI AI AGENT", "KOPI AI AGENT")

    if content != original:
        filepath.write_text(content, encoding="utf-8")
        return 1
    return 0

def rename_items(root, is_dir=False):
    """Rename files/dirs that contain 'kopi' in the name."""
    renamed = 0
    for item in list(root.iterdir()):
        if item.name.startswith("."):
            continue
        if is_dir and not item.is_dir():
            continue
        if not is_dir and not item.is_file():
            continue

        new_name = item.name
        new_name = new_name.replace("kopi", "kopi")
        new_name = new_name.replace("Hermes", "Kopi")

        if new_name != item.name:
            new_path = item.with_name(new_name)
            if not new_path.exists():
                item.rename(new_path)
                renamed += 1
    return renamed

def main():
    total_files = 0
    total_changed = 0
    renamed_files = 0
    renamed_dirs = 0

    # Phase 1: Rebrand file contents
    print("=== Phase 1: Rebranding file contents ===")
    for f in SRC.rglob("*"):
        if f.is_file() and not should_skip(f):
            total_files += 1
            changed = rebrand_file(f)
            if changed:
                total_changed += 1

    # Phase 2: Rename files
    print("=== Phase 2: Renaming files ===")
    for f in SRC.rglob("*"):
        if f.is_file() and not should_skip(f):
            renamed_files += rename_items(f.parent, is_dir=False)

    # Phase 3: Rename directories (bottom-up)
    print("=== Phase 3: Renaming directories ===")
    all_dirs = sorted([d for d in SRC.rglob("*") if d.is_dir()], key=lambda x: len(str(x)), reverse=True)
    for d in all_dirs:
        renamed_dirs += rename_items(d, is_dir=True)

    print(f"\n{'='*50}")
    print(f"Total files scanned: {total_files}")
    print(f"Files content changed: {total_changed}")
    print(f"Files renamed: {renamed_files}")
    print(f"Directories renamed: {renamed_dirs}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
