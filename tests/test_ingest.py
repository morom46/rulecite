import json

import pytest

import io

from rulecite.ingest import compare_snapshot, ingest, parse_pdf
from rulecite.records import load_rules


@pytest.fixture(scope="module")
def parsed(sample_pdf):
    rules, report = parse_pdf(sample_pdf, "DISP")
    return {r.id: r for r in rules}, report


def test_every_provision_found_once(parsed):
    rules, report = parsed
    assert list(rules) == ["DISP 99.1.1", "DISP 99.1.2", "DISP 99.1.3", "DISP 99.1.4",
                           "DISP 99 Annex 1AB"]
    assert report.provisions == 5


def test_types_and_citation(parsed):
    rules, _ = parsed
    assert rules["DISP 99.1.1"].type == "R"
    assert rules["DISP 99.1.2"].type == "G"
    assert rules["DISP 99.1.1"].citation == "DISP 99.1.1R"


def test_type_printed_inside_annex_id(parsed):
    rules, _ = parsed
    annex = rules["DISP 99 Annex 1AB"]
    assert annex.type == "R"
    assert annex.kind == "annex"
    assert annex.section_title == "Example form"


def test_section_and_heading(parsed):
    rules, _ = parsed
    r1, r2 = rules["DISP 99.1.1"], rules["DISP 99.1.2"]
    assert r1.section == "DISP 99.1"
    assert r1.section_title == "Example section"
    assert r1.heading == ""
    assert r2.heading == "Speed of response"


def test_text_lines_and_list_items(parsed):
    rules, _ = parsed
    assert rules["DISP 99.1.1"].text == (
        "A firm must send a final response within eight weeks of receiving a "
        "complaint. The response must:\n"
        "(1) explain the decision; and\n"
        "(2) give the address of the Financial Ombudsman Service.")


def test_text_continues_across_pages(parsed):
    rules, _ = parsed
    assert rules["DISP 99.1.2"].text.endswith(
        "This sentence continues the guidance from the previous page.")


def test_header_footer_toc_and_intro_text_ignored(parsed):
    rules, report = parsed
    everything = " ".join(r.text for r in rules.values())
    assert "last updated" not in everything
    assert "Dispute Resolution" not in everything
    assert "Introductory text" not in everything
    assert report.orphan_lines == 1
    assert report.last_updated == "May 2026"


def test_table_rows_keep_their_cells_together(parsed):
    rules, _ = parsed
    assert rules["DISP 99.1.3"].text == (
        "The firm must follow these principles:\n"
        "1 Honesty | A firm must be honest.\n"
        "2 Care | A firm must take care.")


def test_deleted(parsed):
    rules, report = parsed
    assert rules["DISP 99.1.4"].deleted
    assert report.deleted == 1


def test_glossary_terms_joined_across_lines(parsed):
    rules, _ = parsed
    assert rules["DISP 99.1.1"].terms == ["final response", "complaint",
                                          "financial ombudsman service"]


def test_ingest_writes_rules_and_manifest(sample_pdf, tmp_path):
    reports = ingest(sample_pdf.parent, tmp_path, books=("DISP",))
    assert reports[0].provisions == 5
    rules = load_rules(tmp_path / "rules.jsonl")
    assert len(rules) == 4                      # the deleted one is not loaded
    assert len(load_rules(tmp_path / "rules.jsonl", include_deleted=True)) == 5
    refs = {r.id: r.refs for r in rules}
    # The references keep their book, lose the type letter, and skip the rule itself.
    assert refs["DISP 99.1.2"] == ["DISP 99.1.1", "COBS 4.7.1"]
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["DISP"]["provisions"] == 5
    assert len(manifest["DISP"]["sha256"]) == 64


def test_missing_pdf_explains_where_to_get_it(tmp_path):
    with pytest.raises(FileNotFoundError, match="data/README.md"):
        ingest(tmp_path, tmp_path / "out", books=("DISP",))


def test_snapshot_comparison(sample_pdf, tmp_path):
    reports = ingest(sample_pdf.parent, tmp_path, books=("DISP",))
    snap = tmp_path / "snapshot.json"
    snap.write_text(json.dumps({"books": {"DISP": {"sha256": reports[0].sha256}}}))
    assert compare_snapshot(reports, snap, file=io.StringIO())
    snap.write_text(json.dumps({"books": {"DISP": {"sha256": "0" * 64,
                                                   "last_updated": "January 2026"}}}))
    out = io.StringIO()
    assert not compare_snapshot(reports, snap, file=out)
    assert "differs from the snapshot" in out.getvalue()
