"""Laya's typed decisions over text; no generated summaries or visual claims."""

from functools import lru_cache
import math
from .models import Decision, Features

QUESTIONS = {
    "topic": {
        "type": "choice",
        "instructions": "Which topic is most directly supported by this post's text? Select unknown if unclear.",
        "criteria": {
            "beauty": "Skincare, cosmetics, makeup or hair care.",
            "food": "Cooking, recipes, food or drinks.",
            "fitness": "Exercise, sport or physical training.",
            "fashion": "Clothes, outfits or accessories.",
            "technology": "Software, electronics or digital tools.",
            "business": "Marketing, selling or running a business.",
            "other": "A clear topic outside these categories.",
            "unknown": "The text does not establish a topic.",
        },
    },
    "hook_type": {
        "type": "choice",
        "instructions": "Classify only the opening spoken text. Select unknown if the opening is unavailable.",
        "criteria": {
            "question": "Opens by asking the viewer a question.",
            "problem_solution": "Opens with a problem or mistake and offers help.",
            "claim": "Opens with an assertion or surprising fact.",
            "story": "Opens by telling a personal story or event.",
            "other": "A different identifiable opening.",
            "unknown": "No opening text or insufficient evidence.",
        },
    },
    "format": {
        "type": "choice",
        "instructions": "Infer the content format from text only; do not assume unseen visuals.",
        "criteria": {
            "tutorial": "Teaches steps, tips or how to do something.",
            "review": "Evaluates or compares a product or service.",
            "testimonial": "Shares a personal experience with a product or service.",
            "story": "Narrates an event or experience.",
            "other": "Another clear content format.",
            "unknown": "Insufficient text to infer a format.",
        },
    },
    "call_to_action": {
        "type": "choice",
        "instructions": "Which explicit viewer action is requested? Select none if no explicit request exists.",
        "criteria": {
            "engage": "Explicitly asks to like, save, share or comment.",
            "follow": "Explicitly asks to follow or subscribe.",
            "visit": "Explicitly asks to open a link, website or profile.",
            "purchase": "Explicitly asks to buy, book or order.",
            "none": "No explicit viewer action is requested.",
            "unknown": "The available text is insufficient.",
        },
    },
}


@lru_cache(maxsize=1)
def load_agent(model: str, device: str):
    from laya import Agent
    # Explicit checkpoint keeps this on the Laya encoder, not its optional Vega engine.
    return Agent(model, device=device)


def classify(description: str | None, transcript: str, opening: str | None,
             model: str, device: str, threshold: float) -> tuple[Features, bool]:
    agent = load_agent(model, device)
    state = transcript + ("\n\nPost description:\n" + description if description else "")
    # Record truncation explicitly; long inputs must not silently lose their context.
    max_len = 8192
    result = agent.predict(state, {key: value for key, value in QUESTIONS.items() if key != "hook_type"}, max_len=max_len)
    answers = dict(result["answers"])
    truncated = bool(result.get("usage", {}).get("truncated", False))
    if opening:
        hook_result = agent.predict(opening, {"hook_type": QUESTIONS["hook_type"]}, max_len=max_len)
        answers["hook_type"] = hook_result["answers"]["hook_type"]
        truncated = truncated or bool(hook_result.get("usage", {}).get("truncated", False))
    decisions = {}
    for name, question in QUESTIONS.items():
        if name == "hook_type" and not opening:
            continue
        answer = answers[name]
        probabilities = {key: float(value) for key, value in answer["probabilities"].items()}
        if set(probabilities) != set(question["criteria"]) or any(
            not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities.values()
        ):
            raise ValueError("Invalid Laya probability distribution")
        choice = answer["choice"]
        confidence = probabilities[choice]
        review = confidence < threshold or choice == "unknown" or bool(answer.get("abstain"))
        decisions[name] = Decision(
            label="unknown" if review else choice,
            confidence=confidence, probabilities=probabilities, needs_review=review,
        )
    return Features(
        **decisions, opening_text=opening,
        evidence_sources=["transcript"] + (["post_description"] if description else []),
    ), truncated
