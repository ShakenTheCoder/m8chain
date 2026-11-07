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


@pytest.fixture(autouse=True)
def controlled_concept_reviewer(monkeypatch, request):
    """Storage/API tests exercise real caching with a deterministic model boundary."""
    if request.node.name.startswith('test_model_failure'):
        return
    import json
    from collections import defaultdict
    from backend import llm_trends

    def review(messages, config):
        # Audit returns the draft unchanged; dedicated tests exercise rejection.
        if messages[-1]['role'] == 'user' and len(messages) > 2:
            return llm_trends.Review.model_validate_json(messages[-2]['content'])
        facts = json.loads(messages[1]['content'].split('\n', 1)[1])
        groups = defaultdict(list)
        for fact in facts:
            if fact['script']:
                groups[fact['script']].append(fact['clip'])
        trends = []
        for script, ids in groups.items():
            if len(ids) < 2:
                continue
            trends.append(llm_trends.Proposal(title='Repeated creative setup', concept='A shared creative setup repeated with a recognizable payoff.',
                defining_pattern='Repeat the spoken setup and adapt the contextual payoff.', cohesion='high',
                members=[llm_trends.Support(clip=key, field='script', quote=script, explanation='The source repeats the defining spoken setup.') for key in ids],
                execution_guide={'specific_to_trend':['Preserve the spoken setup'], 'steps':['Introduce the setup', 'Adapt its payoff', 'Check the result'],
                                 'can_adapt':['Setting'], 'review_before_posting':['Check context']}))
        return llm_trends.Review(trends=trends)
    monkeypatch.setattr(llm_trends, 'ask_model', review)
