"""Stand-ins for the two models, so search can be tested without downloading anything.

FakeEncoder turns a text into counts of its words, folded into 64 numbers.
FakeCrossEncoder scores a pair by how many words the two texts share. Both
take the same arguments as the sentence-transformers classes they replace.
"""

import zlib

import numpy as np

from rulecite.search import tokenize


class FakeEncoder:
    dim = 64

    def __init__(self):
        self.calls = 0

    def encode(self, inputs, prompt=None, batch_size=32, show_progress_bar=None,
               convert_to_numpy=True, normalize_embeddings=False):
        self.calls += 1
        out = np.zeros((len(inputs), self.dim), dtype=np.float32)
        for i, text in enumerate(inputs):
            for word in tokenize(text):
                out[i, zlib.crc32(word.encode()) % self.dim] += 1
        if normalize_embeddings:
            norms = np.linalg.norm(out, axis=1, keepdims=True)
            out = out / np.where(norms == 0, 1, norms)
        return out


class FakeCrossEncoder:
    def predict(self, inputs, batch_size=32, show_progress_bar=None, convert_to_numpy=True):
        return np.array([len(set(tokenize(q)) & set(tokenize(p))) for q, p in inputs],
                        dtype=float)
