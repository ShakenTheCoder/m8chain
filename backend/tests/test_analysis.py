from pathlib import Path
from unittest.mock import Mock
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend import pipeline, classifier
from backend.models import Analysis, AnalyzeRequest, Features, Language, Segment, Transcript

URL = "https://www.tiktok.com/@example/video/1234567890123456789"


@pytest.fixture
def settings():
    return pipeline.Settings("test-secret", "clockworks/tiktok-scraper", .10, "base", "convaiinnovations/laya-multilingual", "cpu", .60,
                             vision_enabled=False, retain_source=False)


@pytest.fixture
def item():
    return {"id": "1234567890123456789", "webVideoUrl": URL, "text": "Save this #skincare",
            "authorMeta": {"id": "123"}, "videoMeta": {"duration": 24},
            "playCount": 10000, "diggCount": 800, "shareCount": None,
            "hashtags": [{"name": "Skincare"}, {"name": "skincare"}], "musicMeta": {"musicId": "0"}}


@pytest.mark.parametrize("url", ["https://evil.test/video/123", "https://tiktok.com.evil.test/@x/video/123",
    "http://www.tiktok.com/@x/video/123", "https://www.tiktok.com/@x", "https://user@www.tiktok.com/@x/video/123",
    "https://www.tiktok.com:444/@x/video/123", "https://vm.tiktok.com/"])
def test_reject_non_video_urls(url):
    with pytest.raises(ValidationError):
        AnalyzeRequest(url=url)


def test_normalize_url_and_short_links():
    assert AnalyzeRequest(url=URL + "?tracking=remove#fragment").url == URL
    assert AnalyzeRequest(url="https://vm.tiktok.com/ZExample/").url == "https://vm.tiktok.com/ZExample"


def test_counters_and_sound_absence_are_not_invented(settings, item):
    record = pipeline.normalize(item, "run-1", URL, settings)
    assert record.observation.likes == 800
    assert record.observation.like_rate == .08
    assert record.observation.shares is None
    assert record.observation.share_rate is None
    assert record.elements.sound.id is None
    assert record.elements.hashtags == ["skincare"]
    assert pipeline.ratio(0, 100) == 0
    assert pipeline.ratio(10, 0) is None


def test_mismatched_video_rejected(settings, item):
    with pytest.raises(pipeline.AnalysisError, match="does not match"):
        pipeline.normalize(item, "run-1", URL.replace("1234567890123456789", "999"), settings)


@pytest.mark.parametrize("language,confidence,expected", [("ro", .97, "complete"), ("en", .98, "complete"), ("fr", .95, "unsupported_language"), ("ro", .40, "partial"), (None, None, "partial")])
def test_language_gate(settings, item, monkeypatch, language, confidence, expected):
    monkeypatch.setattr(pipeline, "collect", lambda *_: (item, "run-1"))
    monkeypatch.setattr(pipeline, "download_media", lambda *_: None)
    transcript = Transcript(status="complete", language=language, text="Spoken content", segments=[Segment(start_seconds=0, end_seconds=2, text="Spoken content")])
    detected = Language(code=language, confidence=confidence, source="audio" if language else "unavailable", supported=language in {"en", "ro"} if language else None)
    monkeypatch.setattr(pipeline, "transcribe", lambda *_: (transcript, detected))
    classify = Mock(return_value=(Features(), False))
    monkeypatch.setattr(pipeline, "classify", classify)
    result, _ = pipeline.analyze(URL, settings, lambda *_: None)
    # Counters are intentionally incomplete in the fixture.
    assert result.status == ("partial" if expected == "complete" else expected)
    assert classify.called == (language in {"en", "ro"} and confidence >= .70)
    if language == "fr":
        assert result.elements.transcript.text is None
    if language in {"ro", "en"} and confidence >= .70:
        assert result.classifier.status == "complete"
    assert Analysis.model_validate_json(result.model_dump_json()) == result


def test_classifier_abstains_on_uncertain_output(monkeypatch):
    answers = {}
    for key, question in classifier.QUESTIONS.items():
        labels = list(question["criteria"])
        answers[key] = {"choice": labels[0], "probabilities": {label: 1 / len(labels) for label in labels}}
    agent = Mock()
    agent.predict.return_value = {"answers": answers, "usage": {"truncated": True}}
    monkeypatch.setattr(classifier, "load_agent", lambda *_: agent)
    features, truncated = classifier.classify("Caption", "Text", "Text", "test", "cpu", .6)
    assert truncated
    assert features.topic.label == "unknown"
    assert features.topic.needs_review
    assert features.topic.probabilities


def test_api_configuration_schema_queue_and_persistence(monkeypatch, tmp_path, settings, item):
    from backend import main
    monkeypatch.setattr(main, "DATA", tmp_path)
    monkeypatch.setattr(main.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    with TestClient(main.app) as client:
        assert client.get("/health").json()["apify_configured"] is False
        assert client.post("/analyses", json={"url": URL}).status_code == 503
        assert client.post("/analyses", json={"url": "https://example.com"}).status_code == 422
        assert client.get("/schema").json()["title"] == "Analysis"
        assert client.get("/jobs/unknown").status_code == 404
        record = pipeline.normalize(item, "test-run", URL, settings)
        monkeypatch.setenv("APIFY_TOKEN", "test-secret")
        monkeypatch.setattr(main, "analyze", lambda *_: (record, item))
        response = client.post("/analyses", json={"url": URL})
        assert response.status_code == 202
        # Join only the submitted future before reading its persisted result.
        main.executor.submit(lambda: None).result(timeout=5)
        job = client.get("/jobs/" + response.json()["id"]).json()
        assert job["stage"] == "complete"
        assert job["result"]["video"]["id"] == item["id"]
        saved = client.get("/analyses/" + record.id)
        assert saved.json() == job["result"]
        assert "test-secret" not in saved.text


def test_committed_sample_matches_schema():
    sample = Path(__file__).resolve().parents[2] / "public" / "sample-output.json"
    assert Analysis.model_validate(json.loads(sample.read_text())).collection.run_id == "illustrative-sample"


def test_batch_collected_item_uses_same_pipeline_without_recollecting(settings, item, monkeypatch):
    collect = Mock(side_effect=AssertionError('Should reuse batch collection'))
    monkeypatch.setattr(pipeline, 'collect', collect)
    monkeypatch.setattr(pipeline, 'download_media', lambda *_: None)
    monkeypatch.setattr(pipeline, 'transcribe', lambda *_: (
        Transcript(status='complete', language='en', text='Looking for a man in finance'),
        Language(code='en', confidence=.98, source='audio', supported=True)))
    monkeypatch.setattr(pipeline, 'classify', lambda *_: (Features(), False))
    result, raw = pipeline.analyze_collected(item, 'real-batch-run', URL, settings, lambda *_: None)
    assert result.collection.run_id == 'real-batch-run'
    assert result.language.code == 'en'
    assert result.classifier.status == 'complete'
    assert raw == item
    collect.assert_not_called()
