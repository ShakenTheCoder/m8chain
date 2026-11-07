"""In-memory validation state coordinator with automatic fixture seeding."""

from __future__ import annotations

import json
from threading import RLock
from typing import Any

from ..adapters.laya_classifier import LayaClassifierAdapter
from ..config import FIXTURES_PATH, ValidationSettings, get_settings
from ..schemas.niche import NicheCluster, SeedNicheDefinition
from ..schemas.organ_v1_2 import OrganTrendDescription
from ..schemas.persona import (
    DEFAULT_BUSINESS_PERSONA,
    DEFAULT_CREATOR_PERSONA,
    PersonaProfile,
)
from ..schemas.verdict_handoff import OptimizationHandoffBundle, ValidatedTrendView
from .handoff_service import OptimizationHandoffService
from .ingestion import (
    compute_benchmark_metrics,
    compute_dominant_features,
    parse_incoming_organ_payload,
)
from .niche_engine import HybridNicheEngine
from .verdict_engine import SuitabilityVerdictEngine


class ValidationWorkspaceStore:
    """Thread-safe workspace state for ingested Organ trends, hybrid niches, personas, and handoffs."""

    def __init__(self, settings: ValidationSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._lock = RLock()
        self.classifier = LayaClassifierAdapter(self.settings)
        self.niche_engine = HybridNicheEngine(self.classifier)
        self.verdict_engine = SuitabilityVerdictEngine()
        self.handoff_service = OptimizationHandoffService(self.settings)

        self._trends: dict[str, OrganTrendDescription] = {}
        self._warnings: dict[str, list[str]] = {}
        self._active_persona: PersonaProfile = DEFAULT_CREATOR_PERSONA.model_copy(deep=True)
        self._handoffs: list[OptimizationHandoffBundle] = []

        if self.settings.auto_seed_fixtures and FIXTURES_PATH.exists():
            self.seed_mock_fixtures(replace=True)

    @property
    def active_persona(self) -> PersonaProfile:
        with self._lock:
            return self._active_persona.model_copy(deep=True)

    def set_active_persona(self, persona: PersonaProfile) -> PersonaProfile:
        with self._lock:
            self._active_persona = persona.model_copy(deep=True)
            return self._active_persona

    def get_persona_presets(self) -> dict[str, PersonaProfile]:
        return {
            "content_creator": DEFAULT_CREATOR_PERSONA.model_copy(deep=True),
            "business": DEFAULT_BUSINESS_PERSONA.model_copy(deep=True),
        }

    def ingest_payload(self, payload: Any, replace: bool = False) -> dict[str, Any]:
        parsed = parse_incoming_organ_payload(payload)
        with self._lock:
            if replace:
                self._trends.clear()
                self._warnings.clear()
            for trend in parsed.trends:
                self._trends[trend.trend_id] = trend
                self._warnings[trend.trend_id] = parsed.warnings.get(trend.trend_id, [])

            views, niches = self._evaluate_locked(self._active_persona)
            return {
                "ingested_trend_count": len(parsed.trends),
                "total_trends_in_workspace": len(self._trends),
                "ingested_trend_ids": [t.trend_id for t in parsed.trends],
                "warnings": parsed.warnings,
                "niches": niches,
                "evaluated_trends": views,
            }

    def seed_mock_fixtures(self, replace: bool = True) -> dict[str, Any]:
        if not FIXTURES_PATH.exists():
            raise FileNotFoundError(f"Mock fixtures file missing at {FIXTURES_PATH}")
        raw = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
        return self.ingest_payload(raw, replace=replace)

    def add_custom_niche(self, niche: SeedNicheDefinition) -> list[NicheCluster]:
        with self._lock:
            self.classifier.add_custom_seed_niche(niche)
            _, niches = self._evaluate_locked(self._active_persona)
            return niches

    def evaluate_workspace(
        self, persona_override: PersonaProfile | None = None
    ) -> tuple[list[ValidatedTrendView], list[NicheCluster], PersonaProfile]:
        with self._lock:
            if persona_override is not None:
                self._active_persona = persona_override.model_copy(deep=True)
            persona = self._active_persona.model_copy(deep=True)
            views, niches = self._evaluate_locked(persona)
            return views, niches, persona

    def confirm_handoff(
        self,
        trend_id: str,
        persona_override: PersonaProfile | None = None,
        user_notes: str = "",
        override_webhook_url: str | None = None,
    ) -> OptimizationHandoffBundle:
        with self._lock:
            if trend_id not in self._trends:
                raise KeyError(f"Trend '{trend_id}' not found in Validation workspace.")
            persona = (
                persona_override.model_copy(deep=True)
                if persona_override is not None
                else self._active_persona.model_copy(deep=True)
            )
            self._active_persona = persona
            views, _ = self._evaluate_locked(persona)
            selected_view = next((v for v in views if v.trend_id == trend_id), None)
            if selected_view is None:
                raise KeyError(f"Trend '{trend_id}' could not be evaluated.")

            bundle = self.handoff_service.create_and_deliver_bundle(
                validated_trend=selected_view,
                persona=persona,
                user_notes=user_notes,
                override_webhook_url=override_webhook_url,
            )
            self._handoffs.insert(0, bundle)
            return bundle

    def list_handoffs(self) -> list[OptimizationHandoffBundle]:
        with self._lock:
            return list(self._handoffs)

    def _evaluate_locked(
        self, persona: PersonaProfile
    ) -> tuple[list[ValidatedTrendView], list[NicheCluster]]:
        trends = list(self._trends.values())
        trend_to_niche, trend_to_trace, niches = self.niche_engine.classify_and_cluster(trends)

        views: list[ValidatedTrendView] = []
        for trend in trends:
            dominant = trend.dominant_features or compute_dominant_features(trend)
            metrics = compute_benchmark_metrics(trend)
            niche = trend_to_niche[trend.trend_id]
            trace = trend_to_trace[trend.trend_id]
            verdict = self.verdict_engine.evaluate(
                trend=trend,
                niche=niche,
                laya_trace=trace,
                metrics=metrics,
                dominant=dominant,
                persona=persona,
            )
            views.append(
                ValidatedTrendView(
                    trend_id=trend.trend_id,
                    title=trend.title,
                    summary=trend.summary,
                    discovered_at=trend.discovered_at,
                    shared_elements=trend.shared_elements,
                    dominant_features=dominant,
                    benchmark_metrics=metrics,
                    matched_niche=niche,
                    laya_trace=trace,
                    suitability_verdict=verdict,
                    ingestion_warnings=self._warnings.get(trend.trend_id, []),
                    records=trend.records,
                )
            )

        views.sort(key=lambda v: v.suitability_verdict.overall_score, reverse=True)
        return views, niches
