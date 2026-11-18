"""How search is scored, and how sure we can be that one method beats another."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def gold_rank(ranked: Sequence[str], gold: list[str], category: str) -> int | None:
    """The position (from 1) at which the question counts as found, or None.

    For a multi question that is where the last of its gold provisions appears,
    since all of them are needed. For the others it is where the first of them
    appears, since any one answers it.

    >>> gold_rank(["a", "b", "c", "d"], ["c", "b"], "fact")
    2
    >>> gold_rank(["a", "b", "c", "d"], ["c", "b"], "multi")
    3
    >>> gold_rank(["a", "b"], ["z"], "fact") is None
    True
    """
    position = {pid: i + 1 for i, pid in enumerate(ranked)}
    ranks = [position.get(g) for g in gold]
    if category == "multi":
        return None if None in ranks else max(ranks)
    found = [r for r in ranks if r is not None]
    return min(found) if found else None


def hits(ranks: Sequence[int | None], k: int) -> np.ndarray:
    """1 for each question found in the top k, else 0."""
    return np.array([1 if r is not None and r <= k else 0 for r in ranks])


def recall_at(ranks: Sequence[int | None], k: int) -> float:
    """Share of questions whose answer is in the top k results.

    >>> recall_at([1, 3, None, 7], 5)
    0.5
    """
    return float(hits(ranks, k).mean()) if len(ranks) else 0.0


def mrr(ranks: Sequence[int | None], k: int = 10) -> float:
    """Mean reciprocal rank: 1 for an answer in first place, 1/2 for second, ... 0 past k.

    >>> mrr([1, 2, None, 20])
    0.375
    """
    if not ranks:
        return 0.0
    return float(np.mean([1 / r if r is not None and r <= k else 0.0 for r in ranks]))


def bootstrap_ci(values: Sequence[float], n: int = 10_000, seed: int = 0,
                 level: float = 0.95) -> tuple[float, float]:
    """A confidence interval for the mean, by resampling the questions with replacement.

    Each resample is a set of questions of the same size, some picked twice and
    some not at all. The spread of the means over many resamples shows how much
    the score could move with a different draw of questions.
    """
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), size=(n, len(values)))].mean(axis=1)
    tail = (1 - level) / 2
    return float(np.quantile(means, tail)), float(np.quantile(means, 1 - tail))


def mcnemar(a: Sequence[int], b: Sequence[int]) -> tuple[int, int, float]:
    """Exact McNemar test on paired right/wrong results of two methods.

    Only the questions where the methods disagree count: `only_a` that only A
    got right and `only_b` that only B got right. If the methods were equally
    good, each disagreement would be a coin toss, so the p-value is the chance
    of a split at least this uneven from fair coin tosses.

    >>> mcnemar([1] * 10 + [0] * 2, [0] * 10 + [1] * 2)
    (10, 2, 0.0386)
    """
    only_a = sum(1 for x, y in zip(a, b) if x and not y)
    only_b = sum(1 for x, y in zip(a, b) if y and not x)
    n = only_a + only_b
    if n == 0:
        return 0, 0, 1.0
    tail = sum(math.comb(n, i) for i in range(min(only_a, only_b) + 1)) / 2 ** n
    return only_a, only_b, round(min(1.0, 2 * tail), 4)
