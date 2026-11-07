"""Runtime configuration for the n8chain Part 2 Validation backend."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
FIXTURES_PATH = BASE_DIR / "fixtures" / "mock_trends_v1_2.json"
EXPORTS_DIR = BASE_DIR / "exports"


@dataclass(slots=True)
class ValidationSettings:
    """Environment-driven settings for Laya model routing, hybrid niche thresholds, and handoff."""

    laya_model_id: str = field(
        default_factory=lambda: os.getenv("LAYA_MODEL_ID", "convaiinnovations/laya")
    )
    laya_backend: str = field(
        default_factory=lambda: os.getenv("LAYA_BACKEND", "auto").strip().lower()
    )
    laya_max_tokens: int = field(
        default_factory=lambda: int(os.getenv("LAYA_MAX_TOKENS", "512"))
    )
    laya_temperature: float = field(
        default_factory=lambda: float(os.getenv("LAYA_TEMPERATURE", "1.35"))
    )
    seed_niche_confidence_threshold: float = field(
        default_factory=lambda: float(os.getenv("SEED_NICHE_THRESHOLD", "0.52"))
    )
    hf_token: str | None = field(
        default_factory=lambda: os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
    )
    optimization_ingest_url: str | None = field(
        default_factory=lambda: os.getenv("OPTIMIZATION_INGEST_URL") or None
    )
    auto_seed_fixtures: bool = field(
        default_factory=lambda: os.getenv("AUTO_SEED_FIXTURES", "true").lower()
        in {"1", "true", "yes"}
    )


def get_settings() -> ValidationSettings:
    return ValidationSettings()
