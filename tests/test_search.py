"""Tests for the four search methods, using stand-in models (see fakes.py)."""

import math

import numpy as np
import pytest
from fakes import FakeCrossEncoder, FakeEncoder

from rulecite.records import Rule
from rulecite.search import (BM25, CHUNK_OVERLAP, CHUNK_WORDS, DenseIndex, Result, Searcher,
                             chunks, order, rrf, tokenize)


def rule(n: int, text: str, title: str = "Section") -> Rule:
    return Rule(id=f"DISP 1.{n}.1", type="R", book="DISP", kind="rule", chapter="DISP 1",
                section=f"DISP 1.{n}", section_title=title, text=text)


RULES = [
    rule(1, "The respondent must send a final response within eight weeks of the complaint.",
         "Complaints time limit rules"),
    rule(2, "A banking customer may cancel the contract within 14 calendar days.",
         "Cancellation"),
    rule(3, "The firm must refund the amount of an unauthorised payment to the customer.",
         "Unauthorised payments"),
    rule(4, "A firm must act in good faith towards retail customers.", "Consumer Duty"),
]


# ---- words

def test_tokenize_drops_common_words_and_keeps_numbers():
    assert tokenize("What is the time limit in DISP 1.6.2?") == ["time", "limit", "disp", "1.6.2"]


def test_tokenize_makes_word_forms_the_same():
    assert tokenize("cancel cancelled cancellation") == ["cancel"] * 3


# ---- BM25

def test_bm25_score_by_hand():
    docs = [["cancel", "account"], ["complaint", "time", "limit", "complaint"],
            ["account", "statement"]]
    bm = BM25(docs)
    idf = math.log(1 + (3 - 1 + 0.5) / (1 + 0.5))
    norm = 1 - 0.75 + 0.75 * 2 / (8 / 3)
    expected = idf * 1 * 2.5 / (1 + 1.5 * norm)
    assert bm.scores(["cancel"]) == pytest.approx([expected, 0, 0])


def test_bm25_prefers_rare_words():
    bm = BM25([["account", "cancel"], ["account", "statement"], ["account", "fee"]])
    s = bm.scores(["account", "cancel"])
    assert s[0] > s[1] == s[2]


def test_bm25_holds_back_long_documents():
    bm = BM25([["refund"], ["refund"] + ["other"] * 20])
    s = bm.scores(["refund"])
    assert s[0] > s[1] > 0


def test_bm25_repeats_help_less_and_less():
    bm = BM25([["fee"] * n + ["x"] * (10 - n) for n in (1, 2, 4, 8)])
    gains = np.diff(bm.scores(["fee"]))
    assert all(gains > 0) and gains[0] > gains[-1]


def test_bm25_unknown_word_scores_nothing():
    assert BM25([["a"], ["b"]]).scores(["zzz"]).tolist() == [0, 0]


# ---- pieces of long provisions

def test_short_provision_is_one_piece():
    assert len(chunks(RULES[0])) == 1
    assert chunks(RULES[0])[0].startswith("DISP 1.1.1R · Complaints time limit rules\n")


def test_long_provision_is_cut_into_overlapping_pieces():
    words = [f"w{i}" for i in range(500)]
    pieces = chunks(rule(9, " ".join(words)))
    bodies = [p.split("\n", 1)[1].split() for p in pieces]
    assert [len(b) for b in bodies] == [CHUNK_WORDS, CHUNK_WORDS, CHUNK_WORDS]
    assert bodies[1][:CHUNK_OVERLAP] == bodies[0][-CHUNK_OVERLAP:]
    assert bodies[-1][-1] == "w499"
    assert all(p.startswith("DISP 1.9.1R") for p in pieces)


# ---- meaning search

class KeywordEncoder:
    """Points a text one way if it mentions a refund and the other way if not."""

    def encode(self, inputs, prompt=None, **kw):
        return np.array([[1.0, 0.0] if "refund" in t else [0.0, 1.0] for t in inputs])


def test_dense_score_is_the_best_piece(tmp_path):
    long = rule(5, " ".join([f"w{i}" for i in range(400)] + ["refund"]))
    index = DenseIndex([RULES[0], long], KeywordEncoder(), "kw", cache=tmp_path)
    assert len(index.texts) == 1 + len(chunks(long)) == 4
    best, piece = index.scores(np.array([1.0, 0.0]))
    assert best.tolist() == [0.0, 1.0]
    assert piece.tolist() == [0, 3]  # the last piece of the long provision holds "refund"


def test_dense_embeddings_are_cached_per_model_and_text(tmp_path):
    enc = FakeEncoder()
    DenseIndex(RULES, enc, "fake", cache=tmp_path)
    DenseIndex(RULES, enc, "fake", cache=tmp_path)
    assert enc.calls == 1
    DenseIndex(RULES, enc, "other-model", cache=tmp_path)
    DenseIndex(RULES[:2], enc, "fake", cache=tmp_path)
    assert enc.calls == 3
    assert len(list(tmp_path.glob("dense-*.npy"))) == 3


# ---- combining and re-ranking

def test_order_breaks_ties_by_file_order():
    assert order(np.array([1.0, 3.0, 3.0, 2.0])).tolist() == [1, 2, 3, 0]


def test_rrf_rewards_agreement():
    fused = rrf([np.array([0, 1, 2]), np.array([1, 0, 2])], 3)
    assert fused[2] < fused[0] == fused[1]


def test_rerank_only_reorders_the_top():
    res = Result(bm25=np.arange(5), hybrid=np.array([4, 3, 2, 1, 0]),
                 rerank_scores=np.array([0.1, 0.9, 0.5]))
    assert res.rerank(3).tolist() == [3, 2, 4, 1, 0]
    assert res.rerank(2).tolist() == [3, 4, 2, 1, 0]


@pytest.fixture
def searcher(tmp_path):
    return Searcher(RULES, FakeEncoder(), FakeCrossEncoder(), "fake", cache=tmp_path)


def test_every_method_ranks_every_provision(searcher):
    res = searcher.run(["Within how many days can a customer cancel?"], depth=3)[0]
    for method in ("bm25", "dense", "hybrid", "rerank@3"):
        assert sorted(res.ranking(method).tolist()) == [0, 1, 2, 3]
    assert res.ranking("bm25")[0] == 1
    assert res.rerank_scores.shape == (3,)


def test_bm25_only_searcher():
    res = Searcher(RULES).run(["good faith"])[0]
    assert res.dense is None and res.hybrid is None and res.bm25[0] == 3


@pytest.mark.parametrize("method", ["bm25", "dense", "hybrid", "rerank@4"])
def test_search_returns_hits(searcher, method):
    hits = searcher.search("refund of an unauthorised payment", method, k=2)
    assert len(hits) == 2 and hits[0].id == "DISP 1.3.1"


def test_top_score(searcher):
    res = searcher.run(["eight weeks final response"], depth=4)[0]
    assert res.top_score("bm25") == res.bm25_scores.max()
    assert res.top_score("rerank@4") == res.rerank_scores.max()
    assert res.top_score("hybrid") is None
