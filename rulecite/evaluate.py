"""Score the search methods on the test set.

    python -m rulecite.evaluate --split dev    # compare the methods, choose the re-ranking depth
    python -m rulecite.evaluate --split test   # the reported numbers, using the depth chosen on dev

The dev run writes results/search-choice.json, and the test run refuses to start
without it: the test questions are never used to choose anything.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

from .metrics import bootstrap_ci, gold_rank, hits, mcnemar, mrr, recall_at
from .records import load_rules
from .search import CACHE, DENSE_MODEL, RERANKER, Searcher, load_models
from .testset import QUESTIONS, RULES, Question, load_questions

RESULTS = Path("results")
DEPTHS = (10, 20, 50)          # how many hybrid results the cross-encoder reorders
KS = (1, 3, 5, 10, 20)
KINDS = ("fact", "number", "scope", "multi")
COMPARISONS = (("hybrid", "bm25"), ("hybrid", "dense"), ("rerank", "hybrid"), ("rerank", "bm25"))


def score(questions: list[Question], searcher: Searcher, methods: list[str],
          depth: int) -> dict:
    """Run every method on every question and collect ranks, top results and scores."""
    start = time.perf_counter()
    results = searcher.run([q.question for q in questions], depth=depth)
    seconds = time.perf_counter() - start
    ids = [r.id for r in searcher.rules]
    per_question = []
    for q, res in zip(questions, results):
        entry = {"id": q.id, "category": q.category, "gold": q.gold, "methods": {}}
        for m in methods:
            ranked = [ids[i] for i in res.ranking(m)]
            entry["methods"][m] = {
                "rank": gold_rank(ranked, q.gold, q.category) if q.gold else None,
                "top10": ranked[:10],
                "top_score": None if (t := res.top_score(m)) is None else round(t, 4),
            }
        per_question.append(entry)
    return {"methods": methods, "questions": per_question, "seconds": round(seconds, 1)}


def write_json(report: dict, path: Path) -> None:
    """The report as JSON with one question per line, so a diff shows which questions changed."""
    questions = report["questions"]
    head = [f" {json.dumps(k)}: {json.dumps(v)}," for k, v in report.items() if k != "questions"]
    body = [f"  {json.dumps(q)}{',' if i < len(questions) - 1 else ''}"
            for i, q in enumerate(questions)]
    path.write_text("\n".join(["{", *head, ' "questions": [', *body, " ]", "}"]) + "\n")


def summary(report: dict) -> dict[str, dict]:
    """Recall@k, MRR and recall@5 per kind of question, over the answerable questions."""
    out = {}
    answerable = [q for q in report["questions"] if q["category"] != "unanswerable"]
    for m in report["methods"]:
        ranks = [q["methods"][m]["rank"] for q in answerable]
        row = {f"R@{k}": round(recall_at(ranks, k), 4) for k in KS}
        row["MRR@10"] = round(mrr(ranks, 10), 4)
        for kind in KINDS:
            kr = [q["methods"][m]["rank"] for q in answerable if q["category"] == kind]
            row[kind] = round(recall_at(kr, 5), 4) if kr else None
        out[m] = row
    return out


def choose_depth(table: dict[str, dict]) -> int:
    """The re-ranking depth with the best recall@5 on dev; then best MRR; then the smallest."""
    return max(DEPTHS, key=lambda d: (table[f"rerank@{d}"]["R@5"],
                                      table[f"rerank@{d}"]["MRR@10"], -d))


def significance(report: dict, depth: int) -> dict:
    """Bootstrap intervals for recall@5 and McNemar tests between methods (test split)."""
    answerable = [q for q in report["questions"] if q["category"] != "unanswerable"]
    name = {"rerank": f"rerank@{depth}"}
    found = {m: hits([q["methods"][m]["rank"] for q in answerable], 5) for m in report["methods"]}
    intervals = {m: tuple(round(x, 4) for x in bootstrap_ci(v)) for m, v in found.items()}
    tests = []
    for a, b in COMPARISONS:
        a, b = name.get(a, a), name.get(b, b)
        only_a, only_b, p = mcnemar(found[a], found[b])
        tests.append({"a": a, "b": b, "only_a": only_a, "only_b": only_b, "p": p})
    return {"intervals": intervals, "tests": tests}


def top_scores(report: dict) -> dict[str, dict]:
    """Median score of the first result, for answerable and unanswerable questions."""
    out = {}
    for m in report["methods"]:
        groups = {"answerable": [], "unanswerable": []}
        for q in report["questions"]:
            s = q["methods"][m]["top_score"]
            if s is not None:
                key = "unanswerable" if q["category"] == "unanswerable" else "answerable"
                groups[key].append(s)
        if all(groups.values()):
            out[m] = {k: float(np.median(v)) for k, v in groups.items()}
    return out


def pvalue(p: float) -> str:
    """
    >>> pvalue(0.0386), pvalue(0.00001)
    ('0.039', '<0.001')
    """
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.0f}"


def markdown(report: dict, split: str, table: dict, models: dict, depth: int | None,
             sig: dict | None = None) -> str:
    qs = report["questions"]
    answerable = [q for q in qs if q["category"] != "unanswerable"]
    counts = {k: sum(q["category"] == k for q in answerable) for k in KINDS}
    lines = [
        f"# Search results: {split}",
        "",
        f"{len(qs)} {split} questions, {len(answerable)} of them answerable. "
        f"Made by `python -m rulecite.evaluate --split {split}` on {date.today():%d %B %Y} "
        f"with `{models['dense']}` and `{models['reranker']}`, on the CPU. "
        f"Searching took {report['seconds']} s for {len(qs)} questions.",
        "",
        "Recall@k is the share of answerable questions whose gold provision is in the top k "
        "results (for multi questions, all of them). MRR@10 is the mean of 1/rank. "
        "All numbers are percentages.",
        "",
        "| method | R@1 | R@3 | R@5 | R@10 | R@20 | MRR@10 |",
        "|---|---|---|---|---|---|---|",
    ]
    for m, row in table.items():
        lines.append(f"| {m} | " + " | ".join(pct(row[c]) for c in
                                               [f"R@{k}" for k in KS] + ["MRR@10"]) + " |")
    lines += ["", "Recall@5 by kind of question:", "",
              "| method | " + " | ".join(f"{k} ({counts[k]})" for k in KINDS) + " |",
              "|---|" + "---|" * len(KINDS)]
    for m, row in table.items():
        lines.append(f"| {m} | " + " | ".join(pct(row[k]) for k in KINDS) + " |")
    if split == "dev" and depth is not None:
        lines += ["", f"**Chosen re-ranking depth: {depth}** (best recall@5 on dev, "
                  "then best MRR@10, then the smallest). Saved to `results/search-choice.json` "
                  "for the test run."]
    if sig:
        lines += ["", "## How sure are these numbers?", "",
                  "95% bootstrap intervals for recall@5 (10,000 resamples of the questions):", "",
                  "| method | R@5 | 95% interval |", "|---|---|---|"]
        for m, (lo, hi) in sig["intervals"].items():
            lines.append(f"| {m} | {pct(table[m]['R@5'])} | {pct(lo)} to {pct(hi)} |")
        lines += ["", "Exact McNemar tests on recall@5: of the questions where two methods "
                  "disagree, how many each one got, and the chance of a split that uneven if "
                  "they were equally good.", "",
                  "| A | B | only A finds | only B finds | p |", "|---|---|---|---|---|"]
        for t in sig["tests"]:
            lines.append(f"| {t['a']} | {t['b']} | {t['only_a']} | {t['only_b']} "
                         f"| {pvalue(t['p'])} |")
    ts = top_scores(report)
    if ts:
        lines += ["", "## Score of the first result", "",
                  "For milestone 4, which has to refuse unanswerable questions: the median "
                  "score of the top result for each kind of question.", "",
                  "| method | answerable | unanswerable |", "|---|---|---|"]
        for m, v in ts.items():
            lines.append(f"| {m} | {v['answerable']:.3f} | {v['unanswerable']:.3f} |")
    return "\n".join(lines) + "\n"


def print_table(table: dict) -> None:
    cols = [f"R@{k}" for k in KS] + ["MRR@10"] + [f"{k[:5]}@5" for k in KINDS]
    print(f"{'method':<11}" + "".join(f"{c:>9}" for c in cols))
    for m, row in table.items():
        vals = [row[f"R@{k}"] for k in KS] + [row["MRR@10"]] + [row[k] for k in KINDS]
        print(f"{m:<11}" + "".join(f"{pct(v):>9}" for v in vals))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", choices=("dev", "test"), required=True)
    ap.add_argument("--questions", type=Path, default=QUESTIONS)
    ap.add_argument("--rules", type=Path, default=RULES)
    ap.add_argument("--out", type=Path, default=RESULTS)
    ap.add_argument("--dense-model", default=DENSE_MODEL)
    ap.add_argument("--reranker", default=RERANKER)
    ap.add_argument("--cache", type=Path, default=CACHE, help="where the embeddings are saved")
    ap.add_argument("--bm25-only", action="store_true",
                    help="keyword search only, no models; prints the table and writes nothing")
    args = ap.parse_args(argv)

    if not args.rules.exists():
        print(f"{args.rules} not found: run make ingest first.")
        return 1
    questions = [q for q in load_questions(args.questions) if q.split == args.split]
    unchecked = sum(q.status != "checked" for q in questions)
    if unchecked:
        print(f"Note: {unchecked} of these questions are not marked checked yet (make review).\n")
    rules = load_rules(args.rules)

    if args.bm25_only:
        report = score(questions, Searcher(rules), ["bm25"], depth=0)
        print_table(summary(report))
        return 0

    choice_file = args.out / "search-choice.json"
    if args.split == "test":
        if not choice_file.exists():
            print(f"{choice_file} not found: run the dev split first, which chooses the "
                  "re-ranking depth.")
            return 1
        depth = json.loads(choice_file.read_text())["rerank_depth"]
        methods = ["bm25", "dense", "hybrid", f"rerank@{depth}"]
    else:
        depth = max(DEPTHS)
        methods = ["bm25", "dense", "hybrid"] + [f"rerank@{d}" for d in DEPTHS]

    print("Loading the models (downloaded the first time, about 220 MB) ...")
    start = time.perf_counter()
    encoder, cross = load_models(args.dense_model, args.reranker)
    searcher = Searcher(rules, encoder, cross, args.dense_model, cache=args.cache)
    print(f"Ready in {time.perf_counter() - start:.0f} s. Searching ...\n")
    report = score(questions, searcher, methods, depth)
    table = summary(report)
    models = {"dense": args.dense_model, "reranker": args.reranker}

    sig = None
    if args.split == "dev":
        depth = choose_depth(table)
        choice = {"rerank_depth": depth, "chosen_on": "dev",
                  "dev_recall_at_5": {f"rerank@{d}": table[f"rerank@{d}"]["R@5"]
                                      for d in DEPTHS}}
        args.out.mkdir(parents=True, exist_ok=True)
        choice_file.write_text(json.dumps(choice, indent=2) + "\n")
    else:
        sig = significance(report, depth)

    args.out.mkdir(parents=True, exist_ok=True)
    report.update(models=models, summary=table, rerank_depth=depth)
    if sig:
        report["significance"] = sig
    write_json(report, args.out / f"search-{args.split}.json")
    md = markdown(report, args.split, table, models, depth, sig)
    (args.out / f"search-{args.split}.md").write_text(md)

    print_table(table)
    if args.split == "dev":
        print(f"\nChosen re-ranking depth: {depth}")
    else:
        print()
        for t in sig["tests"]:
            print(f"{t['a']:>10} vs {t['b']:<10} only A {t['only_a']:>3}, "
                  f"only B {t['only_b']:>3}, p = {pvalue(t['p'])}")
    print(f"\nWritten: {args.out / f'search-{args.split}.md'} and .json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
