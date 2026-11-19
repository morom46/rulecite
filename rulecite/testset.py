"""The test set: questions with the provisions that answer them, and the checks on it.

Each question names its gold provisions (the ones that answer it) and a few
key facts: short phrases that a correct answer has to contain, copied from the
gold text. The checks here make sure every gold ID exists, every key fact
really is in the gold text, and the dev/test split is the one we expect.

Run `python -m rulecite.testset` to check the file and print its counts.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .ids import BOOKS
from .records import Rule, load_rules

QUESTIONS = Path("testset/questions.jsonl")
RULES = Path("data/processed/rules.jsonl")

# What kind of question it is. Each one tests a different way an answer can go wrong.
CATEGORIES = {
    "fact": "what a rule requires, answered by one provision",
    "number": "a time limit, amount or count, answered by one provision",
    "scope": "whether a rule applies, or an exception, answered by one provision",
    "multi": "needs two or more provisions together",
    "unanswerable": "about something these three books do not cover",
}
SPLITS = ("dev", "test")
STATUSES = ("draft", "checked", "flagged")
DEV_SIZE = 50
SEED = 2026
MAX_FACT_WORDS = 10  # key facts are short phrases, never whole sentences of rule text


@dataclass
class Question:
    id: str                       # "q001"
    question: str                 # the question, in our own words
    category: str                 # a key of CATEGORIES
    book: str | None              # "DISP", "BCOBS", "PRIN"; None if unanswerable
    gold: list[str] = field(default_factory=list)       # provisions that answer it, best first
    key_facts: list[str] = field(default_factory=list)  # phrases a correct answer must contain
    split: str = ""               # "dev" (for tuning) or "test" (for the final numbers)
    status: str = "draft"         # "draft", then "checked" or "flagged" after hand review
    note: str = ""                # why the gold is what it is, or what is wrong with it


def load_questions(path: Path = QUESTIONS) -> list[Question]:
    with path.open(encoding="utf-8") as f:
        return [Question(**json.loads(line)) for line in f if line.strip()]


def save_questions(questions: list[Question], path: Path = QUESTIONS) -> None:
    """Write the file in one go, so a crash half way through cannot leave it cut short."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(asdict(q), ensure_ascii=False) + "\n")
    tmp.replace(path)


def normalise(text: str) -> str:
    """Lower-case text with curly quotes made straight and runs of spaces made one.

    Key facts are matched against rule text (and, later, against answers) after this,
    so a difference in quote style or line breaks does not count as a miss.

    >>> normalise("The  firm’s\\n“final response”")
    'the firm\\'s "final response"'
    """
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def contains(text: str, phrase: str) -> bool:
    return normalise(phrase) in normalise(text)


def check_structure(questions: list[Question]) -> list[str]:
    """Problems that can be seen without the rule text. An empty list means none."""
    problems = []
    seen = set()
    for q in questions:
        where = f"{q.id}:"
        if not re.fullmatch(r"q\d{3}", q.id):
            problems.append(f"{where} id should look like q001")
        if q.id in seen:
            problems.append(f"{where} id used twice")
        seen.add(q.id)
        if not q.question.strip().endswith("?"):
            problems.append(f"{where} question should end with a question mark")
        if q.category not in CATEGORIES:
            problems.append(f"{where} unknown category {q.category!r}")
        if q.split not in SPLITS:
            problems.append(f"{where} split should be dev or test, not {q.split!r}")
        if q.status not in STATUSES:
            problems.append(f"{where} unknown status {q.status!r}")
        if q.status == "flagged" and not q.note.strip():
            problems.append(f"{where} a flagged question needs a note saying what is wrong")
        if q.category == "unanswerable":
            if q.gold or q.key_facts or q.book is not None:
                problems.append(f"{where} an unanswerable question has no gold, key facts or book")
            if not q.note.strip():
                problems.append(f"{where} say in the note where the answer would be instead")
            continue
        if q.book not in BOOKS:
            problems.append(f"{where} book should be one of {', '.join(BOOKS)}")
        if not q.gold:
            problems.append(f"{where} needs at least one gold provision")
        if not q.key_facts:
            problems.append(f"{where} needs at least one key fact")
        for fact in q.key_facts:
            if len(fact.split()) > MAX_FACT_WORDS:
                problems.append(f"{where} key fact {fact!r} is too long "
                                f"({MAX_FACT_WORDS} words at most)")
        if len(set(q.gold)) != len(q.gold):
            problems.append(f"{where} a gold provision is listed twice")
        if q.category == "multi" and len(q.gold) < 2:
            problems.append(f"{where} a multi question needs two or more gold provisions")
    return problems


