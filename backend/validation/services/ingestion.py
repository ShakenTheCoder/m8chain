"""Ingestion & v1.2 schema validation service for Trend Description JSON from `organ`."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..schemas.organ_v1_2 import (
    OrganTrendDescription,
    OrganVideoRecordV1_2,
    TrendBenchmarkMetrics,
    TrendDominantFeatures,
)


class IngestionResult:
    def __init__(
        self,
        trends: list[OrganTrendDescription],
        warnings: dict[str, list[str]],
    ) -> None:
        self.trends = trends
        self.warnings = warnings


def parse_incoming_organ_payload(payload: Any) -> IngestionResult:
    """Accepts colleague's Trend Description JSON (single trend, `{trends: [...]}`, list of trends,
    or raw `v1.2` video records) and validates every embedded v1.2 record + status/limitations.
    """
    raw_trends: list[dict[str, Any]] = []

    if isinstance(payload, dict):
        if "trends" in payload and isinstance(payload["trends"], list):
            raw_trends = payload["trends"]
        elif _looks_like_single_v1_2_record(payload):
            rec = OrganVideoRecordV1_2.model_validate(payload)
            topic_slug = (rec.features.topic or "ungrouped").lower().replace(" ", "-")[:32]
            raw_trends = [
                {
                    "trend_id": f"trend-auto-{topic_slug}",
                    "title": rec.features.topic.title() if rec.features.topic else f"Trend ({rec.id})",
                    "summary": rec.description.text or rec.visual.summary,
                    "records": [payload],
                }
            ]
        else:
            raw_trends = [payload]
    elif isinstance(payload, list):
        if payload and all(isinstance(x, dict) and _looks_like_single_v1_2_record(x) for x in payload):
            grouped: dict[str, list[dict[str, Any]]] = {}
            for item in payload:
                rec = OrganVideoRecordV1_2.model_validate(item)
                key = (rec.features.topic or "general-trend").strip().lower()
                grouped.setdefault(key, []).append(item)
            for key, items in grouped.items():
                slug = key.replace(" ", "-")[:32]
                raw_trends.append(
                    {
                        "trend_id": f"trend-auto-{slug}",
                        "title": key.title(),
                        "summary": f"Auto-clustered from {len(items)} organ v1.2 record(s) sharing topic '{key}'.",
                        "records": items,
                    }
                )
        else:
            raw_trends = [x for x in payload if isinstance(x, dict)]
    else:
        raise ValueError("Payload must be a JSON object or array of trend descriptions / v1.2 records.")

    validated_trends: list[OrganTrendDescription] = []
    warnings_by_trend: dict[str, list[str]] = {}

    for raw_t in raw_trends:
        trend = OrganTrendDescription.model_validate(raw_t)
        trend_warnings: list[str] = []

        if not trend.records:
            trend_warnings.append("Trend contains 0 supporting v1.2 video records.")

        for rec in trend.records:
            if rec.analysis_version != "organ-mvp-2":
                trend_warnings.append(
                    f"Record '{rec.id}' uses analysis_version='{rec.analysis_version}' (expected 'organ-mvp-2')."
                )
            if rec.status == "partial":
                missing_parts: list[str] = []
                if rec.elements.transcript.status not in {"complete", "ok"} or not rec.elements.transcript.text:
                    missing_parts.append("transcript")
                if rec.visual.status not in {"complete", "ok"} or not rec.visual.summary:
                    missing_parts.append("visual_summary")
                if rec.elements.on_screen_text.status not in {"complete", "ok"}:
                    missing_parts.append("on_screen_text")
                detail = f" ({', '.join(missing_parts)})" if missing_parts else ""
                trend_warnings.append(
                    f"Record '{rec.id}' has status='partial'{detail}; weighted lower in suitability confidence."
                )
            elif rec.status == "unsupported_language":
                trend_warnings.append(
                    f"Record '{rec.id}' flagged status='unsupported_language' (detected '{rec.language.code}', "
                    f"confidence={rec.language.confidence:.2f}); excluded from English Laya semantic core."
                )

            if rec.classifier.input_truncated:
                trend_warnings.append(
                    f"Record '{rec.id}' had upstream organ classifier input truncated."
                )
            for lim in rec.limitations:
                trend_warnings.append(f"Record '{rec.id}' limitation: {lim}")

        if trend.dominant_features is None:
            trend.dominant_features = compute_dominant_features(trend)

        validated_trends.append(trend)
        warnings_by_trend[trend.trend_id] = trend_warnings

    return IngestionResult(trends=validated_trends, warnings=warnings_by_trend)


def _looks_like_single_v1_2_record(obj: dict[str, Any]) -> bool:
    return "schema_version" in obj and "video" in obj and "records" not in obj and "videos" not in obj


def compute_dominant_features(trend: OrganTrendDescription) -> TrendDominantFeatures:
    usable = [r for r in trend.records if r.status != "unsupported_language"] or trend.records
    topics = Counter(r.features.topic.strip() for r in usable if r.features.topic.strip())
    hooks = Counter(r.features.hook_type.strip() for r in usable if r.features.hook_type.strip())
    formats = Counter(r.features.format.strip() for r in usable if r.features.format.strip())
    ctas = Counter(r.features.call_to_action.strip() for r in usable if r.features.call_to_action.strip())
    hashtags = Counter(
        h.lower().lstrip("#") for r in usable for h in r.elements.hashtags if h.strip()
    )
    sounds = Counter(
        f"{r.elements.sound.title} — {r.elements.sound.author}".strip(" —")
        for r in usable
        if r.elements.sound.title
    )

    return TrendDominantFeatures(
        topic=topics.most_common(1)[0][0] if topics else trend.title,
        hook_type=hooks.most_common(1)[0][0] if hooks else "direct_hook",
        format=formats.most_common(1)[0][0] if formats else "short_form_video",
        call_to_action=ctas.most_common(1)[0][0] if ctas else "none_detected",
        common_hashtags=[tag for tag, _ in hashtags.most_common(6)],
        sound_motif=sounds.most_common(1)[0][0] if sounds else "Original Audio",
    )


def compute_benchmark_metrics(trend: OrganTrendDescription) -> TrendBenchmarkMetrics:
    total = len(trend.records)
    complete_cnt = sum(1 for r in trend.records if r.status == "complete")
    partial_cnt = sum(1 for r in trend.records if r.status == "partial")
    unsup_cnt = sum(1 for r in trend.records if r.status == "unsupported_language")

    usable = [r for r in trend.records if r.status != "unsupported_language"] or trend.records
    n = len(usable) or 1
    total_views = sum(r.observation.views for r in usable)

    avg_save_rate = sum(
        (r.observation.saves / max(1, r.observation.views)) for r in usable
    ) / n
    avg_comment_rate = sum(
        (r.observation.comments / max(1, r.observation.views)) for r in usable
    ) / n

    return TrendBenchmarkMetrics(
        record_count=total,
        usable_record_count=len([r for r in trend.records if r.status != "unsupported_language"]),
        complete_count=complete_cnt,
        partial_count=partial_cnt,
        unsupported_language_count=unsup_cnt,
        total_views=total_views,
        avg_views=round(total_views / n, 1),
        avg_like_rate=round(sum(r.observation.like_rate for r in usable) / n, 4),
        avg_share_rate=round(sum(r.observation.share_rate for r in usable) / n, 4),
        avg_save_rate=round(avg_save_rate, 4),
        avg_comment_rate=round(avg_comment_rate, 4),
    )
