"""Checks on the real sourcebooks. Skipped unless `make ingest` has been run.

These check facts that are stable across Handbook updates (a time limit, the
number of Principles), not exact counts, which change whenever the FCA edits
a sourcebook.
"""

import json
from pathlib import Path

import pytest

from rulecite.ids import BOOKS
from rulecite.records import load_rules

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
pytestmark = pytest.mark.skipif(not (PROCESSED / "rules.jsonl").exists(),
                                reason="real data not ingested (see data/README.md)")


@pytest.fixture(scope="module")
def rules():
    return {r.id: r for r in load_rules(PROCESSED / "rules.jsonl")}


def test_all_three_books(rules):
    assert {r.book for r in rules.values()} == set(BOOKS)


def test_every_provision_has_text(rules):
    assert [pid for pid, r in rules.items() if not r.text] == []


def test_ids_unique():
    lines = (PROCESSED / "rules.jsonl").read_text().splitlines()
    ids = [json.loads(line)["id"] for line in lines]
    assert len(ids) == len(set(ids))


def test_no_page_furniture(rules):
    for r in rules.values():
        assert "handbook.fca.org.uk" not in r.text
        assert "last updated in" not in r.text
        assert not r.text.startswith("Section :")


def test_known_facts(rules):
    assert "eight weeks" in rules["DISP 1.6.2"].text
    assert rules["DISP 1.6.2"].type == "R"
    assert "15 business days" in rules["DISP 1.6.2A"].text
    assert "fair, clear and not misleading" in rules["BCOBS 2.2.1"].text
    assert "good faith" in rules["PRIN 2A.2.1"].text


def test_principles_table(rules):
    rows = [line for line in rules["PRIN 2.1.1"].text.split("\n") if " | " in line]
    assert len(rows) == 12
    assert rows[0].startswith("1 Integrity | ")
    assert rows[11].startswith("12 Consumer Duty | ")


def test_references_resolve(rules):
    inside = [x for r in rules.values() for x in r.refs if x.split()[0] in BOOKS]
    resolved = sum(x in rules for x in inside)
    # The rest point to deleted provisions or to annexes printed under other IDs.
    assert resolved / len(inside) > 0.95
