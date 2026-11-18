"""Tests for the hand-review tool, driven by scripted answers instead of a keyboard."""

from rulecite.records import Rule
from rulecite.review import Style, WordIndex, mark_facts, review
from rulecite.testset import Question

RULES = {
    "DISP 1.6.2": Rule(id="DISP 1.6.2", type="R", book="DISP", kind="rule", chapter="DISP 1",
                       section="DISP 1.6", text="Reply by the end of eight weeks after receipt."),
    "BCOBS 6.1.1": Rule(id="BCOBS 6.1.1", type="R", book="BCOBS", kind="rule",
                        chapter="BCOBS 6", section="BCOBS 6.1",
                        text="A customer may cancel a savings contract within 14 calendar days."),
}


def questions():
    return [
        Question(id=f"q00{i}", question=f"Question {i}?", category="number", book="DISP",
                 gold=["DISP 1.6.2"], key_facts=["eight weeks"], split="dev")
        for i in (1, 2, 3)
    ]


def run(qs, answers, **kw):
    """Review qs answering from the list; return what was printed and how often it saved."""
    answers = iter(answers)
    printed, saves = [], []
    review(qs, RULES, save=lambda: saves.append(1), ask=lambda _: next(answers),
           say=printed.append, **kw)
    return "\n".join(printed), len(saves)


def test_correct_and_flag_are_saved_each_time():
    qs = questions()
    _, saves = run(qs, ["c", "f", "gold should be DISP 1.6.2A", "c"])
    assert [x.status for x in qs] == ["checked", "flagged", "checked"]
    assert qs[1].note == "gold should be DISP 1.6.2A"
    assert saves == 3


def test_flag_without_a_note_changes_nothing():
    qs = questions()
    run(qs, ["f", "", "q"])
    assert qs[0].status == "draft"


def test_edit_rewords_then_asks_again():
    qs = questions()
    run(qs, ["e", "How long is the deadline", "c", "q"])
    assert qs[0].question == "How long is the deadline?"
    assert qs[0].status == "checked"


def test_quit_keeps_earlier_answers_and_resume_starts_at_first_draft():
    qs = questions()
    run(qs, ["c", "q"])
    out, _ = run(qs, ["q"])
    first_screen = out.split("[c] correct")[0]
    assert "q002" in first_screen and "q001" not in first_screen


def test_skip_and_back():
    qs = questions()
    run(qs, ["s", "b", "c", "q"])
    assert [x.status for x in qs] == ["checked", "draft", "draft"]


def test_start_from_an_id_includes_checked_questions():
    qs = questions()
    for x in qs:
        x.status = "checked"
    run(qs, ["f", "wrong book", "q"], start="q002")
    assert [x.status for x in qs] == ["checked", "flagged", "checked"]


def test_only_flagged():
    qs = questions()
    qs[2].status, qs[2].note = "flagged", "check this"
    out, _ = run(qs, ["c"], flagged=True)
    assert qs[2].status == "checked" and "q001" not in out


def test_nothing_to_do():
    qs = questions()
    for x in qs:
        x.status = "checked"
    out, saves = run(qs, [])
    assert "Nothing to review" in out and saves == 0


def test_key_facts_are_marked_in_the_rule_text():
    out, _ = run(questions(), ["q"])
    assert "[[eight weeks]]" in out


def test_mark_facts_handles_curly_quotes():
    text = "the firm’s final response"
    assert mark_facts(text, ["firm's final"], Style(False)) == "the [[firm’s final]] response"


def test_unanswerable_shows_nearest_rules():
    qs = [Question(id="q001", question="Can I cancel a savings contract?",
                   category="unanswerable", book=None, split="test", note="test")]
    out, _ = run(qs, ["c"])
    assert "BCOBS 6.1.1" in out


def test_nearest_prefers_rare_shared_words():
    assert WordIndex(RULES).nearest("savings cancel", k=1)[0].id == "BCOBS 6.1.1"
