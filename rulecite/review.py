"""Check the test set by hand, one question at a time, against the rule text.

For each question this shows the gold provisions in full with the key facts
marked, and asks whether the question, its gold and its key facts are right.
For an unanswerable question it shows the provisions that share the most words
with it, so you can confirm that none of them answers it.

Every answer is saved straight away. Quit at any time and run it again to carry
on from the first question still marked draft.

    python -m rulecite.review                 # go through the drafts
    python -m rulecite.review --from q040     # start at q040, whatever its status
    python -m rulecite.review --flagged       # look again at the flagged ones
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import textwrap
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from .records import Rule, load_rules
from .testset import QUESTIONS, RULES, Question, load_questions, normalise, save_questions

WIDTH = 88
STOPWORDS = set("""a an and are as at be been by can do does for from has have how if in is it
its of on or so that the their them they this to was what when where which who will with
would must may should any all not no than into out up about after before under over our
your you my i we he she his her firm firms customer customers bank banks""".split())

HELP = "[c] correct   [f] flag a problem   [e] edit wording   [s] skip   [b] back   [q] quit"


class Style:
    """Bold for headings and key facts when printing to a terminal, plain text otherwise."""

    def __init__(self, colour: bool):
        self.colour = colour

    def bold(self, s: str) -> str:
        return f"\033[1m{s}\033[0m" if self.colour else s

    def fact(self, s: str) -> str:
        return f"\033[1;33m{s}\033[0m" if self.colour else f"[[{s}]]"

    def dim(self, s: str) -> str:
        return f"\033[2m{s}\033[0m" if self.colour else s


def mark_facts(text: str, facts: list[str], style: Style) -> str:
    """Wrap every key fact found in the text in the fact style.

    Matching ignores case, quote style and spacing, the same way the checker does.

    >>> mark_facts("Within eight  weeks of it.", ["Eight weeks"], Style(False))
    'Within [[eight  weeks]] of it.'
    """
    spans = []
    for fact in facts:
        words = [re.escape(normalise(w)) for w in fact.split()]
        words = [w.replace("'", "['’]").replace('"', '["“”]') for w in words]
        pattern = re.compile(r"\s+".join(words), re.IGNORECASE)
        spans += [m.span() for m in pattern.finditer(text)]
    out, last = [], 0
    for start, end in sorted(spans):
        if start < last:
            continue
        out += [text[last:start], style.fact(text[start:end])]
        last = end
    return "".join(out + [text[last:]])


def wrap(text: str, indent: str = "    ") -> str:
    lines = []
    for para in text.split("\n"):
        lines += textwrap.wrap(para, WIDTH, initial_indent=indent, subsequent_indent=indent) or [""]
    return "\n".join(lines)


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9£]+", normalise(text)) if w not in STOPWORDS}


class WordIndex:
    """Which words each provision uses, and how rare each word is across all of them."""

    def __init__(self, rules: dict[str, Rule]):
        self.rules = rules
        self.words = {pid: words(r.text) for pid, r in rules.items()}
        df = Counter(w for ws in self.words.values() for w in ws)
        self.weight = {w: math.log(len(rules) / n) for w, n in df.items()}

    def nearest(self, question: str, k: int = 3) -> list[Rule]:
        """The k provisions sharing the most rare words with the question (a rough check only)."""
        q = words(question)

        def score(pid: str) -> float:
            return sum(self.weight[w] for w in q & self.words[pid])

        best = sorted(self.rules, key=lambda pid: (-score(pid), pid))[:k]
        return [self.rules[pid] for pid in best]


def show(q: Question, rules: dict[str, Rule], position: str, style: Style,
         index: WordIndex | None = None) -> str:
    book = q.book or "no book"
    out = [
        "",
        "=" * WIDTH,
        style.bold(f"{q.id}   {book} · {q.category} · {q.split} · {q.status}") + "   " + position,
        "",
        wrap(style.bold(q.question), indent=""),
        "",
    ]
    if q.category == "unanswerable":
        out += [f"Should be unanswerable from DISP, BCOBS and PRIN. Note: {q.note}", "",
                style.dim("Nearest provisions by shared words. None of these should answer it:")]
        for r in (index or WordIndex(rules)).nearest(q.question):
            out += [f"  {style.bold(r.citation)}  {r.section_title}",
                    wrap(r.text[:300] + (" ..." if len(r.text) > 300 else ""))]
        return "\n".join(out)
    for i, g in enumerate(q.gold):
        r = rules.get(g)
        label = "gold" if i == 0 else "also"
        if r is None:
            out += [f"  {label} {g}: NOT FOUND in the rules"]
            continue
        heading = " · ".join(x for x in (r.section_title, r.heading) if x)
        out += [f"  {label} {style.bold(r.citation)}  {style.dim(heading)}",
                wrap(mark_facts(r.text, q.key_facts, style)), ""]
    out.append("key facts: " + ", ".join(f'"{f}"' for f in q.key_facts))
    if q.note:
        out.append(f"note: {q.note}")
    return "\n".join(out)


def review(questions: list[Question], rules: dict[str, Rule], save: Callable[[], None],
           ask: Callable[[str], str] = input, say: Callable[[str], None] = print,
           start: str | None = None, flagged: bool = False, colour: bool = False) -> int:
    """Go through the questions, saving after every change. Returns how many were changed."""
    style = Style(colour)
    if start:
        todo = [i for i, q in enumerate(questions) if q.id >= start]
    elif flagged:
        todo = [i for i, q in enumerate(questions) if q.status == "flagged"]
    else:
        todo = [i for i, q in enumerate(questions) if q.status == "draft"]
    if not todo:
        say("Nothing to review.")
        return 0

    index = WordIndex(rules)
    changed = 0
    pos = 0
    while 0 <= pos < len(todo):
        q = questions[todo[pos]]
        left = sum(x.status == "draft" for x in questions)
        say(show(q, rules, f"({pos + 1} of {len(todo)}, {left} drafts left)", style, index))
        say(style.dim(HELP))
        choice = ask("> ").strip().lower()[:1]
        if choice == "c":
            q.status = "checked"
        elif choice == "f":
            note = ask("What is wrong? > ").strip()
            if not note:
                say("A flag needs a note. Nothing changed.")
                continue
            q.status, q.note = "flagged", note
        elif choice == "e":
            new = ask("New wording (Enter keeps the old one) > ").strip()
            if new:
                q.question = new if new.endswith("?") else new + "?"
                save()
                changed += 1
            continue  # show it again with the new wording, then decide
        elif choice == "s":
            pos += 1
            continue
        elif choice == "b":
            pos = max(pos - 1, 0)
            continue
        elif choice == "q":
            break
        else:
            say(HELP)
            continue
        save()
        changed += 1
        pos += 1

    done = sum(x.status == "checked" for x in questions)
    flags = sum(x.status == "flagged" for x in questions)
    say(f"\nSaved. {done} checked, {flags} flagged, "
        f"{sum(x.status == 'draft' for x in questions)} still draft.")
    return changed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--questions", type=Path, default=QUESTIONS)
    ap.add_argument("--rules", type=Path, default=RULES)
    ap.add_argument("--from", dest="start", metavar="ID", help="start at this question")
    ap.add_argument("--flagged", action="store_true", help="only the flagged questions")
    args = ap.parse_args(argv)

    if not args.rules.exists():
        print(f"{args.rules} not found: run make ingest first.")
        return 1
    questions = load_questions(args.questions)
    rules = {r.id: r for r in load_rules(args.rules)}
    try:
        review(questions, rules, save=lambda: save_questions(questions, args.questions),
               start=args.start, flagged=args.flagged, colour=sys.stdout.isatty())
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. Everything up to the last answer is saved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
