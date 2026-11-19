"""Answer a question by quoting the rules that answer it, or refuse.

1. Search: the four-step search from milestone 3, ending with the cross-encoder
   re-ranking the top results.
2. Refuse or answer: if the best re-ranker score is below a threshold (chosen
   on the dev questions), say that no rule in these books clearly answers the
   question. The threshold is the one setting milestone 4 tunes.
3. Quote: from each of the top two provisions that clear the threshold, quote
   the sentence or list item that best answers the question (again scored by
   the cross-encoder), with the rest of its list if it is a list item, and
   the provision's citation.

The answer never contains words that are not in the rules. It can still quote
the wrong rule, and the evaluation counts how often it does.

    python -m rulecite.answer "How long do I have to cancel a new savings account?"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .records import Rule, load_rules
from .search import (CACHE, DENSE_MODEL, RERANKER, CrossScorer, Searcher, load_models,
                     order)
from .testset import RULES

MAX_QUOTES = 2           # quote from at most this many provisions
CHOICE = Path("results/answers-choice.json")
SEARCH_CHOICE = Path("results/search-choice.json")
DEFAULT_THRESHOLD = 0.0  # used only until the dev run has chosen one
GAP = " … "

_NOTE = re.compile(r"^\[?Note:", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.;])\s+(?=[A-Z(])")
# Some lists in the PDFs carry an extra running number before the real marker,
# as in "is: 1. (a) £350,000 ...; and 2. (b) £160,000". The number is dropped,
# or the "1." would be read as the end of a sentence.
_STRAY_NUMBER = re.compile(r"(^|\s)\d{1,2}\.\s+(?=\()")
_MARKER = re.compile(r"^\((\d+[A-Z]*|[a-z]{1,2}|[ivx]+)\)")


def units(text: str) -> list[str]:
    """The provision's sentences and list items, the pieces an answer can quote.

    Lines are list items or paragraphs (the parser keeps them apart); long
    lines are split into sentences. Editorial notes are left out, and very
    short pieces are joined to the piece before.

    >>> units("The firm must:\\n(1) refund; and\\n(2) tell the customer. It must act fast.\\n[Note: x]")
    ['The firm must:', '(1) refund; and', '(2) tell the customer.', 'It must act fast.']
    >>> units("(1) The award is: 1. (a) £350,000; and\\n2. (b) £160,000.")
    ['(1) The award is:', '(a) £350,000; and', '(b) £160,000.']
    """
    out: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or _NOTE.match(line):
            continue
        line = _STRAY_NUMBER.sub(r"\1", line).strip()
        line = re.sub(r":\s+(?=\()", ":\n", line)  # a list item after a lead-in starts a piece
        for piece in [p for part in line.split("\n") for p in _SENTENCE_END.split(part)]:
            piece = piece.strip()
            if out and len(piece.split()) < 3 and not piece.startswith("("):
                out[-1] += " " + piece
            elif piece:
                out.append(piece)
    return out


LIST_WORDS = 150          # a whole list is quoted if it is at most this long


def is_item(piece: str) -> bool:
    """A list item, or the continuation of a sentence that a list interrupted."""
    return piece.startswith("(") or piece[:1].islower() or bool(re.match(r"\d+\. ", piece))


def marker_kind(piece: str) -> str | None:
    """The kind of list marker a piece starts with: number, letter or roman.

    >>> [marker_kind(p) for p in ["(2) x", "(1A) x", "(b) x", "(iv) x", "Text"]]
    ['number', 'number', 'letter', 'roman', None]
    """
    m = _MARKER.match(piece)
    if not m:
        return None
    label = m.group(1)
    if label[0].isdigit():
        return "number"
    return "roman" if re.fullmatch(r"[ivx]+", label) else "letter"


def lead_in(pieces: list[str], i: int) -> int | None:
    """The piece that introduces list item i (the nearest one before it ending in ':').

    >>> lead_in(["Keep records for:", "(1) five years; and", "(2) three years."], 2)
    0
    >>> lead_in(["A firm must act.", "It must be fair."], 1) is None
    True
    >>> lead_in(["It does not apply to:", "(1) x;", "(2) y which:", "(a) z;", "(3) w."], 4)
    0
    """
    if not is_item(pieces[i]):
        return None
    kind = marker_kind(pieces[i])
    for j in range(i - 1, -1, -1):
        # A lead-in at the item's own level is a sibling with its own sub-list, not ours.
        if pieces[j].rstrip().endswith(":") and (kind is None or marker_kind(pieces[j]) != kind):
            return j
    return None


def quote_around(pieces: list[str], i: int) -> str:
    """What to quote when piece i is the best one.

    A piece on its own, unless it belongs to a list. Then the whole list with
    its lead-in, so that an answer to "what must the response include?" names
    every item; or, if that list is too long, the lead-in and piece i.

    >>> quote_around(["Keep records for:", "(1) five years; and", "(2) three years."], 2)
    'Keep records for: (1) five years; and (2) three years.'
    >>> quote_around(["A firm must act.", "It must be fair."], 1)
    'It must be fair.'
    """
    lead = i if pieces[i].rstrip().endswith(":") else lead_in(pieces, i)
    if lead is None:
        return pieces[i]
    level = marker_kind(pieces[lead])
    end = lead + 1
    while end < len(pieces) and is_item(pieces[end]):
        if level and marker_kind(pieces[end]) == level:
            break  # the next item at the lead-in's own level ends its list
        end += 1
    whole = " ".join(pieces[lead:end])
    if len(whole.split()) <= LIST_WORDS:
        return whole
    if lead == i:
        return pieces[i]
    return pieces[lead] + (" " if lead == i - 1 else GAP) + pieces[i]


def extract(rule: Rule, question: str, cross: CrossScorer) -> tuple[str, float]:
    """The best piece of the provision for this question, with the rest of its list."""
    pieces = units(rule.text) or [rule.text]
    scores = np.asarray(cross.predict([(question, p) for p in pieces], batch_size=32,
                                      show_progress_bar=False, convert_to_numpy=True),
                        dtype=float).reshape(-1)
    best = int(np.argmax(scores))
    return quote_around(pieces, best), float(scores[best])


@dataclass
class Quote:
    id: str
    citation: str
    score: float          # the re-ranker's score for the whole provision
    text: str             # the piece quoted
    full: str = ""        # the whole provision, for the comparison in the evaluation


@dataclass
class Draft:
    """Everything needed to answer at any threshold, computed once per question."""

    question: str
    candidates: list[Quote] = field(default_factory=list)  # best first

    @property
    def top_score(self) -> float:
        return self.candidates[0].score if self.candidates else float("-inf")


@dataclass
class Answer:
    question: str
    refused: bool
    quotes: list[Quote]
    top_score: float
    threshold: float

    def text(self, whole: bool = False) -> str:
        """The answer as one string: each quote followed by its citation."""
        return " ".join(f"{q.full if whole else q.text} [{q.citation}]" for q in self.quotes)


def decide(draft: Draft, threshold: float, max_quotes: int = MAX_QUOTES) -> Answer:
    """Refuse if the best score is below the threshold, else quote what clears it."""
    quotes = [c for c in draft.candidates[:max_quotes] if c.score >= threshold]
    return Answer(draft.question, refused=not quotes, quotes=quotes,
                  top_score=draft.top_score, threshold=threshold)


class Answerer:
    def __init__(self, searcher: Searcher, depth: int = 50, max_quotes: int = MAX_QUOTES):
        if searcher.cross is None:
            raise ValueError("answering needs the cross-encoder")
        self.searcher, self.depth, self.max_quotes = searcher, depth, max_quotes

    def drafts(self, questions: list[str]) -> list[Draft]:
        out = []
        for question, res in zip(questions, self.searcher.run(questions, depth=self.depth)):
            top = res.hybrid[:self.depth]
            scores = res.rerank_scores[:self.depth]
            draft = Draft(question)
            for k in order(scores)[:self.max_quotes]:
                rule = self.searcher.rules[top[k]]
                text, _ = extract(rule, question, self.searcher.cross)
                draft.candidates.append(Quote(rule.id, rule.citation, round(float(scores[k]), 4),
                                              text, rule.text))
            out.append(draft)
        return out

    def answer(self, question: str, threshold: float) -> Answer:
        return decide(self.drafts([question])[0], threshold, self.max_quotes)


def saved_threshold(path: Path = CHOICE) -> float:
    """The threshold chosen on dev, or the default before there is one."""
    if path.exists():
        return float(json.loads(path.read_text())["threshold"])
    return DEFAULT_THRESHOLD


def saved_depth(path: Path = SEARCH_CHOICE) -> int:
    if path.exists():
        return int(json.loads(path.read_text())["rerank_depth"])
    return 50


def show(answer: Answer, rules: dict[str, Rule]) -> str:
    wrap = lambda s: textwrap.fill(s, 88, initial_indent="    ", subsequent_indent="    ")  # noqa: E731
    if answer.refused:
        return ("No provision in DISP, BCOBS or PRIN clearly answers this. "
                f"(Best match scored {answer.top_score:.2f}, below the threshold of "
                f"{answer.threshold:.2f}.)")
    lines = []
    for i, q in enumerate(answer.quotes):
        rule = rules[q.id]
        label = "Answer" if i == 0 else "Also relevant"
        lines += [f"{label}: {q.citation}  {rule.section_title}  (score {q.score:.2f})",
                  wrap(f"“{q.text}”"), ""]
    lines.append("Quoted from the FCA Handbook. Check the full provision before relying on it; "
                 "this is not legal advice.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("question")
    ap.add_argument("--threshold", type=float, default=None,
                    help="refuse below this re-ranker score (default: the one chosen on dev)")
    ap.add_argument("--rules", type=Path, default=RULES)
    ap.add_argument("--dense-model", default=DENSE_MODEL)
    ap.add_argument("--reranker", default=RERANKER)
    ap.add_argument("--cache", type=Path, default=CACHE)
    ap.add_argument("--json", action="store_true", help="print the answer as JSON")
    args = ap.parse_args(argv)

    if not args.rules.exists():
        print(f"{args.rules} not found: run make ingest first.")
        return 1
    rules = load_rules(args.rules)
    encoder, cross = load_models(args.dense_model, args.reranker)
    answerer = Answerer(Searcher(rules, encoder, cross, args.dense_model, cache=args.cache),
                        depth=saved_depth())
    threshold = saved_threshold() if args.threshold is None else args.threshold
    answer = answerer.answer(args.question, threshold)
    if args.json:
        print(json.dumps(asdict(answer), indent=1, ensure_ascii=False))
    else:
        print("\n" + show(answer, {r.id: r for r in rules}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
