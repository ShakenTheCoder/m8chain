"""Deterministic, evidence-backed candidate trends over saved analyses."""
from collections import Counter
from hashlib import sha256
from itertools import combinations
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field
from .semantic import MODEL_ID, MODEL_REVISION, cosine, embed_texts

_RELATIVE_WEIGHTS = {"sound": 35, "script": 30, "subtitles": 12, "caption": 8, "visual": 5}
WEIGHTS = {signal: value / sum(_RELATIVE_WEIGHTS.values()) for signal, value in _RELATIVE_WEIGHTS.items()}
METHOD = "shared-elements-v8-supported-cues"
TEXT_MATCHING = {"wording_weight": .5, "meaning_weight": .5, "semantic_model": MODEL_ID,
                 "model_revision": MODEL_REVISION, "semantic_metric": "cosine_clamped_0_1"}


class Evidence(BaseModel):
    signal: Literal["sound", "script", "subtitles", "caption", "visual"]
    value: str
    clip_ids: list[str]
    similarity: float = Field(ge=0, le=1)
    strength: Literal["strong", "weak"] = "strong"
    lexical_similarity: float | None = Field(default=None, ge=0, le=1)
    semantic_similarity: float | None = Field(default=None, ge=0, le=1)
    basis: Literal["sound", "wording", "meaning", "both"] = "wording"


class TrendClip(BaseModel):
    analysis_id: str
    video_id: str
    url: str
    caption: str | None = None
    creator_id: str | None = None


class Guide(BaseModel):
    specific_to_trend: list[str]
    steps: list[str]
    can_adapt: list[str]
    review_before_posting: list[str]


