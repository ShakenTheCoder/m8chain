from unittest.mock import Mock

import pytest
from backend import pipeline, vision
from backend.models import Analysis, Classifier, Collection, Elements, Language, Observation, Segment, Transcript, VisualAnalysis
from backend.text_elements import describe_evidence, numeric_expressions, retain_text_elements, sequence


def record():
    return Analysis(id="test-record", video={"id": "123", "url": "https://www.tiktok.com/@x/video/123"},
                    collection=Collection(run_id="run", collected_at="2026-11-07T12:00:00Z"),
                    elements=Elements(), observation=Observation(observed_at="2026-11-07T12:00:00Z"),
                    classifier=Classifier(model="test", min_confidence=.6))


def test_preserve_romanian_diacritics_profanity_and_word_variants():
    original = "Școala pulii! Jobul pulii!"
    item = sequence(original, "transcript", 1.0, 3.0)
    assert item.text == original
    assert item.normalized == "școala pulii! jobul pulii!"
    assert item.folded == "scoala pulii! jobul pulii!"
    assert item.tokens == ["școala", "pulii", "jobul", "pulii"]
    assert item.start_seconds == 1


@pytest.mark.parametrize("text,expected", [("six seven", "67"), ("6-7", "67"), ("67", "67"), ("șase șapte", "67"), ("two four", "24")])
def test_digit_aliases_are_generic_hints_with_original_text(text, expected):
    matches = numeric_expressions(sequence(text, "transcript", 2, 3))
    assert len(matches) == 1
    assert matches[0].compact_digits == expected
    assert matches[0].text == text
    assert matches[0].match_hint_only


def test_number_words_do_not_cross_sentence_boundaries():
    assert numeric_expressions(sequence("six. seven", "transcript")) == []
    assert numeric_expressions(sequence("o școală nouă", "transcript")) == []


def test_keep_utterance_times_and_do_not_invent_visuals():
    result = record()
    result.elements.transcript = Transcript(status="complete", language="ro", text="Școala pulii!", segments=[Segment(start_seconds=1, end_seconds=2, text="Școala pulii!")])
    retain_text_elements(result)
    describe_evidence(result)
    assert result.elements.text_sequences[0].start_seconds == 1
    assert result.description.sources == ["transcript"]
    assert "Școala pulii!" in result.description.text
    assert "room" not in result.description.text
    assert result.visual.summary is None
    assert result.visual.audio_delivery == "not_analyzed"


def test_frame_sample_is_bounded_ordered_and_has_dense_opening():
    assert vision.frame_times(120) == [0, .5, 1, 2, 3, 48, 84, 114]
    assert len(vision.frame_times(.05)) == 1
    assert vision.frame_times(2) == sorted(set(vision.frame_times(2)))
    with pytest.raises(vision.VisionError):
        vision.frame_times(121)


def test_visual_frame_times_are_observed_and_text_location_is_not_invented(monkeypatch, tmp_path):
    image = tmp_path / "frame.jpg"
    from PIL import Image
    Image.new("RGB", (32, 48), "white").save(image)
    monkeypatch.setattr(vision, "sample_frames", lambda *_: [(0, image), (2, image)])
    output = {"summary": "A person is visible near a doorway.", "text": "Școala pulii"}
    import json
    response = Mock(status_code=200)
    response.json.return_value = {"message": {"content": json.dumps(output)}}
    post = Mock(return_value=response)
    monkeypatch.setattr(vision.httpx, "post", post)
    result, text, _ = vision.describe_video(tmp_path / "video.mp4", "test", "http://localhost:11434", 3)
    assert [frame.timestamp_seconds for frame in result.frames] == [0, 2]
    assert result.actions == []
    assert result.action_localization == "not_analyzed"
    assert text.items[0].text == "Școala pulii"
    assert text.items[0].timestamp_seconds is None
    assert text.items[0].frame_index is None
    # The visual model receives no transcript that could prime it to hallucinate a scene.
    assert "Școala pulii" not in post.call_args.kwargs["json"]["messages"][-1]["content"]
    output["invented_field"] = "not part of the schema"
    response.json.return_value = {"message": {"content": json.dumps(output)}}
    with pytest.raises(vision.VisionError, match="ValidationError"):
        vision.describe_video(tmp_path / "video.mp4", "test", "http://localhost:11434", 3)
    response.json.return_value = {"done_reason": "length", "message": {"content": ""}}
    with pytest.raises(vision.VisionError, match="token limit"):
        vision.describe_video(tmp_path / "video.mp4", "test", "http://localhost:11434", 3)


def test_local_vision_schema_is_small_and_flat():
    import json
    assert "$ref" not in json.dumps(vision.response_schema())
    assert set(vision.response_schema()["required"]) == {"summary", "text"}


def test_retained_source_and_frames_have_replayable_paths(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    video = source_dir / "video.mp4"
    video.write_bytes(b"original-video-bytes")
    (source_dir / "frame-00.jpg").write_bytes(b"sampled-frame")
    settings = pipeline.Settings("", "", .1, "base", "test", "cpu", .6, evidence_dir=tmp_path / "evidence")
    result = record()
    result.visual = VisualAnalysis(status="complete", summary="Visible evidence", frames=[{"index": 0, "timestamp_seconds": 0, "description": "Frame description"}])
    pipeline.retain_media(result, video, settings)
    assert result.media_evidence.status == "retained"
    assert (settings.evidence_dir / result.media_evidence.video_path).read_bytes() == video.read_bytes()
    assert len(result.media_evidence.video_sha256) == 64
    assert (settings.evidence_dir / result.visual.frames[0].asset_path).read_bytes() == b"sampled-frame"


def test_music_only_video_still_gets_visual_description(monkeypatch, tmp_path):
    item = {"id": "123", "videoMeta": {"duration": 3}, "musicMeta": {"musicId": "456"}}
    settings = pipeline.Settings("test", "", .1, "base", "test", "cpu", .6, retain_source=False)
    monkeypatch.setattr(pipeline, "collect", lambda *_: (item, "run"))
    monkeypatch.setattr(pipeline, "download_media", lambda *_: None)
    monkeypatch.setattr(pipeline, "transcribe", lambda *_: (Transcript(status="complete", text=""), Language()))
    from backend.models import OnScreenText
    describe = Mock(return_value=(VisualAnalysis(status="complete", summary="A person holds up a sign."), OnScreenText(status="complete"), []))
    monkeypatch.setattr(pipeline, "describe_video", describe)
    result, _ = pipeline.analyze("https://www.tiktok.com/@x/video/123", settings, lambda *_: None)
    assert describe.called
    assert result.status == "partial"
    assert result.visual.status == "complete"
    assert result.classifier.status == "skipped"
    assert "A person holds up a sign." in result.description.text
    assert result.elements.sound.id == "456"
