"""A small synthetic sourcebook PDF laid out like the Handbook PDFs.

The text is invented for the tests; no Handbook text is stored in this repo.
Positions and sizes copy the real layout: IDs at x = 37 in 7.2 pt bold, type
letters at x = 116, text from x = 133 in 9.9 pt, list items at x = 163.
"""

from pathlib import Path

import pymupdf
import pytest

W, H = 595, 842


def _header_footer(page: pymupdf.Page) -> None:
    page.insert_text((496, 22), "DISP", fontname="hebo", fontsize=19.2)
    page.insert_text((37, 805), "DISP Dispute Resolution:", fontname="hebo", fontsize=9.6)
    page.insert_text((322, 810), "This sourcebook was last updated in May 2026",
                     fontname="helv", fontsize=9.9)


def _marker(page, y, pid, ptype=None):
    page.insert_text((37, y + 2), pid, fontname="hebo", fontsize=7.2)
    if ptype:
        page.insert_text((116, y), ptype, fontname="helv", fontsize=7.2)


def _text(page, x, y, *parts):
    """Write one line made of (text, italic) parts."""
    for text, italic in parts:
        font = "heit" if italic else "helv"
        page.insert_text((x, y), text, fontname=font, fontsize=9.9)
        x += pymupdf.get_text_length(text, fontname=font, fontsize=9.9)


def build_sample(path: Path) -> Path:
    doc = pymupdf.open()

    # Page 1: table of contents (must be ignored).
    p = doc.new_page(width=W, height=H)
    _header_footer(p)
    p.insert_text((36, 90), "DISP 99.1 Example section", fontname="hebo", fontsize=12)

    # Page 2: a section with two provisions and a subheading.
    p = doc.new_page(width=W, height=H)
    _header_footer(p)
    p.insert_text((36, 80), "Section : DISP 99.1 Example section", fontname="hebo", fontsize=12)
    _text(p, 133, 100, ("Introductory text that belongs to no provision.", False))
    _marker(p, 130, "DISP 99.1.1", "R")
    _text(p, 133, 130, ("A firm must send a ", False), ("final response", True),
          (" within eight weeks of receiving a", False))
    _text(p, 133, 146, ("complaint", True), (". The response must:", False))
    _text(p, 163, 165, ("(1) explain the decision; and", False))
    _text(p, 163, 184, ("(2) give the address of the ", False), ("Financial", True))
    _text(p, 163, 200, ("Ombudsman Service", True), (".", False))
    p.insert_text((133, 240), "Speed of response", fontname="hebo", fontsize=12)
    _marker(p, 270, "DISP 99.1.2", "G")
    _text(p, 133, 270, ("Most complaints should be answered sooner than DISP 99.1.1R requires,",
                        False))
    _text(p, 133, 286, ("as COBS 4.7.1 R and DISP 99.1.1 R also suggest.", False))

    # Page 3: the text of DISP 99.1.2 continues, then a table, an annex, a deleted rule.
    p = doc.new_page(width=W, height=H)
    _header_footer(p)
    _text(p, 133, 70, ("This sentence continues the guidance from the previous page.", False))
    _marker(p, 110, "DISP 99.1.3", "R")
    _text(p, 133, 110, ("The firm must follow these principles:", False))
    for (ya, yb) in [(130, 160), (160, 190)]:
        for (xa, xb) in [(163, 260), (260, 506)]:
            p.draw_rect(pymupdf.Rect(xa, ya, xb, yb), color=(0, 0, 0), width=0.8)
    _text(p, 166, 148, ("1 Honesty", False))
    _text(p, 263, 148, ("A firm must be honest.", False))
    _text(p, 166, 178, ("2 Care", False))
    _text(p, 263, 178, ("A firm must take care.", False))
    _marker(p, 230, "DISP 99.1.4", "R")
    _text(p, 133, 230, ("[deleted]", False))
    p.insert_text((36, 270), "Section : DISP 99 Annex 1 Example form", fontname="hebo",
                  fontsize=12)
    _marker(p, 300, "DISP 99 Annex 1ABR")
    _text(p, 133, 300, ("Fill in every box of this form.", False))

    doc.save(path)
    return path


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory) -> Path:
    return build_sample(tmp_path_factory.mktemp("raw") / "DISP.pdf")
