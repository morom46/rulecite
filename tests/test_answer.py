"""Tests for quoting answers and refusing, with stand-in models (see fakes.py)."""

import json

import pytest
from fakes import FakeCrossEncoder, FakeEncoder

import rulecite.answer_eval as ae
from rulecite.answer import (Answer, Answerer, Draft, Quote, decide, extract, quote_around,
                             show, units)
from rulecite.records import Rule, save_rules
from rulecite.search import Searcher
from rulecite.testset import Question, save_questions

TEXTS = {
    "DISP 1.6.2": "The respondent must, by the end of eight weeks after its receipt of the "
                  "complaint, send the complainant:\n(1) a final response; or\n(2) a holding "
                  "response.",
    "DISP 1.9.1": "A firm must keep a record of each complaint and retain that record for:\n"
                  "(1) five years where the complaint relates to a UCITS scheme; and\n"
                  "(2) three years for all other complaints;\nfrom the date the complaint "
                  "was received.\n[Note: article 6(2) of the UCITS Directive]",
    "BCOBS 6.1.1": "A banking customer has a right to cancel a contract for a retail banking "
                   "service within 14 calendar days.",
    "BCOBS 6.4.1": "The firm must return any sums within 30 calendar days of cancellation.",
    "PRIN 2A.2.1": "A firm must act in good faith towards retail customers.",
}
RULES = [Rule(id=pid, type="R", book=pid.split()[0], kind="rule",
              chapter=pid.rsplit(".", 2)[0], section=pid.rsplit(".", 1)[0],
              section_title="Title", text=t) for pid, t in TEXTS.items()]
BY_ID = {r.id: r for r in RULES}


# ---- cutting a provision into pieces and choosing one

def test_units_skip_notes_and_keep_list_items():
    assert units(TEXTS["DISP 1.9.1"]) == [
        "A firm must keep a record of each complaint and retain that record for:",
        "(1) five years where the complaint relates to a UCITS scheme; and",
        "(2) three years for all other complaints;",
        "from the date the complaint was received."]


def test_units_join_very_short_pieces():
    assert units("A firm must act. Fast.") == ["A firm must act. Fast."]


def test_extract_quotes_the_whole_short_list():
    text, _ = extract(BY_ID["DISP 1.9.1"], "three years for other complaints", FakeCrossEncoder())
    assert text == ("A firm must keep a record of each complaint and retain that record for: "
                    "(1) five years where the complaint relates to a UCITS scheme; and "
                    "(2) three years for all other complaints; "
                    "from the date the complaint was received.")


def test_a_long_list_is_cut_to_the_lead_in_and_the_best_item():
    pieces = ["The response must:"] + [f"({i}) item {i} " + "word " * 30 for i in range(1, 7)]
    out = quote_around(pieces, 4)
    assert out == "The response must: … " + pieces[4]
    assert quote_around(pieces, 1) == "The response must: " + pieces[1]
    assert quote_around(pieces, 0) == "The response must:"


def test_extract_without_a_list():
    text, score = extract(BY_ID["BCOBS 6.1.1"], "cancel within days", FakeCrossEncoder())
    assert text == TEXTS["BCOBS 6.1.1"] and score > 0


# ---- refusing and quoting

def draft(*scores):
    return Draft("q?", [Quote(f"DISP 9.{i}", f"DISP 9.{i}R", s, f"piece {i}", f"whole {i}")
                        for i, s in enumerate(scores)])


def test_refuses_below_the_threshold():
    a = decide(draft(1.0, 0.5), threshold=2.0)
    assert a.refused and a.quotes == [] and a.top_score == 1.0


def test_quotes_only_what_clears_the_threshold():
    assert len(decide(draft(5.0, 1.0), threshold=2.0).quotes) == 1
    assert len(decide(draft(5.0, 3.0), threshold=2.0).quotes) == 2
    assert len(decide(draft(5.0, 3.0), threshold=2.0, max_quotes=1).quotes) == 1


def test_answer_text_cites_every_quote():
    a = decide(draft(5.0, 3.0), threshold=0)
    assert a.text() == "piece 0 [DISP 9.0R] piece 1 [DISP 9.1R]"
    assert a.text(whole=True) == "whole 0 [DISP 9.0R] whole 1 [DISP 9.1R]"


def test_show():
    rules = {f"DISP 9.{i}": Rule(id=f"DISP 9.{i}", type="R", book="DISP", kind="rule",
                                 chapter="DISP 9", section="DISP 9.9", text="x")
             for i in range(2)}
    assert "clearly answers" in show(decide(draft(-3.0), 0), rules)
    out = show(decide(draft(4.0, 2.0), 0), rules)
    assert out.startswith("Answer: DISP 9.0R") and "Also relevant: DISP 9.1R" in out


