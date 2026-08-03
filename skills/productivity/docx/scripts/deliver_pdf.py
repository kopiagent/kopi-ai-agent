#!/usr/bin/env python3
"""Dual delivery: convert an OOXML document to PDF and PROVE the fonts held.

"Convert to PDF" is the easy half. The half that actually protects the
layout is checking what LibreOffice did to the fonts: it silently
substitutes any font it can't find, and a substitute with different
metrics reflows lines and shifts page/slide breaks — the classic
"the PDF looks different" bug. This script converts, then reads the
fonts actually embedded in the produced PDF and classifies every
requested font as:

  - kept            — the font itself made it into the PDF
  - metric_safe     — replaced by its metric-compatible twin
                      (Calibri→Carlito, Arial→Liberation Sans/Arimo, …):
                      same widths, layout preserved
  - risky           — replaced by something with different metrics:
                      the PDF may not match the source. Fix the source
                      font or install the real font, then re-run.

Usage:
    python3 deliver_pdf.py <file.pptx|file.docx|file.xlsx> [--outdir DIR]

Prints JSON with the pdf path and the font verdict. Exit 1 only when the
conversion itself fails; font warnings are reported in `verdict` so the
caller decides.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Metric-compatible substitution pairs. LibreOffice ships the Liberation
# family and Carlito/Caladea precisely so these swaps don't move a single
# line break. Keys and values are normalized (lowercase, no spaces).
_METRIC_TWINS = {
    "calibri": {"carlito"},
    "cambria": {"caladea"},
    "arial": {"liberationsans", "arimo"},
    "helvetica": {"liberationsans", "arimo"},
    "timesnewroman": {"liberationserif", "tinos"},
    "couriernew": {"liberationmono", "cousine"},
    "georgia": {"gelasio"},
}

# Theme placeholders and control names that are not real font requests.
_NON_FONTS = {"", "+mn-lt", "+mj-lt", "+mn-ea", "+mj-ea", "+mn-cs", "+mj-cs"}

_FONT_ATTR_RE = re.compile(
    r'(?:typeface|w:ascii|w:hAnsi|w:eastAsia|w:cs|val)="([^"]+)"'
)


def _norm(name: str) -> str:
    return re.sub(r"[\s\-_]", "", name).lower()


def requested_fonts(document: Path) -> set[str]:
    """Every font family referenced in the OOXML zip's XML parts."""
    fonts: set[str] = set()
    with zipfile.ZipFile(document) as zf:
        for member in zf.namelist():
            if not member.endswith(".xml"):
                continue
            # Only font-bearing parts: document/slide/styles/theme XML.
            xml = zf.read(member).decode("utf-8", errors="replace")
            if member.startswith("xl/") and member != "xl/styles.xml":
                continue
            for match in _FONT_ATTR_RE.finditer(xml):
                name = match.group(1).strip()
                if name in _NON_FONTS or name.startswith("+"):
                    continue
                # `val="..."` is only a font inside <name val="..."/> (xlsx
                # styles) — for other files the attr matches too much, so
                # keep val= hits only from xl/styles.xml.
                if match.group(0).startswith('val="') and member != "xl/styles.xml":
                    continue
                fonts.add(name)
    return fonts


def _run_soffice(document: Path, outdir: Path) -> Path:
    """Convert via the sibling office/soffice.py wrapper (sandbox-safe);
    fall back to bare soffice when the wrapper is absent."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from office.soffice import run_soffice  # type: ignore
    except ImportError:
        def run_soffice(args, **kwargs):  # type: ignore
            return subprocess.run(["soffice"] + list(args), **kwargs)

    if not shutil.which("soffice"):
        print(
            "soffice not found — install LibreOffice "
            "(macOS: brew install --cask libreoffice; "
            "Debian/Ubuntu: sudo apt install -y libreoffice).",
            file=sys.stderr,
        )
        sys.exit(1)
    result = run_soffice(
        ["--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(document)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    pdf = outdir / (document.stem + ".pdf")
    if result.returncode != 0 or not pdf.exists():
        print(
            f"conversion failed: {result.stderr.strip() or result.stdout.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)
    return pdf


def pdf_fonts(pdf: Path) -> set[str]:
    """Font base names actually embedded/referenced in the PDF."""
    pdffonts = shutil.which("pdffonts")
    names: set[str] = set()
    if pdffonts:
        out = subprocess.run(
            [pdffonts, str(pdf)], capture_output=True, text=True, timeout=60
        ).stdout
        for line in out.splitlines()[2:]:  # skip the two header lines
            if line.strip():
                names.add(line.split()[0])
    else:
        # Poppler-less fallback: /BaseFont entries in the raw PDF.
        raw = pdf.read_bytes().decode("latin-1", errors="replace")
        names.update(re.findall(r"/BaseFont\s*/([#\w+\-.]+)", raw))
    cleaned = set()
    for name in names:
        base = name.split("+", 1)[-1]        # strip the ABCDEF+ subset tag
        base = base.split("-", 1)[0]         # strip -Bold / -Italic style
        base = base.split(",", 1)[0]         # strip ,Bold variants
        cleaned.add(base)
    return cleaned


def classify(requested: set[str], produced: set[str]) -> dict:
    produced_norm = {_norm(p) for p in produced}
    kept, metric_safe, risky = [], [], []
    for font in sorted(requested):
        n = _norm(font)
        if n in produced_norm or any(p.startswith(n) or n.startswith(p) for p in produced_norm):
            kept.append(font)
        elif _METRIC_TWINS.get(n, set()) & produced_norm:
            twin = sorted(_METRIC_TWINS[n] & produced_norm)[0]
            metric_safe.append({"requested": font, "substituted_with": twin})
        else:
            risky.append(font)
    return {
        "kept": kept,
        "metric_safe_substitutions": metric_safe,
        "risky": risky,
        "verdict": "ok" if not risky else "check_layout",
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("--outdir", type=Path, default=None)
    args = parser.parse_args(argv)

    document = args.document.resolve()
    if not document.exists():
        print(f"no such file: {document}", file=sys.stderr)
        sys.exit(1)
    outdir = (args.outdir or document.parent).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    requested = requested_fonts(document)
    pdf = _run_soffice(document, outdir)
    produced = pdf_fonts(pdf)
    report = classify(requested, produced)

    result = {
        "document": str(document),
        "pdf": str(pdf),
        "requested_fonts": sorted(requested),
        "pdf_fonts": sorted(produced),
        **report,
    }
    if report["risky"]:
        result["fix"] = (
            "these fonts were replaced with different-metric substitutes; the "
            "PDF layout may not match the source. Either switch the document "
            "to fonts on this machine (safe: Arial, Calibri, Cambria, Times "
            "New Roman, Courier New) or install the missing fonts, then re-run."
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
