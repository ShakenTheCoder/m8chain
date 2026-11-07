"""Unit tests use deterministic vectors; real model checks run separately without this fixture."""
from hashlib import sha256
import re
import unicodedata

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def controlled_semantic_vectors(monkeypatch):
    from backend import trends

    def encode(texts):
        result = {}
        for text in texts:
            folded = "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))
            vector = np.zeros(4096, dtype=np.float32)
            for word in set(re.findall(r"[^\W_]+", folded)):
                vector[int.from_bytes(sha256(word.encode()).digest()[:4], "little") % len(vector)] = 1
            norm = np.linalg.norm(vector)
            if norm:
                vector /= norm
            result[text] = vector
        return result

    monkeypatch.setattr(trends, "embed_texts", encode)
