"""Tests for sorting failures into kinds, on hand-made results (no models)."""

import json

from rulecite.failures import KINDS, analyse, classify, main, markdown
from rulecite.records import Rule, save_rules
from rulecite.testset import Question, save_questions

T = 0.0  # the threshold in these examples


def q(n, category, gold=(), facts=("x",)):
    return Question(id=f"q{n:03d}", question="Why?", category=category,
                    book=gold[0].split()[0] if gold else None, gold=list(gold),
                    key_facts=list(facts) if gold else [], split="test",
                    note="" if gold else "Hard negative: elsewhere")


def answer(outcome, *quotes):
    return {"id": "q", "outcome": outcome, "top_score": quotes[0][1] if quotes else -9,
            "quotes": [{"id": i, "score": s, "text": "t"} for i, s in quotes]}


def test_right_questions_are_not_failures():
    assert classify(q(1, "fact", ["A 1"]), answer("correct", ("A 1", 3)), 1, T) is None
    assert classify(q(2, "unanswerable"), answer("refused", ("A 1", -3)), None, T) is None


def test_each_kind():
    fact = q(1, "fact", ["A 1"])
    assert classify(q(2, "unanswerable"), answer("answered", ("A 1", 3)), None, T) \
        == "answered_unanswerable"
    assert classify(fact, answer("refused", ("B 1", -2)), 1, T) == "refused_answerable"
    assert classify(fact, answer("wrong", ("A 1", 2), ("B 1", 1)), 1, T) == "wrong_piece"
    assert classify(fact, answer("wrong", ("B 1", 2), ("A 1", -1)), 2, T) == "below_threshold"
    assert classify(fact, answer("wrong", ("B 1", 2), ("C 1", 1)), 7, T) == "ranked_low"
    assert classify(fact, answer("wrong", ("B 1", 2), ("C 1", 1)), 40, T) == "not_found"
    assert classify(fact, answer("wrong", ("B 1", 2), ("C 1", 1)), None, T) == "not_found"
    multi = q(3, "multi", ["A 1", "A 2"])
    assert classify(multi, answer("wrong", ("A 1", 2), ("B 1", 1)), 5, T) == "multi_missing"
    assert classify(multi, answer("wrong", ("A 1", 2), ("A 2", 1)), 2, T) == "wrong_piece"


RULES = {pid: Rule(id=pid, type="R", book="A", kind="rule", chapter="A", section="A",
                   text=text)
         for pid, text in [("A 1", "it is eight weeks"), ("B 1", "something else")]}


def test_analyse_counts_whole_provision_fixes_and_misordered_answers():
    questions = [q(1, "number", ["A 1"], ["eight weeks"]), q(2, "number", ["A 1"], ["weeks"])]
    answers = {"threshold": T, "questions": [
        {**answer("wrong", ("A 1", 3)), "id": "q001"},
        {**answer("correct", ("B 1", 3), ("A 1", 1)), "id": "q002"}]}
    search = {"methods": ["bm25", "rerank@50"], "questions": [
        {"id": "q001", "methods": {"rerank@50": {"rank": 1}}},
        {"id": "q002", "methods": {"rerank@50": {"rank": 2}}}]}
    report = analyse(questions, answers, search, RULES)
    first, second = report["rows"]
    assert first["kind"] == "wrong_piece" and first["whole_fixes"]
    assert second["kind"] is None and second["first_wrong"]
    md = markdown("test", report)
    assert "1 of 2 test questions" in md and "1 would be correct" in md
    assert all(label in md for label in KINDS.values())


def test_main(tmp_path, capsys):
    results = tmp_path / "results"
    results.mkdir()
    save_rules(list(RULES.values()), tmp_path / "rules.jsonl")
    save_questions([q(1, "number", ["A 1"], ["eight weeks"]), q(2, "unanswerable")],
                   tmp_path / "qs.jsonl")
    (results / "answers-test.json").write_text(json.dumps({"threshold": T, "questions": [
        {**answer("correct", ("A 1", 3)), "id": "q001"},
        {**answer("answered", ("B 1", 1)), "id": "q002"}]}))
    (results / "search-test.json").write_text(json.dumps({"methods": ["rerank@50"], "questions": [
        {"id": "q001", "methods": {"rerank@50": {"rank": 1}}},
        {"id": "q002", "methods": {"rerank@50": {"rank": None}}}]}))
    args = ["--results", str(results), "--rules", str(tmp_path / "rules.jsonl"),
            "--questions", str(tmp_path / "qs.jsonl")]
    assert main(args) == 0
    md = (results / "failures-test.md").read_text()
    assert "q002" in md and "⚑" in md
    assert main(["--split", "dev", *args]) == 1
