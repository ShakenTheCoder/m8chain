"""Collect one post, transcribe its audio, then classify supported speech."""

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from uuid import uuid4
import logging
import hashlib
import os
import re
import shutil
import subprocess
import wave
import httpx

from .classifier import classify
from .models import Analysis, Classifier, Collection, Elements, Language, MediaEvidence, Observation, Segment, Sound, Transcript, Video, VisualAnalysis
from .text_elements import describe_evidence, retain_text_elements
from .vision import VisionError, describe_video

log = logging.getLogger(__name__)


class AnalysisError(Exception):
    """An actionable, safe-to-display pipeline failure."""


@dataclass(frozen=True)
class Settings:
    apify_token: str
    actor: str
    max_cost: float
    whisper_model: str
    laya_model: str
    device: str
    min_confidence: float
    vision_enabled: bool = True
    vision_model: str = "qwen3-vl:4b-instruct"
    vision_url: str = "http://127.0.0.1:11434"
    retain_source: bool = True
    evidence_dir: Path = Path(__file__).resolve().parent.parent / ".data" / "evidence"

    @classmethod
    def from_env(cls):
        whisper = os.getenv("WHISPER_MODEL", "small")
        if whisper.endswith(".en"):
            raise ValueError("WHISPER_MODEL must support Romanian; use base or small, not .en.")
        threshold = float(os.getenv("LAYA_MIN_CONFIDENCE", "0.60"))
        max_cost = float(os.getenv("APIFY_MAX_COST_USD", "0.50"))
        if not 0 <= threshold <= 1 or not 0 < max_cost <= 5:
            raise ValueError("Invalid confidence or Apify cost limit.")
        return cls(
            apify_token=os.getenv("APIFY_TOKEN", ""),
            actor=os.getenv("APIFY_ACTOR", "clockworks/tiktok-scraper"),
            max_cost=max_cost, whisper_model=whisper,
            laya_model=os.getenv("LAYA_MODEL", "convaiinnovations/laya-multilingual"),
            device=os.getenv("LAYA_DEVICE", "cpu"), min_confidence=threshold,
            vision_enabled=os.getenv("VISION_ENABLED", "true").lower() in {"true", "1", "yes"},
            vision_model=os.getenv("VISION_MODEL", "qwen3-vl:4b-instruct"),
            vision_url=os.getenv("VISION_API_URL", "http://127.0.0.1:11434"),
            retain_source=os.getenv("RETAIN_SOURCE_MEDIA", "true").lower() in {"true", "1", "yes"},
        )


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def count(value) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
        return number if number >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def ratio(numerator: int | None, denominator: int | None) -> float | None:
    return round(numerator / denominator, 6) if numerator is not None and denominator else None


def normalize(item: dict, run_id: str, submitted_url: str, settings: Settings) -> Analysis:
    video_id = str(item.get("id") or "")
    if not video_id.isdigit():
        raise AnalysisError("Apify did not return a valid video. Check that the post is public and available.")
    requested = re.search(r"/video/(\d+)", submitted_url)
    if requested and requested.group(1) != video_id:
        raise AnalysisError("The returned video does not match the submitted link.")
    if item.get("isSlideshow"):
        raise AnalysisError("This is a photo slideshow. Paste a TikTok video for this POC.")
    author = item.get("authorMeta") or {}
    meta = item.get("videoMeta") or {}
    music = item.get("musicMeta") or {}
    duration = meta.get("duration")
    if duration is not None:
        duration = float(duration)
        if not 0 < duration <= 120:
            raise AnalysisError("Choose a video up to 120 seconds long for this POC.")
    timestamp = now()
    views, likes, shares = (count(item.get(key)) for key in ("playCount", "diggCount", "shareCount"))
    hashtags = []
    for tag in item.get("hashtags") or []:
        name = tag.get("name") if isinstance(tag, dict) else str(tag)
        if name:
            hashtags.append(name.lstrip("#").casefold())
    original = music.get("musicOriginal")
    return Analysis(
        id=str(uuid4()),
        video=Video(id=video_id, url=item.get("webVideoUrl") or submitted_url,
                    creator_id=str(author["id"]) if author.get("id") else None,
                    published_at=item.get("createTimeISO"), duration_seconds=duration),
        collection=Collection(run_id=run_id, collected_at=timestamp, discovery_queries=[submitted_url]),
        elements=Elements(
            post_description=item.get("text") or None,
            hashtags=sorted(set(hashtags)),
            sound=Sound(id=str(music["musicId"]) if music.get("musicId") not in (None, "", "0", 0) else None,
                        title=music.get("musicName") or None, author=music.get("musicAuthor") or None,
                        is_original=original if isinstance(original, bool) else None)),
        observation=Observation(observed_at=timestamp, views=views, likes=likes, shares=shares,
                                comments=count(item.get("commentCount")), saves=count(item.get("collectCount")),
                                like_rate=ratio(likes, views), share_rate=ratio(shares, views)),
        classifier=Classifier(model=settings.laya_model, min_confidence=settings.min_confidence),
        limitations=["single_observation_no_trend_verdict"],
    )


