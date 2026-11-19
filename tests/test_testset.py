"""Tests for the test set file and the checks on it. None of these need the real PDFs."""

from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from rulecite.records import Rule
from rulecite.testset import (CATEGORIES, DEV_SIZE, Question, assign_splits, check_against_rules,
                              check_structure, contains, load_questions, save_questions)

SHIPPED = Path(__file__).resolve().parents[1] / "testset" / "questions.jsonl"


def q(**kw) -> Question:
    base = dict(id="q001", question="How long does a firm have?", category="number",
                book="DISP", gold=["DISP 1.6.2"], key_facts=["eight weeks"], split="dev")
    return Question(**{**base, **kw})


def rule(pid: str, text: str) -> Rule:
    book = pid.split()[0]
    return Rule(id=pid, type="R", book=book, kind="rule", chapter=pid.rsplit(".", 2)[0],
                section=pid.rsplit(".", 1)[0], text=text)


RULES = {r.id: r for r in [
    rule("DISP 1.6.2", "The respondent must, by the end of eight weeks after receipt, reply."),
    rule("DISP 2.8.2", "The Ombudsman cannot consider it more than six months after the final response."),
    rule("BCOBS 6.1.1", "A banking customer may cancel within 14 calendar days."),
]}


# ---- the file as shipped

def test_shipped_file_has_no_structural_problems():
    assert check_structure(load_questions(SHIPPED)) == []


def test_shipped_file_size_and_split():
    questions = load_questions(SHIPPED)
    assert len(questions) == 150
    assert Counter(x.split for x in questions) == {"dev": DEV_SIZE, "test": 150 - DEV_SIZE}


def test_shipped_file_covers_every_category():
    found = Counter(x.category for x in load_questions(SHIPPED))
    assert set(found) == set(CATEGORIES)
    assert min(found.values()) >= 15


def test_shipped_split_is_the_one_assign_splits_makes():
    questions = load_questions(SHIPPED)
    before = [x.split for x in questions]
    assign_splits(questions)
    assert [x.split for x in questions] == before


# ---- reading and writing

def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "qs.jsonl"
    questions = [q(), q(id="q002", category="unanswerable", book=None, gold=[], key_facts=[],
                       note="ICOBS")]
    save_questions(questions, path)
    assert load_questions(path) == questions
    assert not path.with_suffix(".tmp").exists()


def test_contains_ignores_case_quotes_and_spacing():
    assert contains("the firm’s  final\nresponse", "Firm's final response")
    assert not contains("eight weeks", "eight days")


# ---- structure checks

def test_a_good_question_passes():
    assert check_structure([q()]) == []


@pytest.mark.parametrize("change, expected", [
    (dict(id="Q1"), "id should look like q001"),
    (dict(question="How long"), "question mark"),
    (dict(category="lookup"), "unknown category"),
    (dict(split="train"), "split should be dev or test"),
    (dict(status="done"), "unknown status"),
    (dict(status="flagged"), "needs a note"),
    (dict(book="COBS"), "book should be one of"),
    (dict(gold=[]), "at least one gold"),
    (dict(key_facts=[]), "at least one key fact"),
    (dict(key_facts=["one two three four five six seven eight nine ten eleven"]), "too long"),
    (dict(gold=["DISP 1.6.2", "DISP 1.6.2"]), "listed twice"),
    (dict(category="multi"), "two or more gold"),
    (dict(category="unanswerable", note="MCOB"), "no gold, key facts or book"),
    (dict(category="unanswerable", book=None, gold=[], key_facts=[]), "say in the note"),
])
def test_structure_problems_are_caught(change, expected):
    problems = check_structure([q(**change)])
    assert any(expected in p for p in problems), problems


def test_duplicate_ids_are_caught():
    assert any("used twice" in p for p in check_structure([q(), q()]))


# ---- checks against the rule text

def test_gold_and_facts_found():
    assert check_against_rules([q()], RULES) == []


def test_missing_gold_id():
    problems = check_against_rules([q(gold=["DISP 9.9.9"])], RULES)
    assert problems == ["q001: gold DISP 9.9.9 is not in the rules"]


def test_fact_not_in_gold():
    problems = check_against_rules([q(key_facts=["six weeks"])], RULES)
    assert problems == ["q001: key fact 'six weeks' is not in DISP 1.6.2"]


def test_gold_from_another_book():
    problems = check_against_rules([q(gold=["BCOBS 6.1.1"], key_facts=["14 calendar days"])], RULES)
    assert problems == ["q001: gold BCOBS 6.1.1 is in BCOBS, not DISP"]


def test_multi_needs_each_gold_to_hold_a_fact():
    good = q(category="multi", gold=["DISP 1.6.2", "DISP 2.8.2"],
             key_facts=["eight weeks", "six months"])
    assert check_against_rules([good], RULES) == []
    idle = replace(good, key_facts=["eight weeks"])
    assert check_against_rules([idle], RULES) == ["q001: gold DISP 2.8.2 holds none of the key facts"]


def test_unanswerable_is_not_checked_against_rules():
    none = q(category="unanswerable", book=None, gold=[], key_facts=[], note="MCOB 11")
    assert check_against_rules([none], RULES) == []


# ---- the split

def make_set(n_per_group: dict[tuple[str, str], int]) -> list[Question]:
    out = []
    for (book, cat), n in n_per_group.items():
        for _ in range(n):
            out.append(q(id=f"q{len(out) + 1:03d}", book=book, category=cat))
    return out


def test_split_has_exact_dev_size_and_is_repeatable():
    questions = make_set({("DISP", "fact"): 31, ("DISP", "number"): 17,
                          ("BCOBS", "fact"): 29, ("PRIN", "scope"): 13})
    assign_splits(questions, dev_size=30, seed=1)
    first = [x.split for x in questions]
    assert first.count("dev") == 30
    assign_splits(questions, dev_size=30, seed=1)
    assert [x.split for x in questions] == first


def test_split_keeps_each_group_in_proportion():
    questions = make_set({("DISP", "fact"): 60, ("BCOBS", "number"): 30, ("PRIN", "multi"): 9})
    assign_splits(questions, dev_size=33)
    dev = Counter((x.book, x.category) for x in questions if x.split == "dev")
    assert dev == {("DISP", "fact"): 20, ("BCOBS", "number"): 10, ("PRIN", "multi"): 3}


def test_different_seed_gives_a_different_split():
    questions = make_set({("DISP", "fact"): 40})
    assign_splits(questions, dev_size=10, seed=1)
    first = [x.split for x in questions]
    assign_splits(questions, dev_size=10, seed=2)
    assert [x.split for x in questions] != first
