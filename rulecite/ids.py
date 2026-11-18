"""Handbook provision IDs: parsing, citation form, and finding references in text.

A provision in the FCA Handbook has an ID such as ``DISP 1.6.2`` and a type
letter such as ``R`` (rule) or ``G`` (guidance). The Handbook usually cites the
two together, with or without a space: ``DISP 1.6.2R`` or ``DISP 1.6.2 R``.
This module keeps the two apart, and builds the citation form ``DISP 1.6.2R``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# The three sourcebooks this project indexes.
BOOKS = ("DISP", "BCOBS", "PRIN")

# Type letters used in the Handbook margin.
TYPES = {
    "R": "rule",
    "G": "guidance",
    "E": "evidential provision",
    "D": "direction",
    "P": "statement of principle",
    "C": "conclusive evidence",
    "UK": "UK legislation",
    "EU": "EU legislation",
}

# Handbook module codes that may appear in cross-references. Used only to
# recognise references in text; the index itself contains the three BOOKS.
MODULES = (
    "PRIN SYSC COND APER COCON FIT FINMAR TC GEN FEES COBS ICOBS MCOB BCOBS "
    "CMCOB CONC CASS MAR PROD ESG DISP CONRED COMP COLL CREDS SUP DEPP EG "
    "PERG LR UKLR PR DTR FUND RCB BIPRU GENPRU IPRU MIFIDPRU INSPRU PROF "
    "SECU PTRM CTPS COLLG"
).split()

_KIND_WORDS = ("App", "Sch", "TP", "INTRO")

# Book, optional kind word, then the numbered part. The numbered part may have
# letters (1.1A, 2A.4), a dash form (1.1.5-A, 3.4.-1), or "N Annex N".
_ID_RE = re.compile(
    r"^(?P<book>[A-Z]{2,6})\s+"
    r"(?:(?P<kind>App|Sch|TP|INTRO)\s+)?"
    r"(?P<num>\d+[A-Z]{0,2}(?:\s+Annex\s+\d+[A-Z]{0,2}|(?:\.-?\d*[A-Z]{0,2}(?:-[A-Z0-9]+)?)*))$"
)


@dataclass(frozen=True)
class ProvisionId:
    """A parsed provision ID such as ``DISP 1.6.2A`` or ``DISP App 3.2.1``."""

    text: str      # the ID exactly as printed, e.g. "DISP 1.6.2A"
    book: str      # "DISP"
    kind: str      # "rule", "annex", "app", "sch", "tp" or "intro"
    chapter: str   # "DISP 1", "DISP App 3", "DISP Sch 3", "DISP 1" (for an annex)
    section: str   # "DISP 1.6", "DISP App 3.2", or the chapter when there is none


def parse_id(text: str) -> ProvisionId:
    """Parse a provision ID as printed in the Handbook margin.

    >>> parse_id("DISP 1.6.2A").section
    'DISP 1.6'
    >>> parse_id("DISP App 3.2.1").chapter
    'DISP App 3'
    """
    text = " ".join(text.split())
    m = _ID_RE.match(text)
    if not m:
        raise ValueError(f"not a provision ID: {text!r}")
    book, kind_word, num = m.group("book"), m.group("kind"), m.group("num")
    prefix = f"{book} {kind_word} " if kind_word else f"{book} "

    if "Annex" in num:
        chapter_no = num.split()[0]
        kind = "annex"
        chapter = prefix + chapter_no
        section = text
    else:
        parts = num.split(".")
        chapter = prefix + parts[0]
        kind = kind_word.lower() if kind_word else "rule"
        # Schedules, transitional provisions and the introduction number their
        # provisions N.N with no sections in between.
        if kind in ("sch", "tp", "intro") or len(parts) < 2:
            section = chapter
        else:
            section = prefix + ".".join(parts[:2])
    return ProvisionId(text=text, book=book, kind=kind, chapter=chapter, section=section)


def cite(pid: str, ptype: str) -> str:
    """The citation form: ID and type letter with no space, e.g. ``DISP 1.6.2R``."""
    return f"{pid}{ptype}" if ptype else pid


# A reference inside running text, e.g. "DISP 2.8.2 R" or "COBS 4.7.1R" or
# "DISP 1 Annex 3R". The type letter is optional.
_REF_RE = re.compile(
    r"\b(?P<book>" + "|".join(sorted(MODULES, key=len, reverse=True)) + r")\s"
    r"(?:(?P<kind>App|Sch|TP|INTRO)\s)?"
    r"(?P<num>\d+[A-Z]{0,2}(?:\sAnnex\s\d+[A-Z]?|(?:\.\d+[A-Z]{0,2}){1,2}))"
    r"(?:\s?(?P<type>R|G|E|D)\b)?"
)


def find_references(text: str, known: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Provision IDs referred to in a piece of text, in order, without repeats.

    Chapter and section references (``DISP 1``, ``SYSC 4``) are not returned:
    only references that name a single provision or annex. A type letter
    written straight after the number is removed; ``known`` IDs settle the
    cases where a letter could belong to the ID instead (see ``strip_type``).

    >>> find_references("see DISP 2.8.2 R or DISP 2.8.7R and SYSC 4")
    ['DISP 2.8.2', 'DISP 2.8.7']
    """
    out: list[str] = []
    for m in _REF_RE.finditer(text):
        num = m.group("num")
        if "Annex" not in num and num.count(".") < 2:
            continue
        kind = f"{m.group('kind')} " if m.group("kind") else ""
        ref = strip_type(f"{m.group('book')} {kind}{num}", known)
        if ref not in out:
            out.append(ref)
    return out


def strip_type(ref: str, known: set[str] | frozenset[str] = frozenset()) -> str:
    """Remove a type letter written straight after an ID.

    With ``known`` IDs: 'DISP 1.6.2AR' becomes 'DISP 1.6.2A' if that ID exists.
    Without them, only a letter straight after a digit is removed, because
    'DISP 1.6.2AR' could be the ID 'DISP 1.6.2A' or a longer ID.

    >>> strip_type("DISP 2.8.7R")
    'DISP 2.8.7'
    >>> strip_type("DISP 1.6.2AR", known={"DISP 1.6.2A"})
    'DISP 1.6.2A'
    """
    if ref in known:
        return ref
    if known:
        base, ptype = split_citation(ref, known)
        if ptype and base in known:
            return base
    m = re.match(r"^(.*\d)(R|G|E|D)$", ref)
    return m.group(1) if m else ref


def split_citation(text: str, known: set[str] | frozenset[str] = frozenset()) -> tuple[str, str]:
    """Split a citation such as ``DISP 1.6.2AR`` into (ID, type letter).

    A trailing letter can be part of the ID (``DISP 1.6.2A``) or a type
    (``DISP 1.6.2 D``). When ``known`` IDs are given they settle it; otherwise
    a trailing R, G, E or D is taken as the type.

    >>> split_citation("DISP 1.6.2 R")
    ('DISP 1.6.2', 'R')
    >>> split_citation("DISP 1.6.2AR")
    ('DISP 1.6.2A', 'R')
    >>> split_citation("DISP 1.6.2D", known={"DISP 1.6.2D"})
    ('DISP 1.6.2D', '')
    """
    text = " ".join(text.split())
    if known and text in known:
        return text, ""
    m = re.match(r"^(.*?)\s?(R|G|E|D)$", text)
    if m and (not known or m.group(1) in known):
        return m.group(1), m.group(2)
    return text, ""
