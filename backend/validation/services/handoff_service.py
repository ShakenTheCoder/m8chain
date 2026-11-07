"""Handoff bundler & delivery service (`validation` -> `optimization`)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

import httpx

from ..config import EXPORTS_DIR, ValidationSettings, get_settings
from ..schemas.persona import PersonaProfile
from ..schemas.verdict_handoff import (
    HandoffDeliveryStatus,
    OptimizationHandoffBundle,
    OptimizationSeedHints,
    SelectedTrendBundle,
    ValidatedTrendView,
)


class OptimizationHandoffService:
    """Packages user-confirmed winning trend + niche + persona + verdict for Part 3 Optimization."""

    def __init__(self, settings: ValidationSettings | None = None) -> None:
        self.settings = settings or get_settings()
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    def create_and_deliver_bundle(
        self,
        validated_trend: ValidatedTrendView,
        persona: PersonaProfile,
        user_notes: str = "",
        override_webhook_url: str | None = None,
    ) -> OptimizationHandoffBundle:
        handoff_id = f"ho-{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        seed_hints = self._derive_seed_hints(validated_trend)
        selected_trend = SelectedTrendBundle(
            trend_id=validated_trend.trend_id,
            title=validated_trend.title,
            summary=validated_trend.summary,
            shared_elements=validated_trend.shared_elements,
            dominant_features=validated_trend.dominant_features,
            benchmark_metrics=validated_trend.benchmark_metrics,
            supporting_records=validated_trend.records,
        )

        bundle = OptimizationHandoffBundle(
            handoff_version="1.0",
            handoff_id=handoff_id,
            confirmed_at=now_iso,
            source_branch="validation",
            target_branch="optimization",
            persona=persona,
            niche=validated_trend.matched_niche,
            selected_trend=selected_trend,
            suitability_verdict=validated_trend.suitability_verdict,
            laya_decision_trace=validated_trend.laya_trace,
            optimization_seed_hints=seed_hints,
            user_notes=user_notes.strip(),
        )

        # Persist bundle to `exports/latest_handoff.json` and `exports/{handoff_id}.json`
        archive_path: Path = EXPORTS_DIR / f"{handoff_id}.json"
        latest_path: Path = EXPORTS_DIR / "latest_handoff.json"

        target_url = (override_webhook_url or self.settings.optimization_ingest_url or "").strip() or None
        delivery = HandoffDeliveryStatus(
            persisted_path=str(latest_path),
            webhook_configured=bool(target_url),
            webhook_url=target_url,
        )

        if target_url:
            try:
                with httpx.Client(timeout=6.0) as client:
                    resp = client.post(
                        target_url,
                        json=bundle.model_dump(mode="json", exclude={"delivery"}),
                    )
                    delivery.webhook_status_code = resp.status_code
                    delivery.webhook_forwarded = 200 <= resp.status_code < 300
                    delivery.webhook_message = (
                        f"Delivered to Optimization endpoint ({resp.status_code})."
                        if delivery.webhook_forwarded
                        else f"Optimization endpoint returned HTTP {resp.status_code}; bundle safely persisted locally."
                    )
            except Exception as exc:
                delivery.webhook_forwarded = False
                delivery.webhook_message = (
                    f"Optimization endpoint unreachable ({type(exc).__name__}); bundle persisted locally and ready via GET /api/validation/handoffs/latest."
                )

        bundle.delivery = delivery
        serialized = bundle.model_dump_json(indent=2)
        archive_path.write_text(serialized, encoding="utf-8")
        latest_path.write_text(serialized, encoding="utf-8")
        return bundle

    def _derive_seed_hints(self, view: ValidatedTrendView) -> OptimizationSeedHints:
        usable = [r for r in view.records if r.status != "unsupported_language"] or view.records
        durations = [int(round(r.video.duration_seconds)) for r in usable if r.video.duration_seconds > 0]
        min_d = max(10, min(durations) - 3) if durations else 15
        max_d = min(90, max(durations) + 5) if durations else 42

        openings = [
            r.features.opening_text.strip()
            for r in usable
            if r.features.opening_text and r.features.opening_text.strip()
        ]
        if not openings:
            openings = [
                f"[{view.dominant_features.hook_type}] Stop scrolling if you care about {view.dominant_features.topic}..."
            ]

        score = view.suitability_verdict.overall_score
        if score >= 80 and view.suitability_verdict.fit_status == "strong_fit":
            posture = "aggressive_scale"
            pop_size = 16
        elif score >= 58:
            posture = "controlled_test"
            pop_size = 12
        else:
            posture = "micro_experiment"
            pop_size = 8

        return OptimizationSeedHints(
            recommended_hook_type=view.dominant_features.hook_type,
            recommended_format=view.dominant_features.format,
            recommended_cta=view.dominant_features.call_to_action,
            seed_hashtags=view.dominant_features.common_hashtags[:6],
            opening_hook_templates=list(dict.fromkeys(openings))[:4],
            target_duration_seconds_range=(min_d, max(min_d + 8, max_d)),
            budget_allocation_posture=posture,  # type: ignore[arg-type]
            suggested_initial_population_size=pop_size,
        )
