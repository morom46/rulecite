"""Turn a Handbook sourcebook PDF into one record per provision.

The PDFs from handbook.fca.org.uk ("View Sourcebook as PDF") have a fixed
layout, and the parser reads that layout rather than the plain text:

* each provision's ID is printed small and bold in the left margin, with its
  type letter (R, G, E, D) just to the right of it, level with the first line
  of its text;
* the text itself sits in a column starting about 133 points from the left;
* a section starts with a line "Section : DISP 1.6 Complaints time limit rules";
* subheadings inside a section are 12 point bold, in the text column;
* every page has the same header and footer, which are skipped;
* chapter title pages use very large type and are skipped.

Run:  python -m rulecite.ingest            (reads data/raw/*.pdf)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from .ids import BOOKS, TYPES, find_references, parse_id, split_citation, strip_type
from .records import Rule, save_rules

# Layout thresholds, in PDF points (an A4 page is 595 x 842).
HEADER_Y = 40          # anything starting above this is the page header
FOOTER_Y = 780         # anything starting below this is the page footer
MARKER_MAX_SIZE = 8.0  # provision IDs and type letters are 7.2 pt
MARKER_MAX_X = 90      # IDs start at about x = 37
TYPE_MAX_X = 132       # type letters start at about x = 116
BODY_MIN_X = 100       # the text column starts at about x = 133
HEADING_MIN_SIZE = 11.5
TITLE_PAGE_SIZE = 20   # chapter title pages use 21.6 and 24 pt
PARAGRAPH_GAP = 17.3   # lines inside a paragraph are 15.8 pt apart; paragraphs 18.8+
SAME_LINE = 6.0        # an ID and the first line of its text differ by about 2 pt

_ITEM_RE = re.compile(r"^\s*(?:\((?:\d+[A-Za-z]*|[a-z]{1,4}|[ivxlc]+)\)|\[Note|Note:|•)")
_DELETED_RE = re.compile(r"^\[?\s*deleted\s*\]?\.?$", re.IGNORECASE)
_UPDATED_RE = re.compile(r"last updated in ([A-Z][a-z]+ \d{4})")


@dataclass
class Line:
    page: int
    x: float
    y: float
    size: float
    bold: bool
    text: str
    italic_runs: list[str] = field(default_factory=list)
    starts_italic: bool = False   # the line begins inside an italic phrase
    ends_italic: bool = False     # the line ends inside an italic phrase
    table_row: bool = False       # one row of a table, cells joined with " | "


@dataclass
class IngestReport:
    """What happened while parsing one PDF, for the summary and the tests."""

    book: str
    pages: int = 0
    last_updated: str = ""
    sha256: str = ""
    provisions: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    deleted: int = 0
    no_type: list[str] = field(default_factory=list)       # IDs printed without a type letter
    empty: list[str] = field(default_factory=list)         # IDs with no text at all
    continued: list[str] = field(default_factory=list)     # IDs printed twice (text continued)
    orphan_lines: int = 0                                  # body lines before the first ID of a section


def read_lines(doc: pymupdf.Document) -> list[Line]:
    """Every text line in the document, with position, size and italic runs."""
    out: list[Line] = []
    for pno, page in enumerate(doc, start=1):
        tables = _table_rows(page, pno)
        out.extend(row for _, row in tables)
        boxes = [box for box, _ in tables]
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                size = max(s["size"] for s in spans)
                cx = (line["bbox"][0] + line["bbox"][2]) / 2
                cy = (line["bbox"][1] + line["bbox"][3]) / 2
                if size >= MARKER_MAX_SIZE and any(b.contains(pymupdf.Point(cx, cy)) for b in boxes):
                    continue                     # already read as part of a table row
                text = "".join(s["text"] for s in line["spans"])
                runs, cur = [], []
                for s in line["spans"]:
                    if s["flags"] & 2 and s["text"].strip():   # italic
                        cur.append(s["text"])
                    elif cur:
                        runs.append("".join(cur)); cur = []
                if cur:
                    runs.append("".join(cur))
                out.append(Line(
                    page=pno,
                    x=line["bbox"][0],
                    y=line["bbox"][1],
                    size=size,
                    bold=all(s["flags"] & 16 for s in spans),
                    text=text,
                    italic_runs=[r.strip() for r in runs],
                    starts_italic=bool(spans[0]["flags"] & 2),
                    ends_italic=bool(spans[-1]["flags"] & 2),
                ))
    return out


def _table_rows(page: pymupdf.Page, pno: int) -> list[tuple[pymupdf.Rect, Line]]:
    """Tables on a page, one Line per row with cells joined by " | ".

    PyMuPDF finds the table grid; the words in each cell are then read with
    their spacing intact (its own cell text drops the spaces in these PDFs).
    Tables that start in the left margin are skipped (see below), so a few
    annex forms are read line by line, with their columns run together.
    """
    rows: list[tuple[pymupdf.Rect, Line]] = []
    words = page.get_text("words")
    for table in page.find_tables().tables:
        box = pymupdf.Rect(table.bbox)
        # Real tables sit inside the text column. A "table" that starts in the
        # left margin is the page layout itself (IDs in one column, text in
        # another), found by mistake: read those pages line by line instead.
        if box.x0 < BODY_MIN_X:
            continue
        for row in table.rows:
            cells = []
            for cell in row.cells:
                if cell is None:
                    continue
                r = pymupdf.Rect(cell)
                inside = [w for w in words
                          if r.contains(pymupdf.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2))]
                inside.sort(key=lambda w: (round(w[1]), w[0]))
                text = " ".join(w[4] for w in inside).strip()
                if text:
                    cells.append(text)
            if cells:
                rb = pymupdf.Rect(row.bbox)
                rows.append((box, Line(page=pno, x=max(rb.x0, BODY_MIN_X), y=rb.y0, size=9.9,
                                       bold=False, text=" | ".join(cells), table_row=True)))
    return rows


def _sort_key(ln: Line) -> tuple[int, float, float]:
    # An ID is printed level with the first line of its text, about 2 pt lower.
    # Moving IDs up a little puts them before that line.
    nudge = SAME_LINE if ln.size < MARKER_MAX_SIZE else 0.0
    return (ln.page, ln.y - nudge, ln.x)


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def _join(lines: list[Line]) -> str:
    """Join body lines into text: list items and paragraphs start new lines."""
    out = ""
    prev: Line | None = None
    for ln in lines:
        t = _clean(ln.text)
        if not t:
            continue
        new_para = (
            prev is None
            or ln.table_row or prev.table_row
            or _ITEM_RE.match(t) is not None
            or (ln.page == prev.page and ln.y - prev.y > PARAGRAPH_GAP)
        )
        out += ("\n" if out and new_para else (" " if out else "")) + t
        prev = ln
    return out.strip()


def parse_pdf(path: Path, book: str | None = None) -> tuple[list[Rule], IngestReport]:
    """Parse one sourcebook PDF into rule records."""
    doc = pymupdf.open(path)
    lines = read_lines(doc)
    book = book or path.stem.upper()
    report = IngestReport(book=book, pages=len(doc),
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    # The footer says when the sourcebook was last updated.
    for ln in lines[:40]:
        m = _UPDATED_RE.search(ln.text)
        if m:
            report.last_updated = m.group(1)
            break

    body = [ln for ln in lines if HEADER_Y <= ln.y <= FOOTER_Y and ln.size < TITLE_PAGE_SIZE]
    body.sort(key=_sort_key)

    # Type letters, found by position next to each ID.
    type_marks = [ln for ln in body
                  if ln.size < MARKER_MAX_SIZE and not ln.bold and MARKER_MAX_X <= ln.x < TYPE_MAX_X]

    def type_for(marker: Line) -> str:
        best = ""
        for t in type_marks:
            if t.page == marker.page and abs(t.y - marker.y) < SAME_LINE:
                best = _clean(t.text)
                break
        return best if best in TYPES else ""

    rules: dict[str, Rule] = {}
    order: list[str] = []
    text_lines: dict[str, list[Line]] = {}
    italics: dict[str, list[str]] = {}
    current: str | None = None
    section_title = ""
    heading = ""

    for ln in body:
        t = _clean(ln.text)
        if ln.size < MARKER_MAX_SIZE:
            if ln.bold and ln.x < MARKER_MAX_X:          # a provision ID
                printed_type = ""
                try:
                    pid = parse_id(t)
                except ValueError:
                    # A few annex IDs carry their type letter: "DISP 1 Annex 1ABR".
                    base, printed_type = split_citation(t)
                    pid = parse_id(base)
                if pid.text in rules:                     # printed again: text continues
                    report.continued.append(pid.text)
                else:
                    ptype = type_for(ln) or printed_type
                    rules[pid.text] = Rule(
                        id=pid.text, type=ptype, book=pid.book, kind=pid.kind,
                        chapter=pid.chapter, section=pid.section,
                        section_title=section_title, heading=heading, page=ln.page,
                    )
                    order.append(pid.text)
                    text_lines[pid.text] = []
                    italics[pid.text] = []
                    if not ptype:
                        report.no_type.append(pid.text)
                current = pid.text
            continue                                       # type letters are handled above

        if ln.size >= HEADING_MIN_SIZE and ln.bold:
            if t.startswith("Section :") or t.startswith("Section:"):
                m = re.match(r"^Section\s*:\s*(.+)$", t)
                section_title = _section_title(m.group(1)) if m else ""
                heading = ""
                current = None                            # text before the first ID is not a rule
            elif ln.x >= BODY_MIN_X:
                heading = t
                current = None
            continue                                      # table-of-contents entries

        if ln.x < BODY_MIN_X:
            continue
        if current is None:
            report.orphan_lines += 1
            continue
        runs = list(ln.italic_runs)
        prev_lines = text_lines[current]
        if runs and prev_lines and prev_lines[-1].ends_italic and ln.starts_italic and italics[current]:
            italics[current][-1] += " " + runs.pop(0)      # a term broken across two lines
        text_lines[current].append(ln)
        italics[current].extend(runs)

    out: list[Rule] = []
    for pid in order:
        r = rules[pid]
        r.text = _join(text_lines[pid])
        r.deleted = bool(_DELETED_RE.match(r.text))
        r.refs = [x for x in find_references(r.text) if x != r.id]
        r.terms = _terms(italics[pid])
        if not r.text:
            report.empty.append(pid)
        out.append(r)

    report.provisions = len(out)
    report.deleted = sum(r.deleted for r in out)
    for r in out:
        report.by_type[r.type or "-"] = report.by_type.get(r.type or "-", 0) + 1
    return out, report


def _section_title(s: str) -> str:
    """The words after the section number.

    >>> _section_title("DISP 1.6 Complaints time limit rules")
    'Complaints time limit rules'
    >>> _section_title("DISP 1 Annex 1AB Claims management complaints return form")
    'Claims management complaints return form'
    >>> _section_title("PRIN 2A.2 Cross-cutting obligations")
    'Cross-cutting obligations'
    """
    s = _clean(s)
    m = re.match(r"^[A-Z]{2,6}\s+(?:(?:App|Sch|TP|INTRO)\s+)?\d+[A-Z]{0,2}(?:\.\d+[A-Z]{0,2})?"
                 r"(?:\s+Annex\s+\d+[A-Z]{0,2})?\s*(.*)$", s)
    return m.group(1) if m else s


def _terms(runs: list[str]) -> list[str]:
    """Glossary terms: italic phrases, minus references and punctuation."""
    out: list[str] = []
    for run in runs:
        t = re.sub(r"['\u2019]s$", "", run.strip(" .,;:()[]'\"")).strip()
        if len(t) < 3 or find_references(t) or re.search(r"\d", t):
            continue
        t = t.lower()
        if t not in out:
            out.append(t)
    return out


def ingest(raw_dir: Path, out_dir: Path, books: tuple[str, ...] = BOOKS) -> list[IngestReport]:
    """Parse every sourcebook PDF in raw_dir and write rules.jsonl and manifest.json."""
    all_rules: list[Rule] = []
    reports: list[IngestReport] = []
    for book in books:
        path = raw_dir / f"{book}.pdf"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing. See data/README.md for how to download it.")
        rules, report = parse_pdf(path, book)
        all_rules.extend(rules)
        reports.append(report)
    known = {r.id for r in all_rules}
    for r in all_rules:
        refs = [strip_type(x, known) for x in r.refs]
        r.refs = [x for i, x in enumerate(refs) if x != r.id and x not in refs[:i]]
    save_rules(all_rules, out_dir / "rules.jsonl")
    manifest = {r.book: {"file": f"{r.book}.pdf", "sha256": r.sha256, "pages": r.pages,
                         "last_updated": r.last_updated, "provisions": r.provisions,
                         "deleted": r.deleted, "by_type": r.by_type}
                for r in reports}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return reports


def print_summary(reports: list[IngestReport], file=sys.stdout) -> None:
    print(f"{'book':<6} {'updated':<15} {'pages':>5} {'provisions':>10} {'R':>5} {'G':>5} "
          f"{'other':>5} {'deleted':>7}", file=file)
    for r in reports:
        other = r.provisions - r.by_type.get("R", 0) - r.by_type.get("G", 0)
        print(f"{r.book:<6} {r.last_updated:<15} {r.pages:>5} {r.provisions:>10} "
              f"{r.by_type.get('R', 0):>5} {r.by_type.get('G', 0):>5} {other:>5} {r.deleted:>7}",
              file=file)
    total = sum(r.provisions - r.deleted for r in reports)
    print(f"\n{total} provisions indexed (deleted ones are kept in the file but not indexed).",
          file=file)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--out", type=Path, default=Path("data/processed"))
    args = ap.parse_args(argv)
    reports = ingest(args.raw, args.out)
    print_summary(reports)
    compare_snapshot(reports, args.raw.parent / "snapshot.json")
    return 0


def compare_snapshot(reports: list[IngestReport], snapshot: Path, file=sys.stdout) -> bool:
    """Say whether these PDFs are the ones the published results were made with."""
    if not snapshot.exists():
        return True
    books = json.loads(snapshot.read_text())["books"]
    same = True
    for r in reports:
        expected = books.get(r.book, {})
        if expected.get("sha256") != r.sha256:
            same = False
            print(f"note: {r.book}.pdf differs from the snapshot in data/snapshot.json "
                  f"(yours: last updated {r.last_updated or 'unknown'}, snapshot: "
                  f"{expected.get('last_updated', 'none')}). The FCA has probably updated it, "
                  f"so results may differ slightly from the README.", file=file)
    if same:
        print("PDFs match data/snapshot.json: results are comparable with the README.", file=file)
    return same


if __name__ == "__main__":
    raise SystemExit(main())
