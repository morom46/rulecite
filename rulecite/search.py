"""Search the rules four ways: by keywords, by meaning, both combined, and re-ranked.

* **Keyword search (BM25)** scores a provision by the question's words it
  contains, giving more weight to rare words and less to long provisions.
* **Meaning search (dense)** turns the question and every provision into
  vectors with a small sentence-embedding model and compares their directions,
  so "cancel my account" can match "right to cancel" without sharing words.
* **Hybrid** merges the two rankings with reciprocal rank fusion.
* **Re-ranking** reads the question and each of the top hybrid results together
  with a cross-encoder, which is slower but more exact, and reorders them.

The two models are downloaded once (about 220 MB) and run on the CPU.

    python -m rulecite.search "How long do I have to cancel a savings account?"
    python -m rulecite.search --method bm25 "complaint time limit"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import textwrap
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import snowballstemmer

from .records import Rule, load_rules
from .testset import RULES, normalise

DENSE_MODEL = "BAAI/bge-small-en-v1.5"
RERANKER = "cross-encoder/ms-marco-MiniLM-L6-v2"
# bge models are trained to put this before a short query that looks for longer passages.
QUERY_PROMPT = "Represent this sentence for searching relevant passages: "
CACHE = Path("data/processed/cache")

CHUNK_WORDS = 200     # long provisions are embedded in pieces this long,
CHUNK_OVERLAP = 50    # each sharing this many words with the piece before
RRF_K = 60            # the usual constant for reciprocal rank fusion
METHODS = ("bm25", "dense", "hybrid", "rerank")

STOPWORDS = frozenset("""a about above after again against all also am an and any are as at be
because been before being below between both but by can could did do does doing down during
each few for from further had has have having he her here hers him his how i if in into is it
its itself just me more most my no nor not now of off on once only or other our out over own
s same she should so some such than that the their them then there these they this those
through to too under until up very was we were what when where which while who whom why will
with would you your""".split())

_TOKEN = re.compile(r"£?[a-z0-9]+(?:[.,][0-9]+)*")
_stemmer = snowballstemmer.stemmer("english")


def tokenize(text: str) -> list[str]:
    """Lower-case words with common words dropped and endings removed.

    Stemming makes "cancel", "cancelled" and "cancellation" the same word.
    Amounts and numbers stay whole.

    >>> tokenize("The customer's right to cancel within 14 days, up to £350,000.")
    ['custom', 'right', 'cancel', 'within', '14', 'day', '£350,000']
    """
    words = [w for w in _TOKEN.findall(normalise(text)) if w not in STOPWORDS]
    return _stemmer.stemWords(words)


def header(rule: Rule) -> str:
    """The citation and headings, put in front of every piece of a provision."""
    parts = [rule.citation, rule.section_title]
    if rule.heading and rule.heading != rule.section_title:
        parts.append(rule.heading)
    return " · ".join(p for p in parts if p)


def passage(rule: Rule) -> str:
    return header(rule) + "\n" + rule.text


def chunks(rule: Rule, size: int = CHUNK_WORDS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """The provision as one passage, or as overlapping pieces if it is long.

    The embedding model reads at most about 400 words, so a long provision is cut
    into pieces and each piece keeps the provision's header.
    """
    words = rule.text.split()
    if len(words) <= size + overlap:
        return [passage(rule)]
    step = size - overlap
    starts = range(0, len(words) - overlap, step)
    return [header(rule) + "\n" + " ".join(words[s:s + size]) for s in starts]


# ---------------------------------------------------------------- keyword search

class BM25:
    """Okapi BM25 over tokenized documents.

    score(d, q) = sum over query words w of
        idf(w) * f(w, d) * (k1 + 1) / (f(w, d) + k1 * (1 - b + b * |d| / avgdl))
    where f(w, d) is how often w occurs in d, |d| is d's length in words and
    avgdl the average length. k1 limits how much repeating a word helps; b sets
    how much long documents are held back.
    """

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.length = np.array([len(d) for d in docs], dtype=float)
        self.avgdl = float(self.length.mean()) if self.n else 0.0
        self.postings: dict[str, list[tuple[int, int]]] = {}
        for i, doc in enumerate(docs):
            for word, count in Counter(doc).items():
                self.postings.setdefault(word, []).append((i, count))
        # The +1 inside the log keeps idf above zero even for words in most documents.
        self.idf = {w: math.log(1 + (self.n - len(p) + 0.5) / (len(p) + 0.5))
                    for w, p in self.postings.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        out = np.zeros(self.n)
        for word in set(query):
            for i, f in self.postings.get(word, ()):
                norm = 1 - self.b + self.b * self.length[i] / self.avgdl
                out[i] += self.idf[word] * f * (self.k1 + 1) / (f + self.k1 * norm)
        return out


# ---------------------------------------------------------------- meaning search

class Encoder(Protocol):
    """What we need from a sentence-transformers model (tests use a fake one)."""

    def encode(self, inputs, prompt=None, batch_size=32, show_progress_bar=None,
               convert_to_numpy=True, normalize_embeddings=False): ...


class DenseIndex:
    """Embeddings of every provision, or of every piece of a long one.

    A provision's score is the best score of any of its pieces. The embeddings
    are saved in data/processed/cache, so they are only computed once for a
    given model and set of rules.
    """

    def __init__(self, rules: list[Rule], encoder: Encoder, model_name: str,
                 cache: Path | None = CACHE):
        self.encoder = encoder
        self.texts: list[str] = []
        owner = []
        for i, rule in enumerate(rules):
            pieces = chunks(rule)
            self.texts += pieces
            owner += [i] * len(pieces)
        self.owner = np.array(owner)
        self.starts = np.flatnonzero(np.r_[True, self.owner[1:] != self.owner[:-1]])
        self.vectors = self._load_or_encode(model_name, cache)

    def _load_or_encode(self, model_name: str, cache: Path | None) -> np.ndarray:
        key = hashlib.sha256("\n\0".join([model_name, *self.texts]).encode()).hexdigest()[:16]
        path = None
        if cache is not None:
            slug = re.sub(r"[^A-Za-z0-9.-]+", "-", model_name)
            path = cache / f"dense-{slug}-{key}.npy"
            if path.exists():
                return np.load(path)
        vectors = np.asarray(self.encoder.encode(
            self.texts, batch_size=32, show_progress_bar=len(self.texts) > 100,
            convert_to_numpy=True, normalize_embeddings=True), dtype=np.float32)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, vectors)
        return vectors

    def encode_queries(self, queries: list[str]) -> np.ndarray:
        return np.asarray(self.encoder.encode(
            queries, prompt=QUERY_PROMPT, batch_size=32, show_progress_bar=False,
            convert_to_numpy=True, normalize_embeddings=True), dtype=np.float32)

    def scores(self, query_vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Each provision's best cosine similarity, and which piece gave it."""
        sims = self.vectors @ query_vector
        best = np.maximum.reduceat(sims, self.starts)
        piece = self.starts.copy()
        for r, start in enumerate(self.starts):
            end = self.starts[r + 1] if r + 1 < len(self.starts) else len(sims)
            if end - start > 1:
                piece[r] = start + int(np.argmax(sims[start:end]))
        return best, piece


