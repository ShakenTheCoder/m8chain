"""Persona Modeling & Suitability Verdict Engine (`content_creator` vs. `business`)."""

from __future__ import annotations

from ..schemas.niche import LayaTypedDecisionTrace, NicheCluster
from ..schemas.organ_v1_2 import (
    OrganTrendDescription,
    TrendBenchmarkMetrics,
    TrendDominantFeatures,
)
from ..schemas.persona import PersonaProfile
from ..schemas.verdict_handoff import (
    DimensionBreakdown,
    EvidenceReference,
    FitStatus,
    SuitabilityVerdict,
)


EFFORT_RANK = {"low": 1, "medium": 2, "high": 3}


class SuitabilityVerdictEngine:
    """Evaluates whether a matched (Trend, Niche) pair is suitable for the active Persona."""

    def evaluate(
        self,
        trend: OrganTrendDescription,
        niche: NicheCluster,
        laya_trace: LayaTypedDecisionTrace,
        metrics: TrendBenchmarkMetrics,
        dominant: TrendDominantFeatures,
        persona: PersonaProfile,
    ) -> SuitabilityVerdict:
        allowed_langs = {lang.lower() for lang in persona.allowed_languages} or {"en"}
        lang_compatible_records = [
            r
            for r in trend.records
            if r.status != "unsupported_language"
            and any(r.language.code.lower().startswith(al) for al in allowed_langs)
        ]

        domain_score, domain_hits = self._score_domain_relevance(
            trend, niche, dominant, persona
        )
        completeness_score = self._score_data_completeness(trend, metrics, len(lang_compatible_records))

        strengths: list[str] = []
        risks: list[str] = []

        if persona.type == "content_creator":
            persona_align, exec_or_safety, momentum, cta_fit = self._evaluate_creator(
                trend,
                laya_trace,
                metrics,
                dominant,
                persona,
                strengths,
                risks,
            )
            weights = {
                "domain": 0.24,
                "persona": 0.24,
                "momentum": 0.26,
                "exec_safety": 0.14,
                "cta": 0.04,
                "completeness": 0.08,
            }
        else:
            persona_align, exec_or_safety, momentum, cta_fit = self._evaluate_business(
                trend,
                niche,
                laya_trace,
                metrics,
                dominant,
                persona,
                strengths,
                risks,
            )
            weights = {
                "domain": 0.24,
                "persona": 0.18,
                "momentum": 0.14,
                "exec_safety": 0.22,
                "cta": 0.14,
                "completeness": 0.08,
            }

        if domain_hits:
            strengths.insert(
                0,
                f"Direct domain alignment on {', '.join(domain_hits[:4])} within '{niche.name}'.",
            )
        elif domain_score < 48:
            risks.insert(
                0,
                f"Low overlap between persona target domain ('{persona.target_domain}') and niche '{niche.name}'.",
            )

        # Surface record status & upstream limitations transparently
        if metrics.partial_count > 0:
            risks.append(
                f"{metrics.partial_count}/{metrics.record_count} supporting v1.2 record(s) have status='partial'."
            )
        if metrics.unsupported_language_count > 0:
            risks.append(
                f"{metrics.unsupported_language_count}/{metrics.record_count} record(s) flagged status='unsupported_language'."
            )
        for rec in trend.records:
            for lim in rec.limitations[:2]:
                formatted = f"[{rec.id}] {lim}"
                if formatted not in risks:
                    risks.append(formatted)

        overall = round(
            domain_score * weights["domain"]
            + persona_align * weights["persona"]
            + momentum * weights["momentum"]
            + exec_or_safety * weights["exec_safety"]
            + cta_fit * weights["cta"]
            + completeness_score * weights["completeness"],
            1,
        )

        # Disqualification gates
        disqualified = False
        disqualify_reason = ""
        if len(lang_compatible_records) == 0 and len(trend.records) > 0:
            disqualified = True
            overall = min(overall, 28.0)
            disqualify_reason = (
                f"All {len(trend.records)} supporting record(s) are in unsupported languages for persona allowed_languages={persona.allowed_languages}."
            )
            risks.insert(0, disqualify_reason)
        elif (
            persona.type == "business"
            and persona.business_params.brand_safety_strictness == "strict"
            and laya_trace.brand_safe_probability < 0.50
        ):
            disqualified = True
            overall = min(overall, 35.0)
            disqualify_reason = (
                f"Strict brand safety gate triggered (Laya P(brand_safe)={laya_trace.brand_safe_probability:.2f} < 0.50)."
            )
            risks.insert(0, disqualify_reason)

        fit_status = self._determine_fit_status(overall, disqualified)
        headline, rationale = self._compose_narrative(
            fit_status,
            overall,
            trend,
            niche,
            persona,
            disqualify_reason,
        )
        angles = self._build_recommended_angles(trend, niche, dominant, persona)
        evidence = self._extract_evidence_refs(trend)

        return SuitabilityVerdict(
            trend_id=trend.trend_id,
            niche_id=niche.niche_id,
            persona_type=persona.type,
            fit_status=fit_status,
            overall_score=overall,
            dimension_scores=DimensionBreakdown(
                domain_relevance=round(domain_score, 1),
                persona_alignment=round(persona_align, 1),
                engagement_momentum=round(momentum, 1),
                execution_or_brand_safety=round(exec_or_safety, 1),
                cta_and_conversion_fit=round(cta_fit, 1),
                data_completeness=round(completeness_score, 1),
            ),
            headline=headline,
            rationale=rationale,
            strengths=strengths[:5],
            risks_and_limitations=risks[:6],
            recommended_angles=angles,
            evidence_refs=evidence,
        )

    def _score_domain_relevance(
        self,
        trend: OrganTrendDescription,
        niche: NicheCluster,
        dominant: TrendDominantFeatures,
        persona: PersonaProfile,
    ) -> tuple[float, list[str]]:
        haystack = " ".join(
            [
                trend.title,
                trend.summary,
                dominant.topic,
                " ".join(dominant.common_hashtags),
                niche.name,
                niche.description,
                " ".join(niche.keywords),
                " ".join(r.elements.post_description for r in trend.records),
            ]
        ).lower()

        persona_terms = [
            kw.strip().lower()
            for kw in [
                *persona.domain_keywords,
                *[w for w in persona.target_domain.lower().replace("&", " ").split() if len(w) >= 4],
            ]
            if kw.strip()
        ]
        unique_terms = list(dict.fromkeys(persona_terms))
        if not unique_terms:
            return 72.0, []

        hits = [term for term in unique_terms if term in haystack]
        hit_ratio = len(hits) / max(1, min(len(unique_terms), 5))
        base = 34.0 + min(62.0, hit_ratio * 62.0) + (niche.confidence * 6.0 if hits else 0.0)
        return min(98.0, base), hits

    def _score_data_completeness(
        self,
        trend: OrganTrendDescription,
        metrics: TrendBenchmarkMetrics,
        lang_ok_count: int,
    ) -> float:
        if metrics.record_count == 0:
            return 15.0
        complete_ratio = metrics.complete_count / metrics.record_count
        partial_ratio = metrics.partial_count / metrics.record_count
        lang_ratio = lang_ok_count / metrics.record_count
        lim_penalty = min(22.0, sum(len(r.limitations) for r in trend.records) * 4.5)
        score = 30.0 + complete_ratio * 48.0 + partial_ratio * 22.0 + lang_ratio * 22.0 - lim_penalty
        return max(10.0, min(99.0, score))

    def _evaluate_creator(
        self,
        trend: OrganTrendDescription,
        laya_trace: LayaTypedDecisionTrace,
        metrics: TrendBenchmarkMetrics,
        dominant: TrendDominantFeatures,
        persona: PersonaProfile,
        strengths: list[str],
        risks: list[str],
    ) -> tuple[float, float, float, float]:
        cp = persona.creator_params
        pref_formats = {f.lower().replace("-", "_") for f in cp.preferred_formats}
        dom_fmt = dominant.format.lower().replace("-", "_")

        fmt_match = any(pf in dom_fmt or dom_fmt in pf for pf in pref_formats) if pref_formats else True
        persona_align = 84.0 if fmt_match else 58.0

        # Audio preference alignment
        usable = [r for r in trend.records if r.status != "unsupported_language"] or trend.records
        orig_ratio = (
            sum(1 for r in usable if r.elements.sound.is_original) / len(usable)
            if usable
            else 0.5
        )
        if cp.original_audio_preference == "original_only":
            persona_align += 10.0 if orig_ratio >= 0.6 else -14.0
        elif cp.original_audio_preference == "trending_sound":
            persona_align += 10.0 if orig_ratio <= 0.5 else -10.0
        else:
            persona_align += 5.0

        if fmt_match:
            strengths.append(
                f"Format '{dominant.format}' with '{dominant.hook_type}' hook fits creator preferred formats."
            )
        else:
            risks.append(
                f"Dominant format '{dominant.format}' differs from preferred creator formats ({', '.join(cp.preferred_formats[:3])})."
            )

        # Execution effort vs max_production_effort
        req_effort = EFFORT_RANK.get(laya_trace.production_effort_label, 2)
        cap_effort = EFFORT_RANK.get(cp.max_production_effort, 2)
        if req_effort <= cap_effort:
            exec_score = 88.0 + (cap_effort - req_effort) * 5.0
            strengths.append(
                f"Estimated production effort ('{laya_trace.production_effort_label}') stays within '{cp.max_production_effort}' budget."
            )
        else:
            exec_score = 52.0 - (req_effort - cap_effort) * 14.0
            risks.append(
                f"Trend execution effort ('{laya_trace.production_effort_label}') exceeds creator cap ('{cp.max_production_effort}')."
            )

        # Momentum weighted by creator growth_goal
        like_norm = min(100.0, (metrics.avg_like_rate / 0.11) * 100.0)
        share_norm = min(100.0, (metrics.avg_share_rate / 0.024) * 100.0)
        comm_save_norm = min(
            100.0, ((metrics.avg_save_rate + metrics.avg_comment_rate) / 0.032) * 100.0
        )

        if cp.growth_goal == "virality":
            momentum = 0.55 * share_norm + 0.30 * like_norm + 0.15 * comm_save_norm
        elif cp.growth_goal == "engagement":
            momentum = 0.50 * like_norm + 0.25 * share_norm + 0.25 * comm_save_norm
        else:
            momentum = 0.55 * comm_save_norm + 0.25 * like_norm + 0.20 * share_norm

        if momentum >= 75:
            strengths.append(
                f"Strong {cp.growth_goal} velocity (avg like_rate={metrics.avg_like_rate:.1%}, share_rate={metrics.avg_share_rate:.2%})."
            )

        cta_fit = min(96.0, laya_trace.clear_cta_probability * 95.0)
        return (
            max(15.0, min(98.0, persona_align)),
            max(15.0, min(98.0, exec_score)),
            max(15.0, min(98.0, momentum)),
            max(20.0, cta_fit),
        )

    def _evaluate_business(
        self,
        trend: OrganTrendDescription,
        niche: NicheCluster,
        laya_trace: LayaTypedDecisionTrace,
        metrics: TrendBenchmarkMetrics,
        dominant: TrendDominantFeatures,
        persona: PersonaProfile,
        strengths: list[str],
        risks: list[str],
    ) -> tuple[float, float, float, float]:
        bp = persona.business_params

        # Brand safety dimension
        safety_base = laya_trace.brand_safe_probability * 100.0
        if bp.brand_safety_strictness == "strict" and laya_trace.brand_safe_probability < 0.78:
            safety_base -= 14.0
            risks.append(
                f"Strict brand safety posture flags moderate risk (Laya P(brand_safe)={laya_trace.brand_safe_probability:.2f})."
            )
        elif laya_trace.brand_safe_probability >= 0.82:
            strengths.append(
                f"High brand-safety confidence (Laya P(brand_safe)={laya_trace.brand_safe_probability:.2f})."
            )

        # CTA & conversion fit weighted by campaign_objective
        comm_pct = laya_trace.commercial_rubric_score * 100.0
        cta_pct = laya_trace.clear_cta_probability * 100.0

        if bp.campaign_objective == "direct_conversion":
            cta_fit = 0.55 * cta_pct + 0.45 * comm_pct
        elif bp.campaign_objective == "lead_gen":
            cta_fit = 0.60 * cta_pct + 0.40 * comm_pct
        else:
            cta_fit = 0.35 * cta_pct + 0.40 * comm_pct + 25.0

        if cta_fit >= 72:
            strengths.append(
                f"Clear conversion mechanics ('{dominant.call_to_action}') align with '{bp.campaign_objective}' objective."
            )
        else:
            risks.append(
                f"Weak explicit CTA signal for '{bp.campaign_objective}' (Laya P(clear_cta)={laya_trace.clear_cta_probability:.2f})."
            )

        # Commercial placement fit (`persona_alignment`)
        persona_align = 0.55 * comm_pct + 0.45 * (85.0 if niche.commercial_categories else 60.0)
        if bp.commercial_fit_required and laya_trace.commercial_rubric_score < 0.50:
            persona_align -= 18.0
            risks.append(
                f"Commercial placement readiness rated '{laya_trace.commercial_rubric_label}' while commercial_fit_required=True."
            )

        momentum = min(
            98.0,
            (metrics.avg_like_rate / 0.10) * 45.0 + (metrics.avg_share_rate / 0.022) * 55.0,
        )
        return (
            max(15.0, min(98.0, persona_align)),
            max(10.0, min(98.0, safety_base)),
            max(15.0, min(98.0, momentum)),
            max(15.0, min(98.0, cta_fit)),
        )

    def _determine_fit_status(self, overall: float, disqualified: bool) -> FitStatus:
        if disqualified or overall < 38.0:
            return "disqualified"
        if overall >= 76.0:
            return "strong_fit"
        if overall >= 56.0:
            return "conditional_fit"
        return "weak_fit"

    def _compose_narrative(
        self,
        fit_status: FitStatus,
        overall: float,
        trend: OrganTrendDescription,
        niche: NicheCluster,
        persona: PersonaProfile,
        disqualify_reason: str,
    ) -> tuple[str, str]:
        persona_label = (
            "Content Creator" if persona.type == "content_creator" else "Business Marketing"
        )
        status_label = fit_status.replace("_", " ").title()
        headline = f"{status_label} ({overall:.1f}/100) for {persona_label} in {niche.name}"

        if disqualify_reason:
            return headline, disqualify_reason

        origin_note = (
            "emergent niche cluster synthesized dynamically"
            if niche.origin == "emergent_cluster"
            else "curated niche matched via Laya ModernBERT-large"
        )
        rationale = (
            f"Trend '{trend.title}' mapped to '{niche.name}' ({origin_note}, confidence {niche.confidence:.0%}). "
            f"Evaluated for {persona_label} targeting '{persona.target_domain}', scoring {overall:.1f}/100 "
            f"across domain fit, engagement velocity, and persona execution guardrails."
        )
        return headline, rationale

    def _build_recommended_angles(
        self,
        trend: OrganTrendDescription,
        niche: NicheCluster,
        dominant: TrendDominantFeatures,
        persona: PersonaProfile,
    ) -> list[str]:
        if persona.type == "content_creator":
            return [
                f"Open in the first 2.5s using a '{dominant.hook_type}' hook anchored on {persona.target_domain}.",
                f"Deliver in '{dominant.format}' format keeping pacing aligned with '{niche.name}' benchmarks.",
                f"Close with a community-sparking prompt ('{dominant.call_to_action}') to amplify saves & shares.",
            ]
        return [
            f"Adapt the '{dominant.hook_type}' pattern into a brand-safe proof point for {persona.target_domain}.",
            f"Pair '{dominant.format}' creative with an explicit '{persona.business_params.campaign_objective}' CTA ('{dominant.call_to_action}').",
            "Seed 3 hook variations in Part 3 Optimization GA population before scaling paid budget.",
        ]

    def _extract_evidence_refs(
        self, trend: OrganTrendDescription
    ) -> list[EvidenceReference]:
        refs: list[EvidenceReference] = []
        for rec in trend.records[:4]:
            if rec.elements.transcript.segments:
                seg = rec.elements.transcript.segments[0]
                refs.append(
                    EvidenceReference(
                        record_id=rec.id,
                        platform=rec.video.platform,
                        record_status=rec.status,
                        signal_type="transcript_hook",
                        excerpt=seg.text[:140],
                        timestamp_range=f"{seg.start_seconds:.1f}s - {seg.end_seconds:.1f}s",
                    )
                )
            elif rec.visual.actions:
                act = rec.visual.actions[0]
                refs.append(
                    EvidenceReference(
                        record_id=rec.id,
                        platform=rec.video.platform,
                        record_status=rec.status,
                        signal_type="visual_action",
                        excerpt=act.description[:140],
                        timestamp_range=f"{act.start_seconds:.1f}s - {act.end_seconds:.1f}s",
                    )
                )
            elif rec.limitations:
                refs.append(
                    EvidenceReference(
                        record_id=rec.id,
                        platform=rec.video.platform,
                        record_status=rec.status,
                        signal_type="limitation_flag",
                        excerpt=rec.limitations[0][:140],
                        timestamp_range=None,
                    )
                )
        return refs
