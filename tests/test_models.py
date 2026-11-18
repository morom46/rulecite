"""The search pipeline with the real sentence-transformers library, on tiny untrained models.

The models are built here from scratch (a small vocabulary and a two-layer
network with random weights), so these tests need no download and no
internet. Their rankings mean nothing; what is tested is that our code calls
the library correctly. They are skipped where sentence-transformers is not
installed, as on the GitHub test machines.
"""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("sentence_transformers")

from rulecite.evaluate import score, summary  # noqa: E402
from rulecite.records import Rule  # noqa: E402
from rulecite.search import Searcher  # noqa: E402
from rulecite.testset import Question  # noqa: E402

TEXTS = [
    "The respondent must send a final response within eight weeks of the complaint.",
    "A banking customer may cancel the contract within 14 calendar days without penalty.",
    "The firm must refund the amount of an unauthorised payment.",
    "A firm must act in good faith towards retail customers.",
]


def build_tiny_models(folder: Path) -> tuple[str, str]:
    """Save a tiny BERT encoder and a tiny BERT cross-encoder, both with random weights."""
    from tokenizers import Tokenizer, models, pre_tokenizers, trainers
    from transformers import (BertConfig, BertForSequenceClassification, BertModel,
                              PreTrainedTokenizerFast)

    raw = Tokenizer(models.WordPiece(unk_token="[UNK]"))
    raw.pre_tokenizer = pre_tokenizers.BertPreTokenizer()
    special = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
    raw.train_from_iterator(TEXTS * 5, trainers.WordPieceTrainer(vocab_size=200,
                                                                 special_tokens=special))
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=raw, unk_token="[UNK]",
                                        pad_token="[PAD]", cls_token="[CLS]",
                                        sep_token="[SEP]", mask_token="[MASK]")
    config = BertConfig(vocab_size=raw.get_vocab_size(), hidden_size=32, num_hidden_layers=2,
                        num_attention_heads=2, intermediate_size=64,
                        max_position_embeddings=512, num_labels=1)
    paths = []
    for name, model in (("encoder", BertModel(config)),
                        ("cross", BertForSequenceClassification(config))):
        path = folder / name
        model.save_pretrained(path)
        tokenizer.save_pretrained(path)
        paths.append(str(path))
    return paths[0], paths[1]


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    from sentence_transformers import CrossEncoder, SentenceTransformer

    enc_path, cross_path = build_tiny_models(tmp_path_factory.mktemp("models"))
    return enc_path, SentenceTransformer(enc_path, device="cpu"), CrossEncoder(
        cross_path, device="cpu", max_length=128)


@pytest.fixture
def rules():
    return [Rule(id=f"DISP 1.{i}.1", type="R", book="DISP", kind="rule", chapter="DISP 1",
                 section=f"DISP 1.{i}", text=t) for i, t in enumerate(TEXTS, 1)]


def test_dense_and_rerank_run_with_the_real_library(models, rules, tmp_path):
    name, encoder, cross = models
    searcher = Searcher(rules, encoder, cross, dense_model=name, cache=tmp_path)
    res = searcher.run(["How long to cancel a bank contract?", "good faith"], depth=3)
    for r in res:
        assert sorted(r.dense.tolist()) == [0, 1, 2, 3]
        assert sorted(r.hybrid.tolist()) == [0, 1, 2, 3]
        assert r.rerank_scores.shape == (3,)
        assert sorted(r.rerank(3).tolist()) == [0, 1, 2, 3]
    # The embeddings were cached, and a second index loads them instead of encoding again.
    assert len(list(tmp_path.glob("dense-*.npy"))) == 1
    again = Searcher(rules, encoder, cross, dense_model=name, cache=tmp_path)
    assert np.allclose(again.dense.vectors, searcher.dense.vectors)


def test_embeddings_are_unit_length(models, rules, tmp_path):
    name, encoder, _ = models
    searcher = Searcher(rules, encoder, None, dense_model=name, cache=tmp_path)
    assert np.allclose(np.linalg.norm(searcher.dense.vectors, axis=1), 1, atol=1e-5)


def test_evaluation_end_to_end(models, rules, tmp_path):
    name, encoder, cross = models
    searcher = Searcher(rules, encoder, cross, dense_model=name, cache=tmp_path)
    qs = [Question(id="q001", question="cancel within how many days?", category="number",
                   book="DISP", gold=["DISP 1.2.1"], key_facts=["14"], split="dev")]
    report = score(qs, searcher, ["bm25", "dense", "hybrid", "rerank@2"], depth=2)
    table = summary(report)
    assert table["bm25"]["R@1"] == 1.0
    assert set(table) == {"bm25", "dense", "hybrid", "rerank@2"}
