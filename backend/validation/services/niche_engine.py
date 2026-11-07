"""Hybrid Niche Creation & Trend-to-Niche Matching Engine (Seed Taxonomy + Emergent Clusters)."""

from __future__ import annotations

from collections import Counter
import re

from ..adapters.laya_classifier import LayaClassifierAdapter, STOPWORDS
from ..schemas.niche import LayaTypedDecisionTrace, NicheCluster, SeedNicheDefinition
from ..schemas.organ_v1_2 import OrganTrendDescription


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:42] or "emergent-niche"


class HybridNicheEngine:
    """Matches incoming Organ Trend Descriptions to Seed Niches via `convaiinnovations/laya`
    or dynamically synthesizes Emergent Niches when novel semantic clusters appear.
    """

    def __init__(self, classifier: LayaClassifierAdapter) -> None:
        self.classifier = classifier

    def classify_and_cluster(
        self, trends: list[OrganTrendDescription]
    ) -> tuple[dict[str, NicheCluster], dict[str, LayaTypedDecisionTrace], list[NicheCluster]]:
        trend_to_niche: dict[str, NicheCluster] = {}
        trend_to_trace: dict[str, LayaTypedDecisionTrace] = {}
        aggregated_niches: dict[str, NicheCluster] = {}

        seed_lookup: dict[str, SeedNicheDefinition] = {
            n.niche_id: n for n in self.classifier.seed_taxonomy
        }

        for trend in trends:
            trace = self.classifier.evaluate_trend(trend)
            trend_to_trace[trend.trend_id] = trace
            cohesion = self._compute_trend_cohesion(trend)

            if not trace.emergent_niche_triggered and trace.top_choice_id in seed_lookup:
                seed_def = seed_lookup[trace.top_choice_id]
                is_custom = seed_def.niche_id.startswith("custom-")
                origin = "custom_user" if is_custom else "seed_taxonomy"

                if seed_def.niche_id not in aggregated_niches:
                    aggregated_niches[seed_def.niche_id] = NicheCluster(
                        niche_id=seed_def.niche_id,
                        name=seed_def.name,
                        origin=origin,
                        description=seed_def.description,
                        taxonomy_source="convaiinnovations/laya-seed-v1",
                        confidence=trace.top_choice_confidence,
                        cohesion_score=cohesion,
                        keywords=seed_def.keywords[:10],
                        matched_trend_ids=[trend.trend_id],
                        commercial_categories=seed_def.commercial_categories,
                    )
                else:
                    existing = aggregated_niches[seed_def.niche_id]
                    if trend.trend_id not in existing.matched_trend_ids:
                        existing.matched_trend_ids.append(trend.trend_id)
                    existing.confidence = round(
                        max(existing.confidence, trace.top_choice_confidence), 4
                    )
                    existing.cohesion_score = round(
                        (existing.cohesion_score + cohesion) / 2.0, 4
                    )

                trend_to_niche[trend.trend_id] = aggregated_niches[seed_def.niche_id].model_copy(
                    update={"confidence": trace.top_choice_confidence, "cohesion_score": cohesion}
                )
            else:
                emergent = self._synthesize_emergent_niche(trend, trace, cohesion)
                # Merge into existing emergent cluster if >= 2 keywords overlap
                merged_id = self._find_mergeable_emergent(emergent, aggregated_niches)
                if merged_id:
                    target = aggregated_niches[merged_id]
                    if trend.trend_id not in target.matched_trend_ids:
                        target.matched_trend_ids.append(trend.trend_id)
                    combined_kw = list(dict.fromkeys([*target.keywords, *emergent.keywords]))[:10]
                    target.keywords = combined_kw
                    trend_to_niche[trend.trend_id] = target.model_copy()
                else:
                    aggregated_niches[emergent.niche_id] = emergent
                    trend_to_niche[trend.trend_id] = emergent.model_copy()

        ordered_niches = sorted(
            aggregated_niches.values(),
            key=lambda n: (len(n.matched_trend_ids), n.confidence),
            reverse=True,
        )
        return trend_to_niche, trend_to_trace, ordered_niches

    def _compute_trend_cohesion(self, trend: OrganTrendDescription) -> float:
        usable = [r for r in trend.records if r.status != "unsupported_language"] or trend.records
        if len(usable) <= 1:
            return 0.78 if usable else 0.35

        topics = [r.features.topic.lower().strip() for r in usable if r.features.topic]
        formats = [r.features.format.lower().strip() for r in usable if r.features.format]
        hooks = [r.features.hook_type.lower().strip() for r in usable if r.features.hook_type]

        topic_agreement = (
            Counter(topics).most_common(1)[0][1] / len(topics) if topics else 0.5
        )
        format_agreement = (
            Counter(formats).most_common(1)[0][1] / len(formats) if formats else 0.5
        )
        hook_agreement = (
            Counter(hooks).most_common(1)[0][1] / len(hooks) if hooks else 0.5
        )
        return round(0.45 * topic_agreement + 0.30 * format_agreement + 0.25 * hook_agreement, 4)

    def _synthesize_emergent_niche(
        self,
        trend: OrganTrendDescription,
        trace: LayaTypedDecisionTrace,
        cohesion: float,
    ) -> NicheCluster:
        usable = [r for r in trend.records if r.status != "unsupported_language"] or trend.records
        token_counts: Counter[str] = Counter()

        for rec in usable:
            if rec.features.topic:
                for tok in re.findall(r"[a-z0-9]{3,}", rec.features.topic.lower()):
                    if tok not in STOPWORDS:
                        token_counts[tok] += 3
            for tag in rec.elements.hashtags:
                clean = tag.lower().lstrip("#")
                if len(clean) >= 3 and clean not in STOPWORDS:
                    token_counts[clean] += 2
            for seq in rec.elements.text_sequences:
                for tok in seq.tokens:
                    t_clean = tok.lower()
                    if len(t_clean) >= 3 and t_clean not in STOPWORDS:
                        token_counts[t_clean] += 1
            if rec.visual.summary:
                for tok in re.findall(r"[a-z0-9]{4,}", rec.visual.summary.lower()):
                    if tok not in STOPWORDS:
                        token_counts[tok] += 1

        for motif in trend.shared_elements:
            for tok in re.findall(r"[a-z0-9]{3,}", motif.lower()):
                if tok not in STOPWORDS:
                    token_counts[tok] += 2

        top_keywords = [kw for kw, _ in token_counts.most_common(8)]
        dominant_topic = (
            trend.dominant_features.topic
            if trend.dominant_features and trend.dominant_features.topic
            else trend.title
        )
        clean_title = dominant_topic.replace("_", " ").strip().title()
        if "Niche" not in clean_title and len(clean_title.split()) <= 3:
            display_name = f"{clean_title} Micro-Niche"
        else:
            display_name = clean_title

        niche_id = f"emergent-{_slugify(clean_title)}"
        emergent_conf = round(min(0.86, max(0.56, 0.52 + cohesion * 0.32)), 4)

        return NicheCluster(
            niche_id=niche_id,
            name=display_name,
            origin="emergent_cluster",
            description=(
                f"Dynamically synthesized emergent niche from shared organ v1.2 signals "
                f"({', '.join(top_keywords[:4]) or 'multi-modal motifs'}) outside seed taxonomy."
            ),
            taxonomy_source="convaiinnovations/laya-hybrid-emergent-v1",
            confidence=emergent_conf,
            cohesion_score=cohesion,
            keywords=top_keywords,
            matched_trend_ids=[trend.trend_id],
            commercial_categories=["Emerging Consumer Category", "Creator-Led Vertical"],
        )

    def _find_mergeable_emergent(
        self, candidate: NicheCluster, existing_map: dict[str, NicheCluster]
    ) -> str | None:
        cand_set = set(candidate.keywords[:6])
        for nid, cluster in existing_map.items():
            if cluster.origin != "emergent_cluster":
                continue
            overlap = cand_set.intersection(cluster.keywords[:6])
            if nid == candidate.niche_id or len(overlap) >= 2:
                return nid
        return None