def check_against_rules(questions: list[Question], rules: dict[str, Rule]) -> list[str]:
    """Problems that need the rule text: missing IDs and key facts that are not there.

    For a multi question every key fact must be in one of the gold provisions, and
    every gold provision must hold at least one key fact (otherwise it is not needed).
    For the other categories all key facts must be in the first gold provision; any
    others are alternatives that answer the question just as well.
    """
    problems = []
    for q in questions:
        where = f"{q.id}:"
        missing = [g for g in q.gold if g not in rules]
        for g in missing:
            problems.append(f"{where} gold {g} is not in the rules")
        if missing:
            continue
        for g in q.gold:
            if rules[g].book != q.book:
                problems.append(f"{where} gold {g} is in {rules[g].book}, not {q.book}")
        if q.category == "multi":
            for fact in q.key_facts:
                if not any(contains(rules[g].text, fact) for g in q.gold):
                    problems.append(f"{where} key fact {fact!r} is in none of the gold provisions")
            for g in q.gold:
                if not any(contains(rules[g].text, fact) for fact in q.key_facts):
                    problems.append(f"{where} gold {g} holds none of the key facts")
        else:
            for g in q.gold:
                for fact in q.key_facts:
                    if not contains(rules[g].text, fact):
                        problems.append(f"{where} key fact {fact!r} is not in {g}")
    return problems


def _group(q: Question) -> tuple[str, str]:
    return (q.book or "-", q.category)


def assign_splits(questions: list[Question], dev_size: int = DEV_SIZE, seed: int = SEED) -> None:
    """Put dev_size questions in dev and the rest in test, in the same proportions.

    Each (book, category) group gives dev its fair share, rounded so the total is
    exactly dev_size. The seed fixes which ones, so running this again gives the
    same split.
    """
    groups: dict[tuple[str, str], list[Question]] = {}
    for q in sorted(questions, key=lambda q: q.id):
        groups.setdefault(_group(q), []).append(q)
    share = {k: len(v) * dev_size / len(questions) for k, v in groups.items()}
    take = {k: int(s) for k, s in share.items()}
    # Hand out the places left over to the groups that lost the most by rounding down.
    for k in sorted(share, key=lambda k: (share[k] - take[k], k), reverse=True):
        if sum(take.values()) >= dev_size:
            break
        take[k] += 1
    rng = random.Random(seed)
    for k in sorted(groups):
        members = groups[k][:]
        rng.shuffle(members)
        for i, q in enumerate(members):
            q.split = "dev" if i < take[k] else "test"


def counts(questions: list[Question]) -> dict[str, Counter]:
    return {
        "book": Counter(q.book or "none" for q in questions),
        "category": Counter(q.category for q in questions),
        "split": Counter(q.split for q in questions),
        "status": Counter(q.status for q in questions),
    }


def print_table(questions: list[Question], file=sys.stdout) -> None:
    """Questions per book and category, with dev in brackets."""
    cats = list(CATEGORIES)
    rows = [*BOOKS, "none"]
    print(f"{'':<7}" + "".join(f"{c:>14}" for c in cats) + f"{'total':>11}", file=file)
    for book in rows:
        cells = []
        for c in cats:
            qs = [q for q in questions if (q.book or "none") == book and q.category == c]
            dev = sum(q.split == "dev" for q in qs)
            cells.append(f"{len(qs)} ({dev})" if qs else "-")
        n = sum((q.book or "none") == book for q in questions)
        dev = sum((q.book or "none") == book and q.split == "dev" for q in questions)
        print(f"{book:<7}" + "".join(f"{c:>14}" for c in cells) + f"{f'{n} ({dev})':>11}",
              file=file)
    dev = sum(q.split == "dev" for q in questions)
    print(f"{'total':<7}" + "".join(
        f"{sum(q.category == c for q in questions):>14}" for c in cats)
        + f"{f'{len(questions)} ({dev})':>11}", file=file)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--questions", type=Path, default=QUESTIONS)
    ap.add_argument("--rules", type=Path, default=RULES)
    args = ap.parse_args(argv)

    questions = load_questions(args.questions)
    problems = check_structure(questions)
    if args.rules.exists():
        rules = {r.id: r for r in load_rules(args.rules)}
        problems += check_against_rules(questions, rules)
    else:
        print(f"{args.rules} not found, so gold IDs and key facts were not checked "
              "(run make ingest first)\n")

    print_table(questions)
    status = counts(questions)["status"]
    print("\nreview: " + ", ".join(f"{status[s]} {s}" for s in STATUSES))
    for q in questions:
        if q.status == "flagged":
            print(f"  flagged {q.id}: {q.question}\n          {q.note}")
    if problems:
        print(f"\n{len(problems)} problems:")
        for p in problems:
            print("  " + p)
        return 1
    print("no problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