class Trend(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str
    title: str
    classification: Literal["sound", "script", "subtitles", "caption", "visual", "mixed"]
    status: Literal["candidate"] = "candidate"
    method: str = METHOD
    matching_score: float = Field(ge=0, le=1)
    signal_weights: dict[str, float] = Field(default_factory=lambda: dict(WEIGHTS))
    creator_count: int
    clips: list[TrendClip]
    evidence: list[Evidence]
    execution_guide: Guide
    limitations: list[str]


def words(text):
    folded = unicodedata.normalize("NFKD", (text or "").casefold())
    return re.findall(r"[^\W_]+", "".join(c for c in folded if not unicodedata.combining(c)), re.UNICODE)


def prepare(record):
    elements = record.get("elements") or {}
    sound = elements.get("sound") or {}
    texts = {
        "script": (elements.get("transcript") or {}).get("text") or "",
        "caption": elements.get("post_description") or "",
        "subtitles": " ".join(x.get("text", "") for x in (elements.get("on_screen_text") or {}).get("items", [])),
        "visual": (record.get("visual") or {}).get("summary") or "",
    }
    # Bound comparison work; full analyses remain available through clip links.
    tokens = {key: words(value)[:500] for key, value in texts.items()}
    return {"record": record, "texts": texts, "tokens": tokens,
            "semantic_texts": {key: " ".join(value.split()[:500]) for key, value in texts.items()},
            "sets": {key: set(value) for key, value in tokens.items()},
            "sound_id": str(sound["id"]) if sound.get("id") and str(sound["id"]) != "0" else None,
            "sound_title": sound.get("title")}


def phrase(a, b):
    """A shared contiguous phrase, rather than only shared topic words."""
    for size in range(min(12, len(a), len(b)), 2, -1):
        candidates = {tuple(b[i:i + size]) for i in range(len(b) - size + 1)}
        for i in range(len(a) - size + 1):
            chunk = tuple(a[i:i + size])
            if chunk in candidates:
                return " ".join(chunk)
    return None


COMMON_WORDS = set("a an the and or but to of in on at for with is it this that my your i you we they he she as be are was by from video tiktok fyp fy foryou viral trending goviral trend original sound de la si pe un o cu din este eu tu sa ca se nu ma am ce care e ai meu tau".split())


GENERIC_VISUAL_WORDS = set("person people man woman stands standing sitting sits indoors room camera facing talking wearing shirt background visible appears shows video image frame scene front looking young seen white black wall walls floor hand hands".split())


def _eligible(item, signal):
    informative = item["sets"][signal] - COMMON_WORDS
    if signal == "visual":
        informative -= GENERIC_VISUAL_WORDS
    return len(informative) >= (4 if signal == "visual" else 2)


def prepare_semantics(items):
    if len(items) < 2:
        return
    texts = [item["semantic_texts"][signal] for item in items for signal in item["texts"] if _eligible(item, signal)]
    vectors = embed_texts(texts)
    for item in items:
        item["embeddings"] = {signal: vectors.get(text) for signal, text in item["semantic_texts"].items()}


def relationship(a, b):
    """One 50/50 wording/meaning policy for graph edges and trend groups."""
    if "embeddings" not in a or "embeddings" not in b:
        prepare_semantics([a, b])
    evidence, scores = [], {}
    ids = [a["record"]["id"], b["record"]["id"]]
    if a["sound_id"] and a["sound_id"] == b["sound_id"]:
        scores["sound"] = 1.0
        evidence.append(Evidence(signal="sound", value=f'{a["sound_title"] or "Shared audio"} (sound ID {a["sound_id"]})',
                                 clip_ids=ids, similarity=1, basis="sound"))
    for signal in ["script", "subtitles", "caption", "visual"]:
        if not _eligible(a, signal) or not _eligible(b, signal):
            continue
        left, right = a["sets"][signal], b["sets"][signal]
        lexical = len(left & right) / len(left | right)
        semantic = cosine(a["embeddings"][signal], b["embeddings"][signal])
        similarity = .5 * lexical + .5 * semantic
        informative_left, informative_right = left - COMMON_WORDS, right - COMMON_WORDS
        shared = informative_left & informative_right
        wording_match = len(shared) >= 2 and len(shared) / len(informative_left | informative_right) >= .15
        meaning_match = semantic >= .80
        if similarity < .20 or not (wording_match or meaning_match):
            continue
        strength = "strong" if similarity >= (.75 if signal == "visual" else .80) else "weak"
        common_phrase = phrase(a["tokens"][signal], b["tokens"][signal])
        if strength == "strong" and common_phrase:
            value = common_phrase
        elif wording_match:
            value = ", ".join(sorted(shared)[:16])
        else:
            value = f'Similar meaning: “{a["semantic_texts"][signal][:240]}” ↔ “{b["semantic_texts"][signal][:240]}”'
        basis = "both" if wording_match and meaning_match else "meaning" if meaning_match else "wording"
        scores[signal] = similarity
        evidence.append(Evidence(signal=signal, value=value, clip_ids=ids, similarity=similarity, strength=strength,
                                 lexical_similarity=lexical, semantic_similarity=semantic, basis=basis))
    return round(sum(WEIGHTS[key] * value for key, value in scores.items()), 4), evidence


def guide(evidence):
    specifics, steps = [], ["Open the linked clips and compare the shared elements below. Check which clips support each element; a clip may participate in more than one trend."]
    signals = {item.signal for item in evidence}
    for signal in WEIGHTS:
        examples = [item.value for item in evidence if item.signal == signal]
        if not examples:
            continue
        example = Counter(examples).most_common(1)[0][0]
        matching_items = [item for item in evidence if item.signal == signal and item.value == example]
        if all(item.basis == "meaning" for item in matching_items):
            specifics.append(f"Similar meaning in {signal}: {example}.")
            steps.append("Compare the linked wording in context. Express the shared idea in your own words; this evidence does not establish an identical phrase.")
            continue
        if all(item.strength == "weak" for item in matching_items):
            specifics.append(f"Shared {signal} words: {example}. This is a weaker similarity to review in context.")
            steps.append(f"Compare the source clips sharing these {signal} words: {example}. Identify the common idea in the originals before deciding which wording or visual element to reuse.")
            continue
        if signal == "sound":
            specifics.append(f"Shared TikTok sound: {example}.")
            steps.append("Open a linked clip in TikTok, tap its sound, and use that same sound. Match your cuts or delivery to the relevant audio cue after reviewing the clips.")
        elif signal == "visual":
            specifics.append(f"Similar sampled visual content: {example}")
            steps.append("Use the linked clips to identify the recurring setting, props, or action. Recreate that visual idea; check the full videos for movement and timing that still frames cannot establish.")
        else:
            name = {"script": "spoken script", "subtitles": "on-screen text", "caption": "post caption"}[signal]
            specifics.append(f'Shared {name} phrase (normalized for matching): “{example}”.')
            steps.append(f'Use the shared {name} phrase “{example}” as your starting point. Check the linked originals for exact wording, spelling, and context before adapting it.')
    steps.append("Record your version, then compare it with the source clips to check that the defining shared elements are still recognizable.")
    adapt = ["Your subject, product, location, and personal perspective, while keeping the shared elements recognizable."]
    if "sound" not in signals:
        adapt.append("Audio choice: these clips were grouped without a verified shared sound ID.")
    return Guide(specific_to_trend=specifics, steps=steps, can_adapt=adapt,
                 review_before_posting=["This is a suggested execution guide derived from matching evidence, not a verified recipe for performance.",
                                        "Review each source clip; shared phrases may occur in different contexts."])


def extract_trends(records):
    # Defensive deduplication: repeat analyses of one video cannot form a trend.
    unique = {}
    for record in sorted(records, key=lambda r: r["id"]):
        vid = (record.get("video") or {}).get("id")
        if vid and vid not in unique:
            unique[vid] = prepare(record)
    items = list(unique.values())
    prepare_semantics(items)
    edges = {}
    cue_members = {}
    for i, j in combinations(range(len(items)), 2):
        score, evidence = relationship(items[i], items[j])
        # Exploratory weak graph edges are not sufficient trend evidence.
        evidence = [item for item in evidence if item.strength == "strong"]
        if evidence:
            edges[i, j] = (score, evidence)
            for item in evidence:
                # A trend needs one specific, strongly supported recurring cue.
                cue = (item.signal, items[i]["sound_id"]) if item.signal == "sound" else (item.signal, item.value)
                cue_members.setdefault(cue, set()).update((i, j))
    groups = {}
    for cue, members in cue_members.items():
        # Complete-link groups: every pair must support this same cue.
        # Deterministic greedy assignment avoids exponential clique enumeration.
        clusters = []
        for member in sorted(members):
            for cluster in clusters:
                if all(any((item.signal, items[min(member, other)]["sound_id"] if item.signal == "sound" else item.value) == cue
                           for item in edges.get(tuple(sorted((member, other))), (0, []))[1])
                       for other in cluster):
                    cluster.append(member)
                    break
            else:
                clusters.append([member])
        for cluster in clusters:
            if len(cluster) >= 2:
                groups.setdefault(tuple(cluster), set()).add(cue)
    trends = []
    for group, cues in groups.items():
        pairs = []
        for i, j in combinations(group, 2):
            if (i, j) not in edges:
                continue
            matched = []
            for item in edges[i, j][1]:
                cue = (item.signal, items[i]["sound_id"]) if item.signal == "sound" else (item.signal, item.value)
                if cue in cues:
                    matched.append(item)
            if matched:
                by_signal = {}
                for item in matched:
                    by_signal[item.signal] = max(by_signal.get(item.signal, 0), item.similarity)
                score = sum(WEIGHTS[signal] * value for signal, value in by_signal.items())
                pairs.append((score, matched))
        # Merge identical evidence while retaining the exact supporting clips.
        merged = {}
        for _, pair_evidence in pairs:
            for item in pair_evidence:
                # Hybrid scores belong to an exact pair; do not merge unrelated pair scores.
                key = (item.signal, item.value) if item.signal == "sound" else (item.signal, item.value, tuple(item.clip_ids))
                if key not in merged:
                    merged[key] = {"ids": set(), "similarity": item.similarity, "strength": item.strength,
                                   "lexical_similarity": item.lexical_similarity, "semantic_similarity": item.semantic_similarity,
                                   "basis": item.basis}
                merged[key]["ids"].update(item.clip_ids)
                merged[key]["similarity"] = min(merged[key]["similarity"], item.similarity)
        evidence = [Evidence(signal=key[0], value=key[1], clip_ids=sorted(value["ids"]), similarity=value["similarity"], strength=value["strength"],
                             lexical_similarity=value["lexical_similarity"], semantic_similarity=value["semantic_similarity"], basis=value["basis"])
                    for key, value in merged.items()]
        evidence.sort(key=lambda e: (-WEIGHTS[e.signal], -len(e.clip_ids), e.value))
        signals = {item.signal for item in evidence}
        primary = evidence[0]
        classification = "mixed" if len(signals) > 1 else primary.signal
        title = {"sound": "Shared sound", "script": "Shared script", "caption": "Shared caption", "subtitles": "Shared on-screen text", "visual": "Shared visual idea"}[primary.signal]
        if primary.strength == "weak":
            title = {"script": "Script similarity", "caption": "Caption similarity", "subtitles": "On-screen text similarity", "visual": "Visual similarity"}.get(primary.signal, title)
        clips = []
        for i in sorted(group, key=lambda i: items[i]["record"]["id"]):
            record = items[i]["record"]
            video = record["video"]
            clips.append(TrendClip(analysis_id=record["id"], video_id=video["id"], url=video["url"], creator_id=video.get("creator_id"), caption=(record.get("elements") or {}).get("post_description")))
        digest = sha256("|".join(sorted(c.video_id for c in clips)).encode()).hexdigest()[:16]
        limitations = ["Repeated elements establish a candidate pattern, not growth or virality.",
                       "Sound matching uses exact platform sound IDs, not audio fingerprints.",
                       "Text similarity is 50% word overlap and 50% multilingual embedding similarity; meaning scores are approximate, not proof of equivalence.",
                       "Every pair in a group strongly supports the same specific cue. Weak similarities do not establish trends; groups with different cues can overlap."]
        if "visual" in signals:
            limitations.append("Visual matches compare model descriptions of sampled frames, not full-video action sequences.")
        trends.append(Trend(id=f"trend-{digest}", title=f"{title}: {primary.value[:100]}", classification=classification,
                            matching_score=round(sum(score for score, _ in pairs) / len(pairs), 4),
                            creator_count=len({c.creator_id for c in clips if c.creator_id}), clips=clips, evidence=evidence,
                            execution_guide=guide(evidence), limitations=limitations))
    trends.sort(key=lambda t: (-t.matching_score, -len(t.clips), t.id))
    grouped = {clip.video_id for trend in trends for clip in trend.clips}
    return {"schema_version": "1.0", "method": METHOD, "signal_weights": WEIGHTS, "text_matching": TEXT_MATCHING,
            "analyzed_videos": len(items), "grouped_videos": len(grouped), "ungrouped_videos": len(items) - len(grouped),
            "trends": [trend.model_dump() for trend in trends]}
