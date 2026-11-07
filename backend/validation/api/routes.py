"""REST API routes for Part 2 Validation."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from ..schemas.niche import NicheCluster, SeedNicheDefinition
from ..schemas.persona import PersonaProfile
from ..schemas.verdict_handoff import OptimizationHandoffBundle, ValidatedTrendView
from ..services.store import ValidationWorkspaceStore


class EvaluateRequest(BaseModel):
    persona: PersonaProfile


class HandoffConfirmRequest(BaseModel):
    trend_id: str
    persona: PersonaProfile | None = None
    user_notes: str = ""
    optimization_webhook_url: str | None = None


class CustomNicheRequest(BaseModel):
    name: str
    description: str
    keywords: list[str] = Field(default_factory=list)
    commercial_categories: list[str] = Field(default_factory=list)


def create_validation_router(store: ValidationWorkspaceStore) -> APIRouter:
    router = APIRouter(prefix="/api/validation", tags=["validation"])

    @router.get("/health")
    def health() -> dict[str, Any]:
        views, niches, persona = store.evaluate_workspace()
        return {
            "status": "ok",
            "service": "n8chain-validation",
            "branch_scope": "validation",
            "input_contract": "organ-schema-v1.2 (organ-mvp-2)",
            "laya_engine": store.classifier.runtime_status(),
            "trend_count": len(views),
            "niche_count": len(niches),
            "active_persona_type": persona.type,
            "confirmed_handoffs": len(store.list_handoffs()),
        }

    @router.get("/workspace")
    def get_workspace() -> dict[str, Any]:
        views, niches, persona = store.evaluate_workspace()
        return {
            "active_persona": persona,
            "persona_presets": store.get_persona_presets(),
            "laya_engine": store.classifier.runtime_status(),
            "niches": niches,
            "trends": views,
            "handoffs": store.list_handoffs(),
        }

    @router.post("/ingest")
    def ingest_organ_trends(
        payload: Any = Body(...),
        replace: bool = Query(default=False, description="Replace existing trends instead of merging"),
    ) -> dict[str, Any]:
        try:
            return store.ingest_payload(payload, replace=replace)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid Organ v1.2 payload: {exc}") from exc

    @router.post("/seed-fixtures")
    def reset_to_mock_fixtures(
        replace: bool = Query(default=True),
    ) -> dict[str, Any]:
        return store.seed_mock_fixtures(replace=replace)

    @router.get("/niches", response_model=list[NicheCluster])
    def list_niches() -> list[NicheCluster]:
        _, niches, _ = store.evaluate_workspace()
        return niches

    @router.post("/niches/custom", response_model=list[NicheCluster])
    def create_custom_niche(req: CustomNicheRequest) -> list[NicheCluster]:
        slug = "-".join(req.name.lower().split())[:32]
        niche_def = SeedNicheDefinition(
            niche_id=f"custom-{slug}",
            name=req.name.strip(),
            description=req.description.strip(),
            criteria_prompt=f"{req.name}: {req.description} ({', '.join(req.keywords)})",
            keywords=[k.strip().lower() for k in req.keywords if k.strip()],
            commercial_categories=req.commercial_categories or ["Custom Target Vertical"],
        )
        return store.add_custom_niche(niche_def)

    @router.get("/trends", response_model=list[ValidatedTrendView])
    def list_validated_trends() -> list[ValidatedTrendView]:
        views, _, _ = store.evaluate_workspace()
        return views

    @router.post("/evaluate")
    def evaluate_for_persona(req: EvaluateRequest) -> dict[str, Any]:
        views, niches, persona = store.evaluate_workspace(persona_override=req.persona)
        return {
            "active_persona": persona,
            "niches": niches,
            "trends": views,
        }

    @router.post("/handoff", response_model=OptimizationHandoffBundle)
    def confirm_handoff_to_optimization(req: HandoffConfirmRequest) -> OptimizationHandoffBundle:
        try:
            return store.confirm_handoff(
                trend_id=req.trend_id,
                persona_override=req.persona,
                user_notes=req.user_notes,
                override_webhook_url=req.optimization_webhook_url,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/handoffs", response_model=list[OptimizationHandoffBundle])
    def list_handoffs() -> list[OptimizationHandoffBundle]:
        return store.list_handoffs()

    @router.get("/handoffs/latest", response_model=OptimizationHandoffBundle)
    def get_latest_handoff() -> OptimizationHandoffBundle:
        items = store.list_handoffs()
        if not items:
            raise HTTPException(
                status_code=404,
                detail="No trend has been confirmed for Optimization handoff yet.",
            )
        return items[0]

    return router