# ---------------------------------------------------------------- combining and re-ranking

def order(scores: np.ndarray) -> np.ndarray:
    """Indexes from best to worst score; equal scores keep the file order."""
    return np.argsort(-scores, kind="stable")


def rrf(rankings: list[np.ndarray], n: int, k: int = RRF_K) -> np.ndarray:
    """Reciprocal rank fusion: each ranking gives a document 1 / (k + its rank).

    A document near the top of either list ends up near the top of the merged
    one, and no score needs to be put on the same scale as another.

    >>> rrf([np.array([0, 1, 2]), np.array([2, 0, 1])], 3, k=1).round(3).tolist()
    [0.833, 0.583, 0.75]
    """
    fused = np.zeros(n)
    for ranking in rankings:
        fused[ranking] += 1.0 / (k + np.arange(1, len(ranking) + 1))
    return fused


class CrossScorer(Protocol):
    """What we need from a sentence-transformers CrossEncoder (tests use a fake one)."""

    def predict(self, inputs, batch_size=32, show_progress_bar=None, convert_to_numpy=True): ...


@dataclass
class Hit:
    id: str
    score: float


@dataclass
class Result:
    """Every method's ranking for one question, as indexes into the rule list."""

    bm25: np.ndarray
    dense: np.ndarray | None = None
    hybrid: np.ndarray | None = None
    rerank_scores: np.ndarray | None = None  # cross-encoder scores of hybrid[:len(rerank_scores)]
    bm25_scores: np.ndarray | None = None
    dense_scores: np.ndarray | None = None

    def rerank(self, depth: int) -> np.ndarray:
        """Hybrid, with its top `depth` results reordered by the cross-encoder."""
        top = self.hybrid[:depth]
        reordered = top[order(self.rerank_scores[:depth])]
        return np.concatenate([reordered, self.hybrid[depth:]])

    def ranking(self, method: str) -> np.ndarray:
        if method.startswith("rerank@"):
            return self.rerank(int(method.split("@")[1]))
        return getattr(self, method)

    def top_score(self, method: str) -> float | None:
        """How sure each method is about its first result (used for refusing in milestone 4)."""
        if method == "bm25":
            return float(self.bm25_scores[self.bm25[0]])
        if method == "dense" and self.dense_scores is not None:
            return float(self.dense_scores[self.dense[0]])
        if method.startswith("rerank@") and self.rerank_scores is not None:
            depth = int(method.split("@")[1])
            return float(self.rerank_scores[:depth].max())
        return None


