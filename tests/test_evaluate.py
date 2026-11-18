"""Tests for the evaluation run, with stand-in models (see fakes.py)."""

import json

import pytest
from fakes import FakeCrossEncoder, FakeEncoder

import rulecite.evaluate as ev
from rulecite.records import Rule, save_rules
from rulecite.search import Searcher
from rulecite.testset import Question, save_questions

TEXTS = {
    "DISP 1.6.2": "The respondent must send a final response within eight weeks.",
    "DISP 2.8.2": "The Ombudsman cannot consider a complaint referred more than six months later.",
    "BCOBS 6.1.1": "A banking customer may cancel within 14 calendar days.",
    "BCOBS 6.4.1": "The firm must return any sums within 30 calendar days after cancelling.",
    "PRIN 2A.2.1": "A firm must act in good faith towards retail customers.",
}
RULES = [Rule(id=pid, type="R", book=pid.split()[0], kind="rule",
              chapter=pid.rsplit(".", 2)[0], section=pid.rsplit(".", 1)[0], text=t)
         for pid, t in TEXTS.items()]


def question(n, text, category, gold, split="dev"):
    book = gold[0].split()[0] if gold else None
    return Question(id=f"q{n:03d}", question=text, category=category, book=book, gold=gold,
                    key_facts=["x"] if gold else [], split=split, status="checked",
                    note="" if gold else "elsewhere")


QUESTIONS = [
    question(1, "How many weeks for a final response?", "number", ["DISP 1.6.2"]),
    question(2, "How long can a customer cancel, and when is money returned?", "multi",
             ["BCOBS 6.1.1", "BCOBS 6.4.1"]),
    question(3, "Must a firm act in good faith?", "fact", ["PRIN 2A.2.1"]),
    question(4, "What is the payday loan cap?", "unanswerable", []),
    question(5, "Time limit to go to the Ombudsman after six months?", "number", ["DISP 2.8.2"],
             split="test"),
    question(6, "Cancel within how many calendar days?", "number", ["BCOBS 6.1.1"], split="test"),
    question(7, "What is the mortgage affordability rule?", "unanswerable", [], split="test"),
]


@pytest.fixture
def searcher(tmp_path):
    return Searcher(RULES, FakeEncoder(), FakeCrossEncoder(), "fake", cache=tmp_path)


def test_score_and_summary(searcher):
    dev = [q for q in QUESTIONS if q.split == "dev"]
    report = ev.score(dev, searcher, ["bm25", "hybrid", "rerank@3"], depth=3)
    assert [q["id"] for q in report["questions"]] == ["q001", "q002", "q003", "q004"]
    q4 = report["questions"][3]["methods"]["bm25"]
    assert q4["rank"] is None and len(q4["top10"]) == 5
    table = ev.summary(report)
    assert table["bm25"]["R@1"] == pytest.approx(2 / 3, abs=1e-4)  # unanswerable q004 is left out
    assert table["bm25"]["scope"] is None                # no scope questions here
    assert table["bm25"]["multi"] == 1.0


def test_choose_depth_prefers_recall_then_mrr_then_smaller():
    row = lambda r, m: {"R@5": r, "MRR@10": m}  # noqa: E731
    assert ev.choose_depth({"rerank@10": row(.8, .5), "rerank@20": row(.9, .4),
                            "rerank@50": row(.9, .4)}) == 20
    assert ev.choose_depth({"rerank@10": row(.9, .6), "rerank@20": row(.9, .7),
                            "rerank@50": row(.8, .9)}) == 20
    assert ev.choose_depth({d: row(.9, .6) for d in ("rerank@10", "rerank@20", "rerank@50")}) == 10


def test_significance_names_the_chosen_reranker(searcher):
    report = ev.score(QUESTIONS, searcher, ["bm25", "dense", "hybrid", "rerank@4"], depth=4)
    sig = ev.significance(report, 4)
    assert [(t["a"], t["b"]) for t in sig["tests"]] == [
        ("hybrid", "bm25"), ("hybrid", "dense"), ("rerank@4", "hybrid"), ("rerank@4", "bm25")]
    assert set(sig["intervals"]) == {"bm25", "dense", "hybrid", "rerank@4"}


@pytest.fixture
def files(tmp_path, monkeypatch):
    rules, qs = tmp_path / "rules.jsonl", tmp_path / "questions.jsonl"
    save_rules(RULES, rules)
    save_questions(QUESTIONS, qs)
    monkeypatch.setattr(ev, "load_models", lambda *a: (FakeEncoder(), FakeCrossEncoder()))
    return ["--rules", str(rules), "--questions", str(qs), "--out", str(tmp_path / "results"),
            "--cache", str(tmp_path / "cache")]


def test_test_split_needs_the_choice_made_on_dev(files, tmp_path, capsys):
    assert ev.main(["--split", "test", *files]) == 1
    assert "run the dev split first" in capsys.readouterr().out


def test_dev_then_test(files, tmp_path):
    out = tmp_path / "results"
    assert ev.main(["--split", "dev", *files]) == 0
    assert len(list((tmp_path / "cache").glob("dense-*.npy"))) == 1
    choice = json.loads((out / "search-choice.json").read_text())
    assert choice["rerank_depth"] in ev.DEPTHS and choice["chosen_on"] == "dev"
    dev = json.loads((out / "search-dev.json").read_text())
    assert dev["methods"] == ["bm25", "dense", "hybrid", "rerank@10", "rerank@20", "rerank@50"]

    assert ev.main(["--split", "test", *files]) == 0
    test = json.loads((out / "search-test.json").read_text())
    assert test["methods"][-1] == f"rerank@{choice['rerank_depth']}"
    assert {q["id"] for q in test["questions"]} == {"q005", "q006", "q007"}
    md = (out / "search-test.md").read_text()
    assert "| bm25 |" in md and "McNemar" in md and "95% interval" in md


def test_bm25_only_writes_nothing(files, tmp_path, capsys):
    assert ev.main(["--split", "dev", "--bm25-only", *files]) == 0
    assert "bm25" in capsys.readouterr().out
    assert not (tmp_path / "results").exists()
