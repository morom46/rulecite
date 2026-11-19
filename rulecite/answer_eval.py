"""Score the answers: right, wrong, or refused, and whether refusing was right.

    python -m rulecite.answer_eval --split dev    # choose the refusal threshold
    python -m rulecite.answer_eval --split test   # the reported numbers, with that threshold

Each question ends in one of five outcomes:

    answerable question    correct    answered, and the answer contains every key fact
                           wrong      answered, but a key fact is missing
                           refused    no answer given (safe, but unhelpful)
    unanswerable question  refused    the right outcome
                           answered   a quote that cannot be the answer

Accuracy is the share of all questions that are correct or rightly refused.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

from .answer import CHOICE, MAX_QUOTES, Answerer, Draft, decide, saved_depth
from .metrics import bootstrap_ci, mcnemar
from .records import load_rules
from .search import CACHE, DENSE_MODEL, RERANKER, Searcher, load_models
from .testset import QUESTIONS, RULES, Question, contains, load_questions

RESULTS = Path("results")
KINDS = ("fact", "number", "scope", "multi")
SWEEP = (-6.0, -4.0, -2.0, 0.0, 2.0, 4.0, 6.0)   # thresholds shown in the trade-off table


def outcome(q: Question, draft: Draft, threshold: float, whole: bool = False) -> str:
    answer = decide(draft, threshold)
    if q.category == "unanswerable":
        return "refused" if answer.refused else "answered"
    if answer.refused:
        return "refused"
    text = answer.text(whole=whole)
    return "correct" if all(contains(text, f) for f in q.key_facts) else "wrong"


def is_right(q: Question, result: str) -> bool:
    return result == "correct" or (q.category == "unanswerable" and result == "refused")


def tally(questions: list[Question], drafts: list[Draft], threshold: float,
          whole: bool = False) -> dict:
    """Counts of each outcome, accuracy, and how much was answered."""
    results = [outcome(q, d, threshold, whole) for q, d in zip(questions, drafts)]
    ans = [r for q, r in zip(questions, results) if q.category != "unanswerable"]
    una = [r for q, r in zip(questions, results) if q.category == "unanswerable"]
    right = [is_right(q, r) for q, r in zip(questions, results)]
    answered = [r in ("correct", "wrong", "answered") for r in results]
    good = sum(r == "correct" for r in ans)
    n_answered = sum(answered)
    words = [len(decide(d, threshold).text(whole).split()) for d in drafts
             if not decide(d, threshold).refused]
    return {
        "threshold": threshold,
        "accuracy": sum(right) / len(questions),
        "correct": good, "wrong": ans.count("wrong"), "false_refusals": ans.count("refused"),
        "right_refusals": una.count("refused"), "unanswerable_answered": una.count("answered"),
        "answerable": len(ans), "unanswerable": len(una),
        "answered_share": n_answered / len(questions),
        "precision": good / n_answered if n_answered else 0.0,  # correct among answered
        "median_words": float(np.median(words)) if words else 0.0,
        "right": [int(x) for x in right],
    }


def choose_threshold(questions: list[Question], drafts: list[Draft]) -> tuple[float, dict]:
    """The threshold with the best dev accuracy, from the middle of the best range.

    Accuracy only changes when the threshold passes one of the top scores, so
    the candidates are the points halfway between neighbouring scores (and one
    below the lowest). If a range of them ties, the middle one is taken, so the
    threshold is not pressed against any single dev question.
    """
    scores = sorted({round(d.top_score, 4) for d in drafts if math.isfinite(d.top_score)})
    candidates = [scores[0] - 1.0] + [(a + b) / 2 for a, b in zip(scores, scores[1:])] \
        + [scores[-1] + 1.0]
    acc = [tally(questions, drafts, t)["accuracy"] for t in candidates]
    best = max(acc)
    tied = [t for t, a in zip(candidates, acc) if a == best]
    threshold = round(float(np.median(tied)), 3)
    return threshold, {"best_dev_accuracy": best, "tied_range": [tied[0], tied[-1]]}


def by_kind(questions: list[Question], drafts: list[Draft], threshold: float) -> dict:
    out = {}
    for kind in (*KINDS, "unanswerable"):
        pairs = [(q, d) for q, d in zip(questions, drafts) if q.category == kind]
        if pairs:
            out[kind] = sum(is_right(q, outcome(q, d, threshold)) for q, d in pairs) / len(pairs)
    return out


def pct(x: float) -> str:
    return f"{100 * x:.0f}"


def markdown(split: str, questions: list[Question], drafts: list[Draft], threshold: float,
             seconds: float, models: dict, extra: dict) -> str:
    main = tally(questions, drafts, threshold)
    never = tally(questions, drafts, float("-inf"))
    whole = tally(questions, drafts, threshold, whole=True)
    lo, hi = bootstrap_ci(main["right"])
    lines = [
        f"# Answer results: {split}",
        "",
        f"{len(questions)} {split} questions ({main['answerable']} answerable, "
        f"{main['unanswerable']} unanswerable). Made by "
        f"`python -m rulecite.answer_eval --split {split}` on {date.today():%d %B %Y} with "
        f"`{models['dense']}` and `{models['reranker']}`, on the CPU, in {seconds:.0f} s. "
        f"Refusal threshold {threshold:.2f}"
        + (" (chosen on these questions)." if split == "dev" else " (chosen on dev)."),
        "",
        "An answer is **correct** when it contains every key fact of the question. A question "
        "is **right** when its answer is correct, or when it is unanswerable and the system "
        "refused.",
        "",
        "| | quoted pieces (the system) | no refusing | whole provisions |",
        "|---|---|---|---|",
    ]
    rows = [("accuracy (right / all)", "accuracy", pct),
            ("correct answers", "correct", str), ("wrong answers", "wrong", str),
            ("answerable but refused", "false_refusals", str),
            ("unanswerable, rightly refused", "right_refusals", str),
            ("unanswerable but answered", "unanswerable_answered", str),
            ("correct among answered (%)", "precision", pct),
            ("median words in an answer", "median_words", lambda x: f"{x:.0f}")]
    for label, key, fmt in rows:
        lines.append(f"| {label} | {fmt(main[key])} | {fmt(never[key])} | {fmt(whole[key])} |")
    lines += ["",
              "*No refusing* answers every question with the same quotes. *Whole provisions* "
              "quotes each provision in full instead of its best piece: an upper limit on what "
              "picking the piece can reach, at the cost of much longer answers.",
              "",
              f"95% bootstrap interval for accuracy: {pct(lo)} to {pct(hi)}."]
    if split == "test":
        a, b, p = mcnemar(main["right"], never["right"])
        lines += [f"Refusing against never refusing: right only with refusing {a}, right only "
                  f"without {b} (exact McNemar p = {p:.3f})."]
    kinds = by_kind(questions, drafts, threshold)
    lines += ["", "Right by kind of question (%):", "",
              "| " + " | ".join(f"{k} ({sum(q.category == k for q in questions)})"
                                for k in kinds) + " |",
              "|" + "---|" * len(kinds),
              "| " + " | ".join(pct(v) for v in kinds.values()) + " |",
              "", "## The trade-off", "",
              "A higher threshold refuses more: fewer wrong answers and fewer unanswerable "
              "questions answered, but more answerable questions refused.", "",
              "| threshold | answered | accuracy | correct | wrong | answerable refused "
              "| unanswerable answered |",
              "|---|---|---|---|---|---|---|"]
    for t in sorted({*SWEEP, threshold}):
        r = tally(questions, drafts, t)
        mark = " **(chosen)**" if t == threshold else ""
        lines.append(f"| {t:.2f}{mark} | {pct(r['answered_share'])}% | {pct(r['accuracy'])} "
                     f"| {r['correct']} | {r['wrong']} | {r['false_refusals']} "
                     f"| {r['unanswerable_answered']} |")
    if split == "dev" and extra:
        lines += ["", f"The best dev accuracy, {pct(extra['best_dev_accuracy'])}%, holds for "
                  f"thresholds from {extra['tied_range'][0]:.2f} to {extra['tied_range'][1]:.2f}; "
                  f"the middle, {threshold:.2f}, is saved to `results/answers-choice.json`."]
    return "\n".join(lines) + "\n"


def write_json(path: Path, questions: list[Question], drafts: list[Draft], threshold: float,
               head: dict) -> None:
    rows = []
    for q, d in zip(questions, drafts):
        rows.append({"id": q.id, "category": q.category, "gold": q.gold,
                     "outcome": outcome(q, d, threshold), "top_score": d.top_score,
                     "quotes": [{"id": c.id, "score": c.score, "text": c.text}
                                for c in d.candidates]})
    lines = ["{"] + [f" {json.dumps(k)}: {json.dumps(v)}," for k, v in head.items()]
    lines += [' "questions": ['] + [
        f"  {json.dumps(r, ensure_ascii=False)}{',' if i < len(rows) - 1 else ''}"
        for i, r in enumerate(rows)] + [" ]", "}"]
    path.write_text("\n".join(lines) + "\n")


def demo_examples(results: Path = RESULTS, questions: Path = QUESTIONS,
                  n: int = 4) -> tuple[list[str], list[str], float | None]:
    """Questions for the demo page: some it answered right, one it rightly refused.

    Taken from the saved results, so the examples show what the system really
    does: n answerable questions whose first quote is from a gold provision (one
    per book first), then one unanswerable question it refused. Also returns
    the test accuracy, which the page shows beside them. Returns (answered,
    refused, accuracy).
    """
    by_id = {q.id: q for q in load_questions(questions)} if questions.exists() else {}
    good, refused, accuracy = [], [], None
    for split in ("test", "dev"):
        path = results / f"answers-{split}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        if split == "test":
            accuracy = data["summary"]["accuracy"]
        for a in data["questions"]:
            q = by_id.get(a["id"])
            if q is None:
                continue
            if a["outcome"] == "correct" and a["quotes"] and a["quotes"][0]["id"] in q.gold:
                good.append(q)
            elif q.category == "unanswerable" and a["outcome"] == "refused":
                refused.append(q)
    picked: list[Question] = []
    for book in ("DISP", "BCOBS", "PRIN"):
        picked += [q for q in good if q.book == book][:1]
    picked += [q for q in good if q not in picked][:max(0, n - len(picked))]
    return [q.question for q in picked[:n]], [q.question for q in refused[:1]], accuracy


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", choices=("dev", "test"), required=True)
    ap.add_argument("--questions", type=Path, default=QUESTIONS)
    ap.add_argument("--rules", type=Path, default=RULES)
    ap.add_argument("--out", type=Path, default=RESULTS)
    ap.add_argument("--dense-model", default=DENSE_MODEL)
    ap.add_argument("--reranker", default=RERANKER)
    ap.add_argument("--cache", type=Path, default=CACHE)
    args = ap.parse_args(argv)

    if not args.rules.exists():
        print(f"{args.rules} not found: run make ingest first.")
        return 1
    choice_file = args.out / CHOICE.name
    if args.split == "test" and not choice_file.exists():
        print(f"{choice_file} not found: run the dev split first, which chooses the threshold.")
        return 1
    questions = [q for q in load_questions(args.questions) if q.split == args.split]
    rules = load_rules(args.rules)
    depth = saved_depth(args.out / "search-choice.json")

    print("Loading the models ...")
    encoder, cross = load_models(args.dense_model, args.reranker)
    answerer = Answerer(Searcher(rules, encoder, cross, args.dense_model, cache=args.cache),
                        depth=depth)
    print(f"Answering {len(questions)} {args.split} questions (re-ranking the top {depth}) ...")
    start = time.perf_counter()
    drafts = answerer.drafts([q.question for q in questions])
    seconds = time.perf_counter() - start
    models = {"dense": args.dense_model, "reranker": args.reranker}

    extra = {}
    if args.split == "dev":
        threshold, extra = choose_threshold(questions, drafts)
        args.out.mkdir(parents=True, exist_ok=True)
        choice_file.write_text(json.dumps({"threshold": threshold, "chosen_on": "dev",
                                           "max_quotes": MAX_QUOTES, **extra}, indent=2) + "\n")
    else:
        threshold = float(json.loads(choice_file.read_text())["threshold"])

    args.out.mkdir(parents=True, exist_ok=True)
    md = markdown(args.split, questions, drafts, threshold, seconds, models, extra)
    (args.out / f"answers-{args.split}.md").write_text(md)
    summary = {k: v for k, v in tally(questions, drafts, threshold).items() if k != "right"}
    write_json(args.out / f"answers-{args.split}.json", questions, drafts, threshold,
               {"threshold": threshold, "models": models, "summary": summary})
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