# ---- the whole pipeline with stand-in models

@pytest.fixture
def answerer(tmp_path):
    return Answerer(Searcher(RULES, FakeEncoder(), FakeCrossEncoder(), "fake", cache=tmp_path),
                    depth=5)


def test_drafts_hold_the_two_best_provisions(answerer):
    d = answerer.drafts(["How many calendar days to cancel a retail banking service?"])[0]
    assert [c.id for c in d.candidates][0] == "BCOBS 6.1.1"
    assert len(d.candidates) == 2 and d.candidates[0].score >= d.candidates[1].score
    assert "14 calendar days" in d.candidates[0].text


def test_answering_needs_the_cross_encoder(tmp_path):
    with pytest.raises(ValueError):
        Answerer(Searcher(RULES))


def test_answer(answerer):
    a = answerer.answer("good faith towards retail customers", threshold=1)
    assert isinstance(a, Answer) and not a.refused and a.quotes[0].id == "PRIN 2A.2.1"
    assert answerer.answer("payday loan interest cap", threshold=1).refused


# ---- scoring

def q(n, category, gold=(), facts=(), split="dev"):
    return Question(id=f"q{n:03d}", question="x?", category=category,
                    book=gold[0].split()[0] if gold else None, gold=list(gold),
                    key_facts=list(facts), split=split, note="" if gold else "elsewhere")


def test_outcomes():
    good = Draft("x?", [Quote("A 1.1", "A 1.1R", 5.0, "within eight weeks", "")])
    assert ae.outcome(q(1, "number", ["A 1.1"], ["eight weeks"]), good, 0) == "correct"
    assert ae.outcome(q(1, "number", ["A 1.1"], ["six weeks"]), good, 0) == "wrong"
    assert ae.outcome(q(1, "number", ["A 1.1"], ["eight weeks"]), good, 9) == "refused"
    assert ae.outcome(q(2, "unanswerable"), good, 9) == "refused"
    assert ae.outcome(q(2, "unanswerable"), good, 0) == "answered"


def test_tally_and_choose_threshold():
    qs = [q(1, "fact", ["A 1.1"], ["yes"]), q(2, "fact", ["A 1.1"], ["yes"]),
          q(3, "unanswerable"), q(4, "unanswerable")]
    drafts = [Draft("x?", [Quote("A 1.1", "A 1.1R", s, t, "")])
              for s, t in [(6.0, "yes"), (4.0, "yes"), (1.0, "no"), (-2.0, "no")]]
    t = ae.tally(qs, drafts, 2.5)
    assert t["accuracy"] == 1.0 and t["correct"] == 2 and t["right_refusals"] == 2
    assert ae.tally(qs, drafts, float("-inf"))["accuracy"] == 0.5
    threshold, extra = ae.choose_threshold(qs, drafts)
    # Every threshold between 1.0 and 4.0 is perfect; the candidates there are 2.5 only.
    assert threshold == 2.5 and extra["best_dev_accuracy"] == 1.0


@pytest.fixture
def files(tmp_path, monkeypatch):
    rules, qs = tmp_path / "rules.jsonl", tmp_path / "questions.jsonl"
    save_rules(RULES, rules)
    questions = [
        q(1, "number", ["DISP 1.6.2"], ["eight weeks"]),
        q(2, "number", ["BCOBS 6.1.1"], ["14 calendar days"]),
        q(3, "unanswerable"),
        q(4, "fact", ["PRIN 2A.2.1"], ["good faith"], split="test"),
        q(5, "unanswerable", split="test"),
    ]
    texts = ["weeks for a final response to a complaint", "calendar days to cancel",
             "payday loan cap", "act in good faith", "mortgage affordability"]
    for question, text in zip(questions, texts):
        question.question = text + "?"
    save_questions(questions, qs)
    monkeypatch.setattr(ae, "load_models", lambda *a: (FakeEncoder(), FakeCrossEncoder()))
    return ["--rules", str(rules), "--questions", str(qs), "--out", str(tmp_path / "results"),
            "--cache", str(tmp_path / "cache")]


def test_dev_then_test(files, tmp_path, capsys):
    out = tmp_path / "results"
    assert ae.main(["--split", "test", *files]) == 1
    assert ae.main(["--split", "dev", *files]) == 0
    choice = json.loads((out / "answers-choice.json").read_text())
    assert choice["chosen_on"] == "dev"
    assert ae.main(["--split", "test", *files]) == 0
    md = (out / "answers-test.md").read_text()
    assert "| accuracy (right / all) |" in md and "McNemar" in md and "(chosen)" in md
    data = json.loads((out / "answers-test.json").read_text())
    assert data["threshold"] == choice["threshold"]
    assert [r["id"] for r in data["questions"]] == ["q004", "q005"]
