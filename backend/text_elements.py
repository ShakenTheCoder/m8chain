"""Retain language literally; matching hints never replace original text."""

import re
import unicodedata
from .models import Analysis, ContentDescription, NumericExpression, TextSequence

TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
DIGITS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "unu": "1", "doi": "2", "trei": "3", "patru": "4", "cinci": "5",
    "sase": "6", "sapte": "7", "opt": "8", "noua": "9",
}


def normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", normalize_text(text))
                   if unicodedata.category(c) != "Mn")


def sequence(text: str, source: str, start=None, end=None) -> TextSequence:
    normalized = normalize_text(text)
    return TextSequence(source=source, text=text, normalized=normalized, folded=fold(text),
                        tokens=TOKEN.findall(normalized), start_seconds=start, end_seconds=end)


def numeric_expressions(item: TextSequence) -> list[NumericExpression]:
    """Store generic digit-word runs as ambiguous candidate aliases, not named memes."""
    tokens = list(TOKEN.finditer(item.text))
    groups = []
    current = []
    for token in tokens:
        value = fold(token.group())
        recognized = value in DIGITS or value.isascii() and value.isdigit()
        contiguous = not current or re.fullmatch(r"[\s\-–—]*", item.text[current[-1].end():token.start()])
        if not recognized or not contiguous:
            if current:
                groups.append(current)
            current = []
        if recognized:
            current.append(token)
    if current:
        groups.append(current)
    output = []
    for group in groups:
        literal = group[0].group()
        if len(group) == 1 and not literal.isdigit():
            continue
        digits = "".join(DIGITS.get(fold(t.group()), fold(t.group())) for t in group)
        if len(digits) > 12:
            continue
        output.append(NumericExpression(source=item.source, text=item.text[group[0].start():group[-1].end()],
                                        compact_digits=digits, start_seconds=item.start_seconds))
    return output


def retain_text_elements(record: Analysis):
    sequences = []
    transcript = record.elements.transcript
    if transcript.segments:
        sequences.extend(sequence(s.text, "transcript", s.start_seconds, s.end_seconds) for s in transcript.segments)
    elif transcript.text:
        sequences.append(sequence(transcript.text, "transcript"))
    if record.elements.post_description:
        sequences.append(sequence(record.elements.post_description, "post_description"))
    sequences.extend(sequence(t.text, "on_screen_text", t.timestamp_seconds) for t in record.elements.on_screen_text.items)
    record.elements.text_sequences = sequences
    record.elements.numeric_expressions = [expression for item in sequences for expression in numeric_expressions(item)]


def describe_evidence(record: Analysis):
    parts, sources = [], []
    if record.visual.status == "complete" and record.visual.summary:
        parts.append("In the sampled frames: " + record.visual.summary)
        sources.append("sampled_frames")
    if record.elements.transcript.text:
        # This quotes the recognizer output. It is not a corrected or translated transcript.
        text = record.elements.transcript.text
        excerpt = text[:600] + ("…" if len(text) > 600 else "")
        parts.append("Speech transcript excerpt: «" + excerpt + "».")
        sources.append("transcript")
    if record.elements.on_screen_text.items:
        # Repeated overlays remain separate timestamped observations in elements.
        texts = list(dict.fromkeys(t.text for t in record.elements.on_screen_text.items))
        parts.append("Recognized on-screen text: «" + " | ".join(texts) + "».")
        sources.append("on_screen_text")
    if not parts and record.elements.post_description:
        parts.append("Post description: «" + record.elements.post_description + "».")
        sources.append("post_description")
    record.description = ContentDescription(text=" ".join(parts) or None, sources=sources)
