"""Comprehensive test suite for n8chain Part 2: Validation (`validation` branch)."""

from __future__ import annotations

from backend.validation.schemas.niche import SeedNicheDefinition
from backend.validation.schemas.persona import (
    DEFAULT_BUSINESS_PERSONA,
    DEFAULT_CREATOR_PERSONA,
)
from backend.validation.services.store import ValidationWorkspaceStore


def test_seeded_fixtures_and_laya_runtime() -> None:
    store = ValidationWorkspaceStore()
    views, niches, persona = store.evaluate_workspace()

    assert persona.type == "content_creator"
    assert store.classifier.runtime_status()["model_id"] == "convaiinnovations/laya"
    assert len(views) == 5
    assert len(niches) >= 4


def test_hybrid_niche_seed_and_emergent_clustering() -> None:
    store = ValidationWorkspaceStore()
    _, niches, _ = store.evaluate_workspace()
    origins = {n.niche_id: n.origin for n in niches}

    assert "skincare-beauty-science" in origins
    assert origins["skincare-beauty-science"] == "seed_taxonomy"
    assert "ai-creator-productivity-saas" in origins

    emergent_niches = [n for n in niches if n.origin == "emergent_cluster"]
    assert len(emergent_niches) >= 1
    assert any("trend-pocket-thermal-journaling" in n.matched_trend_ids for n in emergent_niches)

    # Adding a custom user niche dynamically re-clusters matching trends into it!
    updated_niches = store.add_custom_niche(
        SeedNicheDefinition(
            niche_id="custom-stationery-journaling",
            name="Analog Stationery & Thermal Journaling",
            description="Pocket thermal printers, sticker paper, notebooks, and analog habit logs.",
            criteria_prompt="thermal printer, stationery, journaling, notebook, analog desk",
            keywords=["thermal", "printer", "journaling", "stationery", "notebook", "inkless"],
            commercial_categories=["Stationery", "Desk Gadgets"],
        )
    )
    custom_map = {n.niche_id: n for n in updated_niches}
    assert "custom-stationery-journaling" in custom_map
    assert "trend-pocket-thermal-journaling" in custom_map["custom-stationery-journaling"].matched_trend_ids


def test_status_handling_and_persona_switching() -> None:
    store = ValidationWorkspaceStore()

    creator_views, _, _ = store.evaluate_workspace(DEFAULT_CREATOR_PERSONA)
    creator_trends = {t.trend_id: t for t in creator_views}

    unsup = creator_trends["trend-unverified-miracle-drops-es"]
    assert unsup.suitability_verdict.fit_status == "disqualified"
    assert any("unsupported_language" in w for w in unsup.ingestion_warnings)

    skin = creator_trends["trend-skin-barrier-reset"]
    assert skin.benchmark_metrics.complete_count == 1
    assert skin.benchmark_metrics.partial_count == 1
    assert skin.suitability_verdict.fit_status in {"strong_fit", "conditional_fit"}

    biz_views, _, _ = store.evaluate_workspace(DEFAULT_BUSINESS_PERSONA)
    biz_trends = {t.trend_id: t for t in biz_views}

    ai_score = biz_trends["trend-ai-workflow-solostack"].suitability_verdict.overall_score
    hojicha_score = biz_trends["trend-hojicha-cloud-asmr"].suitability_verdict.overall_score
    assert ai_score > hojicha_score + 15.0


def test_colleague_trend_description_json_aliases_and_laya_512_truncation() -> None:
    store = ValidationWorkspaceStore()

    long_transcript = " ".join(["ceramide peptide hydration skin barrier routine"] * 220)
    colleague_payload = {
        "id": "colleague-trend-99",
        "name": "Colleague Organ Trend Payload",
        "description": "Testing flexible field aliases (id/name/description/videos) + 512-token Laya window.",
        "motifs": ["ceramide_mist", "hydration_meter"],
        "videos": [
            {
                "schema_version": "1.2",
                "analysis_version": "organ-mvp-2",
                "id": "col-vid-1",
                "status": "complete",
                "video": {
                    "platform": "tiktok",
                    "id": "tt-999",
                    "url": "https://tiktok.com/@test/video/999",
                    "creator_id": "tester",
                    "published_at": "2026-11-07T12:00:00Z",
                    "duration_seconds": 25,
                },
                "language": {
                    "code": "en",
                    "confidence": 0.99,
                    "source": "lid",
                    "supported": True,
                    "allowed": ["en"],
                },
                "elements": {
                    "post_description": "Ceramide mist test",
                    "hashtags": ["skincare", "ceramide"],
                    "transcript": {
                        "status": "complete",
                        "source": "whisper",
                        "model": "v3",
                        "language": "en",
                        "text": long_transcript,
                        "segments": [
                            {
                                "start_seconds": 0.0,
                                "end_seconds": 4.0,
                                "text": "Testing ceramide mist hydration levels.",
                            }
                        ],
                    },
                },
                "observation": {
                    "observed_at": "2026-11-07T12:30:00Z",
                    "views": 180000,
                    "likes": 21000,
                    "shares": 4500,
                    "comments": 400,
                    "saves": 6000,
                    "like_rate": 0.1166,
                    "share_rate": 0.025,
                },
                "features": {
                    "topic": "ceramide skin mist",
                    "hook_type": "before_after",
                    "format": "tutorial",
                    "call_to_action": "Shop mist link in bio",
                    "opening_text": "Testing ceramide mist hydration levels.",
                    "evidence_sources": ["transcript"],
                },
                "limitations": [],
            }
        ],
    }

    ingested = store.ingest_payload(colleague_payload)
    assert "colleague-trend-99" in ingested["ingested_trend_ids"]

    matched = next(
        t for t in ingested["evaluated_trends"] if t.trend_id == "colleague-trend-99"
    )
    assert matched.laya_trace.estimated_input_tokens <= 512
    assert matched.laya_trace.input_truncated is True
    assert matched.matched_niche.niche_id == "skincare-beauty-science"


def test_confirm_handoff_to_optimization() -> None:
    store = ValidationWorkspaceStore()

    bundle = store.confirm_handoff(
        trend_id="trend-skin-barrier-reset",
        user_notes="Prioritize 72-hour reset hook in initial GA post population.",
    )
    assert bundle.handoff_version == "1.0"
    assert bundle.source_branch == "validation"
    assert bundle.target_branch == "optimization"
    assert bundle.selected_trend.trend_id == "trend-skin-barrier-reset"
    assert len(bundle.selected_trend.supporting_records) == 2
    assert bundle.niche.niche_id == "skincare-beauty-science"
    assert bundle.persona.type == "content_creator"
    assert bundle.suitability_verdict.overall_score > 60.0
    assert bundle.optimization_seed_hints.suggested_initial_population_size >= 8
    assert store.list_handoffs()[0].handoff_id == bundle.handoff_id
