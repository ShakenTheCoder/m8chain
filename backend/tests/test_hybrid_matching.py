from math import sqrt
from unittest.mock import Mock
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import trends
from backend.semantic import SemanticUnavailable
from backend.tests.test_trends import clip


def pair_with_meaning(monkeypatch, first, second, semantic_score):
    vectors = {first: np.array([1., 0.]), second: np.array([semantic_score, sqrt(1 - semantic_score ** 2)])}
    monkeypatch.setattr(trends, "embed_texts", lambda texts: {text: vectors[text] for text in texts})
    return trends.relationship(trends.prepare(clip(1, script=first)), trends.prepare(clip(2, script=second)))


def test_meaning_can_connect_paraphrases_with_no_shared_content_words(monkeypatch):
    left, right = "Someone enters the room", "A person walks through a doorway"
    score, evidence = pair_with_meaning(monkeypatch, left, right, .94)
    match = evidence[0]
    assert match.lexical_similarity == 0
    assert match.semantic_similarity == pytest.approx(.94)
    assert match.similarity == pytest.approx(.47)
    assert score == round(trends.WEIGHTS["script"] * .47, 4)
    assert match.basis == "meaning" and match.strength == "weak"
    guide = trends.guide(evidence)
    assert any("own words" in item for item in guide.steps)
    assert not any("Shared spoken script phrase" in item for item in guide.specific_to_trend)


def test_wording_and_meaning_have_equal_contributions(monkeypatch):
    _, evidence = pair_with_meaning(monkeypatch, "I love this bright school", "I hate this bright school", .1)
    match = evidence[0]
    assert match.lexical_similarity == pytest.approx(2 / 3)
    assert match.semantic_similarity == pytest.approx(.1)
    assert match.similarity == pytest.approx(.5 * (2 / 3) + .5 * .1)
    assert match.strength == "weak"


def test_unrelated_disjoint_text_does_not_connect(monkeypatch):
    _, evidence = pair_with_meaning(monkeypatch, "Someone enters the room", "Fresh bread bakes inside ovens", .12)
    assert evidence == []


def test_same_model_failure_is_not_silently_treated_as_word_only_matching(monkeypatch):
    monkeypatch.setattr(trends, "embed_texts", Mock(side_effect=SemanticUnavailable("Meaning model unavailable")))
    with pytest.raises(SemanticUnavailable):
        trends.extract_trends([clip(1, script="Here is my morning routine"), clip(2, script="Here is my morning routine")])


def test_hybrid_evidence_retains_exact_pairs_and_formula():
    records = [clip(index, script="A person enters the room through a doorway") for index in range(1, 4)]
    evidence = trends.extract_trends(records)["trends"][0]["evidence"]
    assert len(evidence) == 3
    for item in evidence:
        assert len(item["clip_ids"]) == 2
        assert item["similarity"] == pytest.approx(.5 * item["lexical_similarity"] + .5 * item["semantic_similarity"])


def test_api_reports_unavailable_meaning_model(monkeypatch, tmp_path):
    from backend import main
    from backend.storage import AnalysisStore
    monkeypatch.setattr(main, "DATA", tmp_path)
    with TestClient(main.app) as client:
        monkeypatch.setattr(AnalysisStore, "trend_snapshot", Mock(side_effect=SemanticUnavailable("Meaning model unavailable")))
        assert client.get("/trends").status_code == 503
        assert client.get("/graph").status_code == 503
