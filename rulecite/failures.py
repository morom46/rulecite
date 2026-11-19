"""Why answers go wrong: sort every failure on test into one kind, and list them.

Reads the saved results (no models are run):

    results/answers-{split}.json   what each question got: outcome and quotes
    results/search-{split}.json    where search ranked the gold provisions

and writes results/failures-{split}.md.

    python -m rulecite.failures            # test
    python -m rulecite.failures --split dev
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .records import load_rules
from .testset import QUESTIONS, RULES, Question, contains, load_questions

RESULTS = Path("results")

# Every failure gets exactly one of these, checked in this order.
KINDS = {
    "answered_unanswerable": "Answered a question these books do not cover",
    "refused_answerable": "Refused a question that has an answer",
    "not_found": "Right provision not in the top 20 of search",
    "ranked_low": "Right provision found by search (top 20), but not in the top two",
    "below_threshold": "Right provision second, but its score was below the threshold",
    "multi_missing": "Multi question: one of the needed provisions not quoted",
    "wrong_piece": "Right provision quoted, but the wrong piece of it",
}


def classify(q: Question, answer: dict, rank: int | None, threshold: float) -> str | None:
    """The kind of failure, or None if the question was right."""
    outcome = answer["outcome"]
    if outcome == "correct" or (q.category == "unanswerable" and outcome == "refused"):
        return None
    if q.category == "unanswerable":
        return "answered_unanswerable"
    if outcome == "refused":
        return "refused_answerable"
    candidates = [c["id"] for c in answer["quotes"]]
    quoted = [c["id"] for c in answer["quotes"] if c["score"] >= threshold]
    if q.category == "multi":
        if not all(g in quoted for g in q.gold):
            return "multi_missing"
        return "wrong_piece"
    if any(g in quoted for g in q.gold):
        return "wrong_piece"
    if any(g in candidates for g in q.gold):
        return "below_threshold"
    if rank is None or rank > 20:
        return "not_found"
    return "ranked_low"


def first_quote_wrong(q: Question, answer: dict, threshold: float) -> bool:
    """A correct answer whose first quote is not from a gold provision."""
    quoted = [c for c in answer["quotes"] if c["score"] >= threshold]
    return (answer["outcome"] == "correct" and q.category != "multi"
            and bool(quoted) and quoted[0]["id"] not in q.gold)


def whole_would_fix(q: Question, answer: dict, threshold: float, rules: dict) -> bool:
    quoted = [c["id"] for c in answer["quotes"] if c["score"] >= threshold]
    text = " ".join(rules[i].text for i in quoted if i in rules)
    return all(contains(text, f) for f in q.key_facts)


def analyse(questions: list[Question], answers: dict, search: dict, rules: dict) -> dict:
    threshold = answers["threshold"]
    method = search["methods"][-1]
    ranks = {s["id"]: s["methods"][method]["rank"] for s in search["questions"]}
    by_id = {a["id"]: a for a in answers["questions"]}
    rows = []
    for q in questions:
        a = by_id.get(q.id)
        if a is None:
            continue
        kind = classify(q, a, ranks.get(q.id), threshold)
        rows.append({"q": q, "answer": a, "rank": ranks.get(q.id), "kind": kind,
                     "first_wrong": first_quote_wrong(q, a, threshold),
                     "whole_fixes": kind == "wrong_piece"
                     and whole_would_fix(q, a, threshold, rules)})
    return {"threshold": threshold, "method": method, "rows": rows}


def short(text: str, n: int = 90) -> str:
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def markdown(split: str, report: dict) -> str:
    rows = report["rows"]
    failures = [r for r in rows if r["kind"]]
    counts = Counter(r["kind"] for r in failures)
    lines = [
        f"# Why answers go wrong: {split}",
        "",
        f"{len(failures)} of {len(rows)} {split} questions were not right at the refusal "
        f"threshold {report['threshold']:.2f}. Each is put in the first kind that fits, in "
        f"this order. Search ranks are from `{report['method']}`.",
        "",
        "| kind of failure | questions |",
        "|---|---|",
    ]
    for kind, label in KINDS.items():
        lines.append(f"| {label} | {counts.get(kind, 0)} |")
    fixes = sum(r["whole_fixes"] for r in failures)
    misordered = [r for r in rows if r["first_wrong"]]
    lines += ["",
              f"Of the {counts.get('wrong_piece', 0)} wrong-piece failures, {fixes} would be "
              "correct if the whole provision were quoted.",
              "",
              f"Also: {len(misordered)} answers counted as correct put another provision's quote "
              "first, so the right quote is second."]
    for kind, label in KINDS.items():
        group = [r for r in failures if r["kind"] == kind]
        if not group:
            continue
        lines += ["", f"## {label} ({len(group)})", "",
                  "| id | kind | question | gold | quoted (score) | search rank |",
                  "|---|---|---|---|---|---|"]
        for r in group:
            q, a = r["q"], r["answer"]
            quoted = ", ".join(f"{c['id']} ({c['score']:.1f})" for c in a["quotes"]
                               if c["score"] >= report["threshold"]) or \
                f"none (best {a['top_score']:.1f})"
            gold = ", ".join(q.gold) or "–"
            note = " ⚑" if q.note.startswith("Hard negative") else ""
            lines.append(f"| {q.id} | {q.category} | {short(q.question)}{note} | {gold} "
                         f"| {quoted} | {r['rank'] if r['rank'] else '–'} |")
    if counts.get("answered_unanswerable"):
        lines += ["", "⚑ marks a hard negative: a question written to share words with a real "
                  "provision that does not answer it."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", choices=("dev", "test"), default="test")
    ap.add_argument("--questions", type=Path, default=QUESTIONS)
    ap.add_argument("--rules", type=Path, default=RULES)
    ap.add_argument("--results", type=Path, default=RESULTS)
    args = ap.parse_args(argv)

    needed = [args.results / f"answers-{args.split}.json",
              args.results / f"search-{args.split}.json", args.rules]
    missing = [str(p) for p in needed if not p.exists()]
    if missing:
        print("Not found: " + ", ".join(missing))
        return 1
    answers = json.loads(needed[0].read_text())
    search = json.loads(needed[1].read_text())
    rules = {r.id: r for r in load_rules(args.rules)}
    questions = [q for q in load_questions(args.questions) if q.split == args.split]
    md = markdown(args.split, analyse(questions, answers, search, rules))
    out = args.results / f"failures-{args.split}.md"
    out.write_text(md)
    print(md)
    print(f"Written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
