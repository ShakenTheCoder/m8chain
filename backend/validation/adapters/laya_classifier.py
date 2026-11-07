"""Adapter for `convaiinnovations/laya` (ModernBERT-large, 421M params, 512 context, English).

Reference: https://huggingface.co/convaiinnovations/laya
Laya is an open-weight non-autoregressive "System 1" decision model (Apache 2.0, open counterpart
to TypeSafe's Jev) that evaluates a compact text/JSON state against typed decision primitives:
  - `choice`: discrete classification with probability distribution
  - `score`: ordinal rubric evaluation
  - `noul`: calibrated yes/no probability P(true)

Because `convaiinnovations/laya` uses a 512-token English ModernBERT-large encoder and its model
card notes un-finetuned zero-shot predictions benefit from temperature calibration, this adapter:
  1. Packs trend + v1.2 record signals strictly inside the 512-token English window.
  2. Executes via `laya` SDK, Hugging Face `transformers`, HF Inference API (`HF_TOKEN`),
     or a calibrated deterministic System-1 fallback when local 421M weights are not present.
  3. Applies temperature scaling and triggers Hybrid Emergent Niche synthesis when max choice
     confidence falls below `seed_niche_confidence_threshold`.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

import httpx

from ..config import ValidationSettings, get_settings
from ..schemas.niche import LayaBackendStatus, LayaTypedDecisionTrace, SeedNicheDefinition
from ..schemas.organ_v1_2 import OrganTrendDescription, OrganVideoRecordV1_2


SEED_NICHE_TAXONOMY: list[SeedNicheDefinition] = [
    SeedNicheDefinition(
        niche_id="skincare-beauty-science",
        name="Skincare & Derm-Backed Beauty",
        description="Ingredient-led routines, skin barrier repair, SPF testing, and clinical before/after demos.",
        criteria_prompt="skincare routines, serums, barrier repair, dermatology tips, cosmetics, glow up demos",
        keywords=[
            "skincare",
            "skin",
            "barrier",
            "serum",
            "retinol",
            "spf",
            "sunscreen",
            "hydration",
            "moisturizer",
            "acne",
            "ceramide",
            "routine",
            "derm",
            "glow",
            "cleanser",
            "peptides",
        ],
        typical_hooks=["myth_bust", "before_after", "problem_solution", "derm_reaction"],
        typical_formats=["talking_head", "split_screen_demo", "tutorial", "get_ready_with_me"],
        commercial_categories=["DTC Beauty", "Cosmetics", "Personal Care", "Dermatology Clinics"],
    ),
    SeedNicheDefinition(
        niche_id="ai-creator-productivity-saas",
        name="AI Workflows & Creator SaaS",
        description="AI automation tools, solo-founder stacks, editing shortcuts, and B2B/prosumer productivity demos.",
        criteria_prompt="software tools, AI workflows, automation, SaaS product demos, productivity apps, coding or editing shortcuts",
        keywords=[
            "ai",
            "saas",
            "workflow",
            "automation",
            "productivity",
            "tool",
            "app",
            "prompt",
            "notion",
            "agent",
            "editing",
            "software",
            "founder",
            "template",
            "workspace",
            "pipeline",
        ],
        typical_hooks=["time_saved_shock", "screen_share_reveal", "stop_doing_this", "secret_tool"],
        typical_formats=["screen_recording", "split_screen_demo", "talking_head", "tutorial"],
        commercial_categories=["B2B SaaS", "Creator Tools", "EdTech", "Productivity Apps"],
    ),
    SeedNicheDefinition(
        niche_id="fitness-metabolic-wellness",
        name="Fitness & Metabolic Wellness",
        description="Functional training, high-protein nutrition, recovery protocols, and wearable health habits.",
        criteria_prompt="workouts, gym training, high protein meals, running, recovery, supplements, wellness habits",
        keywords=[
            "fitness",
            "workout",
            "gym",
            "protein",
            "running",
            "recovery",
            "sleep",
            "electrolytes",
            "creatine",
            "mobility",
            "cardio",
            "strength",
            "wellness",
            "macros",
            "habit",
        ],
        typical_hooks=["challenge_log", "form_fix", "what_i_eat", "science_breakdown"],
        typical_formats=["pov", "montage", "tutorial", "vlog"],
        commercial_categories=["Supplements", "Athletic Apparel", "Fitness Apps", "Health Wearables"],
    ),
    SeedNicheDefinition(
        niche_id="specialty-food-beverage",
        name="Specialty Food, Coffee & Functional Drinks",
        description="Home cafe rituals, viral 3-ingredient recipes, functional sodas, and kitchen gear tests.",
        criteria_prompt="recipes, coffee, matcha, cooking, functional beverages, snacks, kitchen gadgets, taste tests",
        keywords=[
            "coffee",
            "matcha",
            "recipe",
            "espresso",
            "drink",
            "kitchen",
            "cooking",
            "protein_snack",
            "taste",
            "latte",
            "beverage",
            "barista",
            "crispy",
            "bake",
            "flavor",
        ],
        typical_hooks=["asmr_pour", "three_ingredient_hack", "taste_test", "cafe_at_home"],
        typical_formats=["asmr_close_up", "recipe_demo", "pov", "tutorial"],
        commercial_categories=["CPG Beverage", "Specialty Coffee", "Kitchen Appliances", "Grocery Delivery"],
    ),
    SeedNicheDefinition(
        niche_id="sustainable-fashion-streetwear",
        name="Capsule Fashion & Streetwear Styling",
        description="Cost-per-wear styling, thrift flips, capsule wardrobes, and silhouette comparisons.",
        criteria_prompt="outfits, fashion styling, streetwear, capsule wardrobe, thrifting, apparel fit checks",
        keywords=[
            "outfit",
            "styling",
            "wardrobe",
            "capsule",
            "streetwear",
            "thrift",
            "fit",
            "denim",
            "jacket",
            "sneakers",
            "fashion",
            "ootd",
            "tailoring",
            "fabric",
        ],
        typical_hooks=["fit_check", "three_ways_to_style", "worth_the_price", "closet_audit"],
        typical_formats=["lookbook", "transition_reel", "talking_head", "pov"],
        commercial_categories=["Apparel", "Footwear", "Resale Platforms", "Accessories"],
    ),
    SeedNicheDefinition(
        niche_id="personal-finance-fintech",
        name="Personal Finance & Smart Money Habits",
        description="Salary transparency, cash-flow systems, credit optimization, and Gen-Z investing explainers.",
        criteria_prompt="budgeting, investing, personal finance, credit cards, saving money, fintech apps, salary breakdown",
        keywords=[
            "budget",
            "money",
            "investing",
            "savings",
            "salary",
            "fintech",
            "credit",
            "apr",
            "cashback",
            "net_worth",
            "paycheck",
            "expense",
            "wealth",
            "tax",
        ],
        typical_hooks=["numbers_breakdown", "money_mistake", "salary_transparency", "step_by_step"],
        typical_formats=["whiteboard_explainer", "talking_head", "green_screen", "storytime"],
        commercial_categories=["FinTech", "Consumer Banking", "Budgeting Software", "Financial Education"],
    ),
]

RISK_LEXICON = {
    "miracle",
    "guaranteed cure",
    "get rich quick",
    "medical claim",
    "nsfw",
    "pirated",
    "unverified",
    "dangerous",
    "hack_illegal",
    "controversy",
    "ragebait",
}

CTA_LEXICON = {
    "comment",
    "link in bio",
    "shop",
    "download",
    "try",
    "code",
    "discount",
    "save this",
    "follow",
    "grab",
    "sign up",
    "free trial",
    "checklist",
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "from",
    "your",
    "have",
    "into",
    "just",
    "what",
    "when",
    "how",
    "why",
    "are",
    "was",
    "were",
    "you",
    "our",
    "out",
    "all",
    "about",
    "over",
    "video",
    "trend",
    "post",
    "using",
    "shows",
    "showing",
}


def _tokenize(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[a-z0-9_+#]{2,}", text.lower()) if tok not in STOPWORDS]


def _softmax(scores: dict[str, float], temperature: float = 1.0) -> dict[str, float]:
    if not scores:
        return {}
    temp = max(temperature, 0.15)
    scaled = {k: v / temp for k, v in scores.items()}
    max_val = max(scaled.values())
    exps = {k: math.exp(v - max_val) for k, v in scaled.items()}
    total = sum(exps.values()) or 1.0
    return {k: round(val / total, 4) for k, val in exps.items()}


class LayaClassifierAdapter:
    """Adapter around `convaiinnovations/laya` (ModernBERT-large, 421M, 512 context, English)."""

    def __init__(self, settings: ValidationSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._custom_niches: list[SeedNicheDefinition] = []
        self._local_laya_agent: Any | None = None
        self._local_hf_pipeline: Any | None = None
        self._load_attempted = False
        self._load_error: str | None = None

    @property
    def seed_taxonomy(self) -> list[SeedNicheDefinition]:
        return [*SEED_NICHE_TAXONOMY, *self._custom_niches]

    def add_custom_seed_niche(self, niche: SeedNicheDefinition) -> None:
        self._custom_niches = [
            existing for existing in self._custom_niches if existing.niche_id != niche.niche_id
        ]
        self._custom_niches.append(niche)

    def runtime_status(self) -> dict[str, Any]:
        return {
            "model_id": self.settings.laya_model_id,
            "huggingface_url": f"https://huggingface.co/{self.settings.laya_model_id}",
            "architecture": "ModernBERT-large (421M params, 512-token context, English)",
            "configured_backend": self.settings.laya_backend,
            "hf_token_present": bool(self.settings.hf_token),
            "local_agent_loaded": self._local_laya_agent is not None or self._local_hf_pipeline is not None,
            "temperature": self.settings.laya_temperature,
            "seed_niche_threshold": self.settings.seed_niche_confidence_threshold,
            "seed_niche_count": len(self.seed_taxonomy),
            "last_load_note": self._load_error,
        }

    # ------------------------------------------------------------------
    # 1. 512-Token Compact English Context Builder for ModernBERT-large
    # ------------------------------------------------------------------
    def build_compact_laya_state(
        self, trend: OrganTrendDescription
    ) -> tuple[dict[str, Any], str, int, bool, bool]:
        """Serialize trend + v1.2 record evidence strictly within Laya's 512-token window."""
        en_records: list[OrganVideoRecordV1_2] = []
        non_en_count = 0
        for rec in trend.records:
            is_en = rec.language.code.lower().startswith("en") and rec.status != "unsupported_language"
            if is_en:
                en_records.append(rec)
            else:
                non_en_count += 1

        usable = en_records if en_records else trend.records
        english_compatible = len(en_records) > 0 or len(trend.records) == 0

        topics = [r.features.topic for r in usable if r.features.topic]
        hooks = [r.features.hook_type for r in usable if r.features.hook_type]
        formats = [r.features.format for r in usable if r.features.format]
        ctas = [r.features.call_to_action for r in usable if r.features.call_to_action]
        openings = [r.features.opening_text for r in usable if r.features.opening_text]
        hashtags: list[str] = []
        captions: list[str] = []
        visuals: list[str] = []
        transcripts: list[str] = []
        ocr_snippets: list[str] = []

        truncated = len(usable) > 4 or len(trend.summary) > 220

        for r in usable[:4]:
            hashtags.extend(r.elements.hashtags[:6])
            if r.elements.post_description:
                if len(r.elements.post_description) > 140:
                    truncated = True
                captions.append(r.elements.post_description[:140])
            if r.visual.summary:
                if len(r.visual.summary) > 140:
                    truncated = True
                visuals.append(r.visual.summary[:140])
            if r.elements.transcript.text:
                if len(r.elements.transcript.text) > 180:
                    truncated = True
                transcripts.append(r.elements.transcript.text[:180])
            for item in r.elements.on_screen_text.items[:3]:
                if item.text:
                    ocr_snippets.append(item.text[:60])

        state_obj: dict[str, Any] = {
            "trend_title": trend.title[:100],
            "trend_summary": trend.summary[:220],
            "shared_elements": trend.shared_elements[:8],
            "topics": list(dict.fromkeys(topics))[:5],
            "hooks": list(dict.fromkeys(hooks))[:4],
            "formats": list(dict.fromkeys(formats))[:4],
            "ctas": list(dict.fromkeys(ctas))[:4],
            "openings": openings[:3],
            "hashtags": list(dict.fromkeys(h.lower().lstrip("#") for h in hashtags))[:12],
            "visual_summary": " | ".join(visuals)[:260],
            "ocr_text": " | ".join(ocr_snippets)[:180],
            "captions": " | ".join(captions)[:240],
            "transcript_excerpt": " | ".join(transcripts)[:320],
        }

        serialized = (
            f"TREND: {state_obj['trend_title']}. {state_obj['trend_summary']} "
            f"TOPICS: {', '.join(state_obj['topics'])}. "
            f"HOOKS: {', '.join(state_obj['hooks'])}. "
            f"FORMATS: {', '.join(state_obj['formats'])}. "
            f"CTA: {', '.join(state_obj['ctas'])}. "
            f"HASHTAGS: {', '.join(state_obj['hashtags'])}. "
            f"OPENINGS: {' / '.join(state_obj['openings'])}. "
            f"VISUAL: {state_obj['visual_summary']}. "
            f"OCR: {state_obj['ocr_text']}. "
            f"CAPTIONS: {state_obj['captions']}. "
            f"TRANSCRIPT: {state_obj['transcript_excerpt']}"
        ).strip()

        # ModernBERT subword tokenizer averages ~3.6 characters per token on social text.
        # Reserve ~130 tokens for Laya typed question prompts so total <= 512 tokens.
        max_state_tokens = max(self.settings.laya_max_tokens - 132, 180)
        max_chars = int(max_state_tokens * 3.6)
        if len(serialized) > max_chars:
            serialized = serialized[:max_chars].rsplit(" ", 1)[0] + "..."
            state_obj["transcript_excerpt"] = state_obj["transcript_excerpt"][:120]
            truncated = True

        estimated_tokens = min(
            self.settings.laya_max_tokens,
            int(math.ceil(len(serialized) / 3.6)) + 115,
        )
        if non_en_count > 0 and not english_compatible:
            truncated = truncated or False

        return state_obj, serialized, estimated_tokens, truncated, english_compatible

    def build_laya_questions(self) -> dict[str, Any]:
        """Typed-decision primitives expected by `convaiinnovations/laya`."""
        return {
            "niche": {
                "type": "choice",
                "instructions": "Which content marketing niche best matches this short-form video trend?",
                "criteria": {n.niche_id: n.criteria_prompt for n in self.seed_taxonomy},
            },
            "virality_potential": {
                "type": "score",
                "instructions": "Rate the short-form virality and shareability momentum of this trend.",
                "criteria": ["low", "moderate", "strong", "breakout"],
            },
            "commercial_readiness": {
                "type": "score",
                "instructions": "Rate how naturally a business can attach a product, offer, or conversion CTA.",
                "criteria": ["poor", "indirect", "promising", "high_intent"],
            },
            "brand_safe": {
                "type": "noul",
                "instructions": "Is this trend safe for mainstream commercial brand sponsorship without controversial or unverified claims?",
            },
            "clear_cta": {
                "type": "noul",
                "instructions": "Does this trend feature a clear, repeatable viewer call-to-action?",
            },
        }

    # ------------------------------------------------------------------
    # 2. Optional Local / HF Remote Model Execution
    # ------------------------------------------------------------------
    def _try_load_local(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True

        if self.settings.laya_backend in {"heuristic", "fallback", "hf_api"}:
            return

        # Only eagerly load local 421M weights when explicitly requested (`local`, `laya_sdk`, `transformers`)
        # or if `laya` package is already installed in `.venv` under `auto`.
        try:
            import laya  # type: ignore[import-not-found]

            if self.settings.laya_backend in {"local", "laya_sdk", "auto"}:
                self._local_laya_agent = laya.load(self.settings.laya_model_id)
                return
        except Exception as exc:  # pragma: no cover - optional heavy dependency
            self._load_error = f"laya SDK unavailable ({type(exc).__name__}); using calibrated signal engine."

        if self.settings.laya_backend == "transformers":
            try:
                from transformers import pipeline  # type: ignore[import-not-found]

                self._local_hf_pipeline = pipeline(
                    "zero-shot-classification",
                    model=self.settings.laya_model_id,
                    truncation=True,
                    max_length=self.settings.laya_max_tokens,
                )
            except Exception as exc:  # pragma: no cover
                self._load_error = f"transformers load skipped ({type(exc).__name__}: {exc})"

    def _query_hf_inference_api(
        self, serialized_state: str
    ) -> dict[str, float] | None:
        if not self.settings.hf_token or self.settings.laya_backend in {"heuristic", "fallback", "local"}:
            return None
        url = f"https://router.huggingface.co/hf-inference/models/{self.settings.laya_model_id}"
        candidate_labels = [n.name for n in self.seed_taxonomy]
        label_to_id = {n.name: n.niche_id for n in self.seed_taxonomy}
        try:
            with httpx.Client(timeout=6.0) as client:
                resp = client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.settings.hf_token}"},
                    json={
                        "inputs": serialized_state,
                        "parameters": {"candidate_labels": candidate_labels},
                    },
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()
                if isinstance(data, dict) and "labels" in data and "scores" in data:
                    return {
                        label_to_id.get(lbl, lbl): float(sc)
                        for lbl, sc in zip(data["labels"], data["scores"])
                    }
        except Exception as exc:
            self._load_error = f"HF Inference API fallback ({type(exc).__name__})"
        return None

    # ------------------------------------------------------------------
    # 3. Calibrated System-1 Evaluation + Hybrid Niche Trigger
    # ------------------------------------------------------------------
    def evaluate_trend(self, trend: OrganTrendDescription) -> LayaTypedDecisionTrace:
        state_obj, serialized_state, est_tokens, truncated, en_ok = self.build_compact_laya_state(
            trend
        )
        questions = self.build_laya_questions()
        notes: list[str] = []

        if not en_ok:
            notes.append(
                "convaiinnovations/laya is an English-root ModernBERT-large encoder; trend records lack supported English transcripts/metadata."
            )
        if truncated:
            notes.append(
                f"Input compressed to fit {self.settings.laya_max_tokens}-token ModernBERT context window."
            )

        # Compute rich multi-signal lexical & structural logits across seed niches
        corpus_tokens = Counter(_tokenize(serialized_state))
        raw_logits: dict[str, float] = {}
        matched_keyword_counts: dict[str, int] = {}

        for niche in self.seed_taxonomy:
            score = 0.15
            kw_hits = 0
            for kw in niche.keywords:
                kw_clean = kw.lower()
                if kw_clean in corpus_tokens:
                    kw_hits += 1
                    score += 1.35 + min(0.45, 0.15 * corpus_tokens[kw_clean])
                elif kw_clean.replace("_", " ") in serialized_state.lower():
                    kw_hits += 1
                    score += 1.25

            for hook in niche.typical_hooks:
                if any(hook in h.lower() for h in state_obj["hooks"]):
                    score += 0.65
            for fmt in niche.typical_formats:
                if any(fmt in f.lower() for f in state_obj["formats"]):
                    score += 0.45

            matched_keyword_counts[niche.niche_id] = kw_hits
            raw_logits[niche.niche_id] = score

        execution_mode: LayaBackendStatus = "laya_calibrated_fallback"
        model_choice_probs: dict[str, float] | None = None

        self._try_load_local()
        if self._local_laya_agent is not None:
            try:
                res = self._local_laya_agent.predict(state_obj, questions)
                ans = res.get("answers", res) if isinstance(res, dict) else {}
                niche_ans = ans.get("niche", {})
                if isinstance(niche_ans, dict) and "probabilities" in niche_ans:
                    model_choice_probs = {
                        str(k): float(v) for k, v in niche_ans["probabilities"].items()
                    }
                    execution_mode = "laya_sdk_local"
                elif isinstance(niche_ans, dict) and "choice" in niche_ans:
                    chosen = str(niche_ans["choice"])
                    conf = float(niche_ans.get("confidence", 0.65))
                    rem = max(0.0, 1.0 - conf) / max(1, len(self.seed_taxonomy) - 1)
                    model_choice_probs = {
                        n.niche_id: (conf if n.niche_id == chosen else rem)
                        for n in self.seed_taxonomy
                    }
                    execution_mode = "laya_sdk_local"
            except Exception as exc:  # pragma: no cover
                notes.append(f"Local Laya SDK forward pass fallback ({type(exc).__name__}).")

        if model_choice_probs is None and self._local_hf_pipeline is not None:
            try:
                labels = [n.criteria_prompt for n in self.seed_taxonomy]
                prompt_to_id = {n.criteria_prompt: n.niche_id for n in self.seed_taxonomy}
                out = self._local_hf_pipeline(serialized_state, candidate_labels=labels)
                model_choice_probs = {
                    prompt_to_id[lbl]: float(sc)
                    for lbl, sc in zip(out["labels"], out["scores"])
                }
                execution_mode = "laya_transformers_local"
            except Exception as exc:  # pragma: no cover
                notes.append(f"Local HF pipeline fallback ({type(exc).__name__}).")

        if model_choice_probs is None:
            hf_probs = self._query_hf_inference_api(serialized_state)
            if hf_probs:
                model_choice_probs = hf_probs
                execution_mode = "laya_hf_inference_api"

        heuristic_probs = _softmax(raw_logits, temperature=self.settings.laya_temperature)

        # Calibrated fusion: per model card guidance, raw zero-shot Laya benefits from calibration
        if model_choice_probs:
            blended = {
                nid: round(0.55 * model_choice_probs.get(nid, 0.0) + 0.45 * heuristic_probs.get(nid, 0.0), 4)
                for nid in heuristic_probs
            }
            total_b = sum(blended.values()) or 1.0
            choice_probs = {k: round(v / total_b, 4) for k, v in blended.items()}
            notes.append(
                f"Executed {self.settings.laya_model_id} ({execution_mode}) with temperature calibration (T={self.settings.laya_temperature})."
            )
        else:
            choice_probs = heuristic_probs
            notes.append(
                f"Calibrated System-1 decision trace ready for {self.settings.laya_model_id} (set LAYA_BACKEND=local or HF_TOKEN for live neural weights)."
            )

        top_id, top_conf = max(choice_probs.items(), key=lambda kv: kv[1])
        top_kw_hits = matched_keyword_counts.get(top_id, 0)

        # Hybrid Emergent Niche trigger: if even top seed niche has weak lexical/model support,
        # flag `emergent_niche_triggered = True` so NicheEngine spawns a dynamic cluster!
        emergent_triggered = (
            top_conf < self.settings.seed_niche_confidence_threshold or top_kw_hits <= 1
        )
        if emergent_triggered:
            notes.append(
                f"Hybrid mode: max seed confidence ({top_conf:.2f}, keyword hits={top_kw_hits}) below threshold "
                f"({self.settings.seed_niche_confidence_threshold:.2f}) -> spawning emergent niche cluster."
            )

        # Compute ordinal `score` & boolean `noul` primitives from record metrics & text signals
        usable_records = [r for r in trend.records if r.status != "unsupported_language"] or trend.records
        avg_like = (
            sum(r.observation.like_rate for r in usable_records) / len(usable_records)
            if usable_records
            else 0.0
        )
        avg_share = (
            sum(r.observation.share_rate for r in usable_records) / len(usable_records)
            if usable_records
            else 0.0
        )
        virality_score = min(1.0, round((avg_like / 0.12) * 0.45 + (avg_share / 0.025) * 0.55, 3))
        if virality_score >= 0.8:
            virality_label = "breakout"
        elif virality_score >= 0.58:
            virality_label = "strong"
        elif virality_score >= 0.35:
            virality_label = "moderate"
        else:
            virality_label = "low"

        lower_state = serialized_state.lower()
        cta_hits = sum(1 for phrase in CTA_LEXICON if phrase in lower_state)
        has_explicit_cta = any(bool(r.features.call_to_action.strip()) for r in usable_records)
        num_expr_count = sum(len(r.elements.numeric_expressions) for r in usable_records)
        clear_cta_prob = min(
            0.98,
            round(0.28 + (0.36 if has_explicit_cta else 0.0) + min(0.26, cta_hits * 0.09) + min(0.10, num_expr_count * 0.04), 3),
        )

        commercial_score = min(
            1.0,
            round(0.55 * clear_cta_prob + (0.25 if top_kw_hits >= 2 else 0.12) + min(0.20, num_expr_count * 0.07), 3),
        )
        if commercial_score >= 0.78:
            commercial_label = "high_intent"
        elif commercial_score >= 0.55:
            commercial_label = "promising"
        elif commercial_score >= 0.35:
            commercial_label = "indirect"
        else:
            commercial_label = "poor"

        # Brand safety `noul` probability
        risk_hits = sum(1 for rword in RISK_LEXICON if rword in lower_state)
        limitation_flags = sum(len(r.limitations) for r in trend.records)
        partial_or_unsup = sum(1 for r in trend.records if r.status != "complete")
        brand_safe_prob = max(
            0.08,
            min(
                0.97,
                round(
                    0.93
                    - risk_hits * 0.22
                    - limitation_flags * 0.045
                    - partial_or_unsup * 0.07
                    - (0.18 if not en_ok else 0.0),
                    3,
                ),
            ),
        )

        # Estimate production effort from duration + visual actions density
        avg_duration = (
            sum(r.video.duration_seconds for r in usable_records) / len(usable_records)
            if usable_records
            else 25.0
        )
        avg_actions = (
            sum(len(r.visual.actions) for r in usable_records) / len(usable_records)
            if usable_records
            else 2.0
        )
        if avg_duration <= 24 and avg_actions <= 2.5:
            effort: LayaTypedDecisionTrace.__annotations__["production_effort_label"] = "low"  # type: ignore[assignment]
            effort_val: Any = "low"
        elif avg_duration <= 48 and avg_actions <= 4.5:
            effort_val = "medium"
        else:
            effort_val = "high"

        return LayaTypedDecisionTrace(
            model_id=self.settings.laya_model_id,
            backbone="ModernBERT-large (421M params, 512 context, English)",
            execution_mode=execution_mode,
            estimated_input_tokens=est_tokens,
            max_context_tokens=self.settings.laya_max_tokens,
            input_truncated=truncated,
            english_compatible=en_ok,
            temperature=self.settings.laya_temperature,
            choice_probabilities=dict(
                sorted(choice_probs.items(), key=lambda kv: kv[1], reverse=True)
            ),
            top_choice_id=top_id,
            top_choice_confidence=round(top_conf, 4),
            virality_rubric_score=virality_score,
            virality_rubric_label=virality_label,
            commercial_rubric_score=commercial_score,
            commercial_rubric_label=commercial_label,
            production_effort_label=effort_val,
            brand_safe_probability=brand_safe_prob,
            clear_cta_probability=clear_cta_prob,
            emergent_niche_triggered=emergent_triggered,
            compact_state_preview=serialized_state[:360] + ("..." if len(serialized_state) > 360 else ""),
            notes=notes,
        )
