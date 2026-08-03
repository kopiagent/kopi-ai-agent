"""deliver_pdf's value is the font verdict: a PDF whose fonts were swapped
for different-metric substitutes reflows silently, which is exactly the
"the PDF looks different" failure dual delivery must prevent. These tests
pin the OOXML font extraction, the kept/metric-safe/risky classification,
and that the powerpoint and docx skill copies never drift apart. The full
soffice conversion runs only where LibreOffice is installed."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PPTX_COPY = REPO / "skills/productivity/powerpoint/scripts/deliver_pdf.py"
DOCX_COPY = REPO / "skills/productivity/docx/scripts/deliver_pdf.py"


def load_module():
    spec = importlib.util.spec_from_file_location("deliver_pdf_skill", PPTX_COPY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_skill_copies_are_identical():
    """Both skills ship the same script; edits must land in both."""
    assert PPTX_COPY.read_text(encoding="utf-8") == DOCX_COPY.read_text(encoding="utf-8")


def _write_zip(path: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return path


def test_extracts_fonts_from_pptx_and_skips_theme_placeholders(tmp_path):
    mod = load_module()
    deck = _write_zip(
        tmp_path / "deck.pptx",
        {
            "ppt/slides/slide1.xml": (
                '<p:sp xmlns:a="x"><a:latin typeface="Calibri"/>'
                '<a:latin typeface="+mn-lt"/><a:ea typeface="PingFang SC"/></p:sp>'
            ),
            "ppt/theme/theme1.xml": '<a:latin xmlns:a="x" typeface="Cambria"/>',
        },
    )
    assert mod.requested_fonts(deck) == {"Calibri", "PingFang SC", "Cambria"}


def test_extracts_fonts_from_docx_rfonts(tmp_path):
    mod = load_module()
    doc = _write_zip(
        tmp_path / "r.docx",
        {
            "word/document.xml": (
                '<w:rFonts xmlns:w="x" w:ascii="Georgia" w:hAnsi="Georgia" '
                'w:eastAsia="SimSun"/>'
            )
        },
    )
    assert mod.requested_fonts(doc) == {"Georgia", "SimSun"}


def test_xlsx_val_attr_counts_only_in_styles(tmp_path):
    mod = load_module()
    book = _write_zip(
        tmp_path / "b.xlsx",
        {
            "xl/styles.xml": '<name xmlns="x" val="Arial"/>',
            "xl/workbook.xml": '<definedName val="NotAFont"/>',
        },
    )
    assert mod.requested_fonts(book) == {"Arial"}


def test_classify_kept_metric_safe_and_risky():
    mod = load_module()
    report = mod.classify(
        {"Arial", "Calibri", "Fancy Demo Font"},
        {"Arial", "Carlito", "LiberationSerif"},
    )
    assert report["kept"] == ["Arial"]
    assert report["metric_safe_substitutions"] == [
        {"requested": "Calibri", "substituted_with": "carlito"}
    ]
    assert report["risky"] == ["Fancy Demo Font"]
    assert report["verdict"] == "check_layout"


def test_classify_all_good_is_ok():
    mod = load_module()
    report = mod.classify({"Times New Roman"}, {"LiberationSerif"})
    assert report["risky"] == []
    assert report["verdict"] == "ok"


def test_pdf_font_names_strip_subset_and_style_tags(tmp_path):
    mod = load_module()
    pdf = tmp_path / "f.pdf"
    pdf.write_bytes(
        b"%PDF-1.4 /BaseFont /ABCDEF+Carlito-Bold /BaseFont /LiberationSerif"
    )
    # force the poppler-less fallback so the regex path is what's tested
    real_which = shutil.which
    try:
        shutil.which = lambda name: None if name == "pdffonts" else real_which(name)
        assert mod.pdf_fonts(pdf) == {"Carlito", "LiberationSerif"}
    finally:
        shutil.which = real_which


needs_soffice = pytest.mark.skipif(
    shutil.which("soffice") is None, reason="LibreOffice not installed"
)


@needs_soffice
def test_end_to_end_conversion_flags_missing_font(tmp_path):
    doc = _write_zip(
        tmp_path / "report.docx",
        {
            "[Content_Types].xml": (
                '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
                'package/2006/content-types"><Default Extension="rels" ContentType='
                '"application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" ContentType="application/'
                'vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
            ),
            "_rels/.rels": (
                '<?xml version="1.0"?><Relationships xmlns="http://schemas.'
                'openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/officeDocument" Target="word/document.xml"/></Relationships>'
            ),
            "word/document.xml": (
                '<?xml version="1.0"?><w:document xmlns:w="http://schemas.'
                'openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                '<w:p><w:r><w:rPr><w:rFonts w:ascii="Fancy Demo Font"/></w:rPr>'
                "<w:t>hello</w:t></w:r></w:p></w:body></w:document>"
            ),
        },
    )
    result = subprocess.run(
        [sys.executable, str(DOCX_COPY), str(doc)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert Path(report["pdf"]).exists()
    assert "Fancy Demo Font" in report["risky"]
    assert report["verdict"] == "check_layout"
