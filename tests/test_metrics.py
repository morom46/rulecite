"""Tests for the scores and statistical tests (the simple cases are doctests in metrics.py)."""

import pytest

from rulecite.metrics import bootstrap_ci, gold_rank, mcnemar, mrr, recall_at


def test_multi_question_needs_every_gold():
    assert gold_rank(["a", "b"], ["a", "z"], "multi") is None


def test_alternative_gold_counts_for_a_single_question():
    assert gold_rank(["x", "y", "alt"], ["main", "alt"], "fact") == 3


def test_recall_and_mrr_of_nothing():
    assert recall_at([], 5) == 0.0 and mrr([]) == 0.0


def test_bootstrap_is_repeatable_and_brackets_the_mean():
    values = [1] * 70 + [0] * 30
    lo, hi = bootstrap_ci(values, seed=1)
    assert (lo, hi) == bootstrap_ci(values, seed=1)
    assert lo < 0.7 < hi
    assert 0.58 < lo < 0.65 and 0.75 < hi < 0.82


def test_bootstrap_of_all_hits():
    assert bootstrap_ci([1] * 20) == (1.0, 1.0)


def test_mcnemar_is_symmetric():
    a = [1, 1, 1, 0, 0, 1, 0]
    b = [0, 1, 0, 1, 0, 0, 0]
    only_a, only_b, p = mcnemar(a, b)
    assert (only_a, only_b) == (3, 1)
    assert mcnemar(b, a) == (1, 3, p)
    assert p == pytest.approx(0.625)


def test_mcnemar_without_disagreement():
    assert mcnemar([1, 0], [1, 0]) == (0, 0, 1.0)