def collect(url: str, settings: Settings) -> tuple[dict, str]:
    from apify_client import ApifyClient
    from apify_client.errors import ApifyApiError
    if settings.actor == "clockworks/tiktok-scraper" and settings.max_cost < .50:
        raise AnalysisError("Set APIFY_MAX_COST_USD to at least 0.50 in .env; this actor rejects lower spending caps. Restart the Python service afterward.")
    client = ApifyClient(settings.apify_token)
    try:
        run = client.actor(settings.actor).call(
            run_input={
                "postURLs": [url], "resultsPerPage": 1,
                "scrapeRelatedVideos": False, "shouldDownloadVideos": True,
                "shouldDownloadCovers": False, "shouldDownloadAvatars": False,
                "shouldDownloadMusicCovers": False, "shouldDownloadSlideshowImages": False,
                "downloadSubtitlesOptions": "NEVER_DOWNLOAD_SUBTITLES",
                "commentsPerPost": 0, "aiVideoDescription": False, "aiVideoSummary": False,
            },
            timeout_secs=180, wait_secs=200, max_total_charge_usd=Decimal(str(settings.max_cost)),
        )
        if not run or run.get("status") != "SUCCEEDED":
            raise AnalysisError("TikTok collection did not finish. Check the run in Apify Console before retrying.")
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items(limit=2))
        if len(items) != 1:
            raise AnalysisError("Apify did not return one video. Check that the post is public and try its full URL.")
        return items[0], run["id"]
    except AnalysisError:
        raise
    except ApifyApiError as error:
        # Only surface structured API errors, never a raw SDK request/response dump.
        message = str(error.message or "Apify rejected the request.") if error.type else "Apify rejected the request. Check the actor run in Apify Console."
        if settings.apify_token:
            message = message.replace(settings.apify_token, "[redacted]")
        message = re.sub(r"apify_api_[A-Za-z0-9_-]+", "[redacted]", message)
        message = re.sub(r"(?i)((?:token|api_key|apikey|authorization)=)[^&\s]+", r"\1[redacted]", message)
        raise AnalysisError(f"Apify request failed (HTTP {error.status_code}): {message[:600]}") from None
    except Exception:
        # SDK errors can contain credentials in URLs. Never return their text to a browser.
        raise AnalysisError("Apify collection failed. Check your token, remaining credit and actor run in Apify Console.") from None


def download_media(item: dict, path: Path, settings: Settings):
    urls = item.get("mediaUrls") or []
    if not urls:
        raise AnalysisError("Apify returned metadata without a downloaded video.")
    # Download only Actor-stored media. Never fetch arbitrary URLs supplied in a request.
    url = next((u for u in urls if isinstance(u, str) and
                urlsplit(u).scheme == "https" and urlsplit(u).hostname == "api.apify.com" and
                urlsplit(u).path.startswith("/v2/key-value-stores/")), None)
    if not url:
        raise AnalysisError("Apify did not return a supported stored video URL.")
    try:
        with httpx.stream("GET", url, headers={"Authorization": f"Bearer {settings.apify_token}"},
                          timeout=60, follow_redirects=False) as response:
            response.raise_for_status()
            total = 0
            with path.open("wb") as target:
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > 60 * 1024 * 1024:
                        raise AnalysisError("The downloaded video exceeds the 60 MB POC limit.")
                    target.write(chunk)
            if total == 0:
                raise AnalysisError("The downloaded video was empty.")
    except httpx.HTTPError:
        raise AnalysisError("The stored video could not be downloaded from Apify.") from None


@lru_cache(maxsize=1)
def load_whisper(model: str):
    from faster_whisper import WhisperModel
    return WhisperModel(model, device="cpu", compute_type="int8")


def transcribe(path: Path, model: str) -> tuple[Transcript, Language]:
    audio_path = path.with_suffix(".wav")
    try:
        process = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(path), "-t", "121",
             "-vn", "-ar", "16000", "-ac", "1", str(audio_path)],
            capture_output=True, timeout=45,
        )
    except FileNotFoundError:
        raise AnalysisError("Install ffmpeg to extract the video's audio.") from None
    except subprocess.TimeoutExpired:
        raise AnalysisError("Audio extraction timed out.") from None
    if process.returncode != 0:
        return Transcript(status="unavailable", model=model), Language()
    with wave.open(str(audio_path)) as audio:
        if audio.getnframes() / audio.getframerate() > 120:
            raise AnalysisError("Choose a video up to 120 seconds long for this POC.")
    engine = load_whisper(model)
    segments, info = engine.transcribe(str(audio_path), beam_size=3, vad_filter=True, condition_on_previous_text=False)
    extracted = [Segment(start_seconds=round(s.start, 3), end_seconds=round(s.end, 3), text=s.text.strip())
                 for s in segments if s.text.strip()]
    if not extracted:
        return Transcript(status="complete", model=model, text=""), Language()
    language = Language(code=info.language, confidence=info.language_probability,
                        source="audio", supported=info.language in {"en", "ro"})
    return Transcript(status="complete", model=model, language=info.language,
                      text=" ".join(s.text for s in extracted), segments=extracted), language


