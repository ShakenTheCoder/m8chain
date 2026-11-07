"""FastAPI entry point for n8chain Part 2: Validation (`validation` branch)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import create_validation_router
from .config import ValidationSettings, get_settings
from .services.store import ValidationWorkspaceStore


def create_app(settings: ValidationSettings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    store = ValidationWorkspaceStore(cfg)

    app = FastAPI(
        title="n8chain — Part 2: Validation API",
        version="1.0.0",
        description=(
            "Ingests Organ Trend Description JSON + schema v1.2 video records, classifies and "
            "synthesizes hybrid niches via convaiinnovations/laya (ModernBERT-large, 512 ctx, EN), "
            "evaluates Content Creator & Business suitability verdicts, and exports confirmed "
            "winning trend bundles to Part 3 Optimization."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.validation_store = store
    app.include_router(create_validation_router(store))
    return app


app = create_app()