class Searcher:
    def __init__(self, rules: list[Rule], encoder: Encoder | None = None,
                 cross: CrossScorer | None = None, dense_model: str = DENSE_MODEL,
                 cache: Path | None = CACHE):
        self.rules = rules
        self.bm25 = BM25([tokenize(passage(r)) for r in rules])
        self.dense = DenseIndex(rules, encoder, dense_model, cache) if encoder else None
        self.cross = cross

    def run(self, questions: list[str], depth: int = 50) -> list[Result]:
        """Rank all provisions for each question with every method available."""
        results = []
        vectors = self.dense.encode_queries(questions) if self.dense else None
        for i, question in enumerate(questions):
            bm25_scores = self.bm25.scores(tokenize(question))
            res = Result(bm25=order(bm25_scores), bm25_scores=bm25_scores)
            if self.dense is not None:
                dense_scores, piece = self.dense.scores(vectors[i])
                res.dense, res.dense_scores = order(dense_scores), dense_scores
                res.hybrid = order(rrf([res.bm25, res.dense], len(self.rules)))
                if self.cross is not None and depth > 0:
                    top = res.hybrid[:depth]
                    pairs = [(question, self.dense.texts[piece[r]]) for r in top]
                    res.rerank_scores = np.asarray(self.cross.predict(
                        pairs, batch_size=32, show_progress_bar=False, convert_to_numpy=True),
                        dtype=float).reshape(-1)
            results.append(res)
        return results

    def search(self, question: str, method: str = "rerank@20", k: int = 5) -> list[Hit]:
        res = self.run([question], depth=int(method.split("@")[1]) if "@" in method else 0)[0]
        ranking = res.ranking(method)
        scores = {"bm25": res.bm25_scores, "dense": res.dense_scores}.get(method)
        hits = []
        for pos, r in enumerate(ranking[:k]):
            if scores is not None:
                score = scores[r]
            elif method.startswith("rerank@") and pos < len(res.rerank_scores):
                score = float(np.sort(res.rerank_scores[:int(method.split('@')[1])])[::-1][pos])
            else:
                score = 1.0 / (RRF_K + pos + 1)
            hits.append(Hit(self.rules[r].id, float(score)))
        return hits


def load_models(dense_model: str = DENSE_MODEL, reranker: str = RERANKER):
    """Load (downloading the first time) the embedding model and the cross-encoder."""
    from sentence_transformers import CrossEncoder, SentenceTransformer

    encoder = SentenceTransformer(dense_model, device="cpu")
    cross = CrossEncoder(reranker, device="cpu", max_length=512) if reranker else None
    return encoder, cross


def default_method(choice: Path = Path("results/search-choice.json")) -> str:
    """Re-ranking at the depth the dev run chose, or 20 before there is one."""
    if choice.exists():
        return f"rerank@{json.loads(choice.read_text())['rerank_depth']}"
    return "rerank@20"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("question")
    ap.add_argument("--method", default=default_method(),
                    help="bm25, dense, hybrid or rerank@N (default: rerank at the depth "
                         "chosen on dev, or 20)")
    ap.add_argument("-k", type=int, default=5, help="how many results to show")
    ap.add_argument("--rules", type=Path, default=RULES)
    ap.add_argument("--dense-model", default=DENSE_MODEL)
    ap.add_argument("--reranker", default=RERANKER)
    args = ap.parse_args(argv)

    if not args.rules.exists():
        print(f"{args.rules} not found: run make ingest first.")
        return 1
    rules = load_rules(args.rules)
    encoder = cross = None
    if args.method != "bm25":
        encoder, cross = load_models(args.dense_model,
                                     args.reranker if args.method.startswith("rerank") else "")
    searcher = Searcher(rules, encoder, cross, args.dense_model)
    by_id = {r.id: r for r in rules}
    for n, hit in enumerate(searcher.search(args.question, args.method, args.k), 1):
        rule = by_id[hit.id]
        print(f"\n{n}. {rule.citation}  ({hit.score:.3f})  {rule.section_title}")
        print(textwrap.fill(rule.text[:400] + (" ..." if len(rule.text) > 400 else ""),
                            88, initial_indent="   ", subsequent_indent="   "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