def retain_media(record: Analysis, path: Path, settings: Settings):
    if not settings.retain_source:
        record.limitations.append("source_media_not_retained")
        return
    destination = settings.evidence_dir / record.id
    try:
        destination.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(path, destination / "source.mp4")
        for frame in path.parent.glob("frame-*.jpg"):
            shutil.copyfile(frame, destination / frame.name)
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        record.media_evidence = MediaEvidence(status="retained", video_path=f"{record.id}/source.mp4", video_sha256=digest)
        for frame in record.visual.frames:
            record_path = destination / f"frame-{frame.index:02}.jpg"
            if record_path.exists():
                frame.asset_path = f"{record.id}/{record_path.name}"
    except OSError:
        record.limitations.append("source_media_retention_failed")


def analyze(url: str, settings: Settings, update) -> tuple[Analysis, dict]:
    update("collecting", "Collecting the TikTok post and video through Apify")
    item, run_id = collect(url, settings)
    return analyze_collected(item, run_id, url, settings, update)


def analyze_collected(item: dict, run_id: str, url: str, settings: Settings, update) -> tuple[Analysis, dict]:
    """Run the same analysis on a verified batch-collected item without recollection."""
    record = normalize(item, run_id, url, settings)
    with TemporaryDirectory(prefix="n8chain-") as directory:
        path = Path(directory) / "video.mp4"
        update("downloading", "Downloading the video for audio analysis")
        try:
            download_media(item, path, settings)
        except AnalysisError:
            record.limitations.append("video_download_unavailable")
            retain_text_elements(record)
            describe_evidence(record)
            return record, item
        update("transcribing", "Detecting speech language and transcribing audio; first use downloads the model")
        try:
            record.elements.transcript, record.language = transcribe(path, settings.whisper_model)
        except AnalysisError:
            raise
        except Exception:
            record.elements.transcript = Transcript(status="failed", model=settings.whisper_model)
            record.limitations.append("transcription_failed")
        if record.language.supported is False:
            record.status = "unsupported_language"
            record.limitations.append("supported_languages_are_english_and_romanian")
            record.elements.transcript = Transcript(status="skipped", model=settings.whisper_model, language=record.language.code)
            return record, item
        if settings.vision_enabled:
            update("describing", "Describing sampled frames and reading visible text with the local vision model")
            try:
                record.visual, record.elements.on_screen_text, _ = describe_video(
                    path, settings.vision_model, settings.vision_url, record.video.duration_seconds)
                record.limitations.extend(["sparse_frames_may_miss_brief_actions", "visual_descriptions_and_visible_text_are_model_inferences",
                                           "visible_text_not_localized_to_individual_frames", "visual_action_intervals_not_extracted"])
            except VisionError:
                record.visual = VisualAnalysis(status="failed", model=settings.vision_model)
                record.elements.on_screen_text.status = "failed"
                record.limitations.append("visual_description_failed_check_ollama_model")
        else:
            record.limitations.extend(["visual_description_disabled", "on_screen_text_not_analyzed"])
        retain_media(record, path, settings)
    retain_text_elements(record)
    describe_evidence(record)
    record.limitations.extend(["transcript_is_unverified_asr_output", "vocal_delivery_and_audio_fingerprints_not_analyzed"])
    if record.language.code is None:
        record.limitations.append("speech_language_unavailable")
        if record.elements.transcript.status == "unavailable":
            record.limitations.append("audio_stream_unavailable")
        return record, item
    if (record.language.confidence or 0) < 0.70:
        record.limitations.append("speech_language_uncertain_classification_skipped")
        return record, item
    update("classifying", "Classifying the text with multilingual Laya; first use downloads the model")
    transcript = record.elements.transcript
    first_text = next((s.text for s in transcript.segments if s.start_seconds < 5), "")
    opening = re.split(r"(?<=[.!?])\s+", first_text, maxsplit=1)[0] or None
    try:
        record.features, record.classifier.input_truncated = classify(
            record.elements.post_description, transcript.text or "", opening,
            settings.laya_model, settings.device, settings.min_confidence,
        )
        record.classifier.status = "complete"
        record.status = "complete" if record.visual.status == "complete" else "partial"
        record.limitations.append("laya_marketing_labels_not_domain_calibrated")
        if record.classifier.input_truncated:
            record.status = "partial"
            record.limitations.append("classifier_input_truncated")
        if "source_media_retention_failed" in record.limitations:
            record.status = "partial"
        if any(value is None for value in (record.observation.views, record.observation.likes,
                                           record.observation.shares, record.observation.comments, record.observation.saves)):
            record.status = "partial"
            record.limitations.append("some_engagement_counters_unavailable")
    except Exception:
        record.classifier.status = "failed"
        record.limitations.append("laya_classification_failed")
    return record, item
