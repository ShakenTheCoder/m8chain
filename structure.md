# Organ structure — retain evidence before detecting trends

An Organ is one TikTok video post. Its output describes the post and preserves its elements so a later aggregation step can compare posts across creators and time windows. Broad topic or format labels supplement those elements; they cannot describe a repeated joke, phrase, sound, or action by themselves.

The implemented contract is schema **v1.2**, defined in [backend/models.py](backend/models.py) and exported to [output.schema.json](output.schema.json). [public/sample-output.json](public/sample-output.json) is an illustrative record, not a real TikTok analysis. See [README.md](README.md) for setup and limits.

## What we retain and return

| Section | Contents | Evidence and limits |
| --- | --- | --- |
| `video` | Video ID, URL, creator ID, publication time, duration | Collected metadata; unavailable values stay null |
| `collection` | Collection time, Actor run ID, submitted URL | Distinct from publication time |
| `language` | Dominant speech language, detection confidence, English/Romanian support verdict | Detection confidence does not establish transcript accuracy |
| `elements.transcript` | Original ASR text, model name, timed segments | No censorship, translation, or rewriting; recognition can be wrong |
| `elements.post_description` | Original post description | Separate from speech and visible text |
| `elements.on_screen_text` | Recognized text and source model | Best-effort contact-sheet reading; frame index and timestamp remain null because text is not localized |
| `elements.sound` | Platform sound ID, title, author, original-sound flag | Metadata only; no perceptual audio matching yet |
| `elements.hashtags` | Normalized hashtags | Names without the hash sign |
| `elements.text_sequences` | Original text, normalized and diacritic-folded forms, ordered tokens, source, available timestamps | Enables later substring, suffix, and phrase comparisons without losing the original |
| `elements.numeric_expressions` | Original digit expression and ambiguous compact-digit hint | Generic digit words, not a list of known trends; hints require later validation |
| `visual` | Scene summary and ordered timestamped frame references | Up to eight sampled frames; action localization is explicitly not analyzed |
| `description` | Visual summary and attributed original-text excerpts | A transcript alone never becomes a visual claim |
| `media_evidence` | Retained source-video path and SHA-256; frame paths in `visual.frames` | Local review files, retained by default; configurable off |
| `observation` | Views, likes, shares, comments, saves, observation time, like/share rates | Missing is null; zero remains zero; one snapshot is not growth |
| `features` | Laya topic, hook, format, viewer-action decisions and distributions | Inferences supplementary to the retained elements |
| `classifier` | Checkpoint, taxonomy version, status, threshold, truncation flag | Marketing classifications still need domain evaluation |
| `limitations` | Skipped, uncertain, failed, or unavailable components | No fabricated elements when a stage fails |

## Preserve wording before normalizing

For a transcript segment containing the user-provided example `Școala pulii!`, a text sequence looks like this (times are illustrative):

```json
{
  "source": "transcript",
  "text": "Școala pulii!",
  "normalized": "școala pulii!",
  "folded": "scoala pulii!",
  "tokens": ["școala", "pulii"],
  "start_seconds": 1.2,
  "end_seconds": 2.4
}
```

The extractor does not censor `pulii`, change its grammatical form, or translate it to an English swear word. A later process can discover that `școala pulii` and `jobul pulii` share a suffix and potentially a phrase structure with a variable slot. A single-video analysis does not declare that `{noun} pulii` is a trend.

For spoken `six seven`, the numeric hint is:

```json
{
  "source": "transcript",
  "text": "six seven",
  "compact_digits": "67",
  "start_seconds": 2.0,
  "match_hint_only": true
}
```

The generic process can also produce a `67` hint from `șase șapte`, `6-7`, or literal `67`, and a `24` hint from `two four`. It does not equate their meanings automatically: separate digits and a whole number are ambiguous. Preserve the original text, sound metadata, and surrounding context to resolve candidates later.

## Describe action-based videos with evidence

For the user's example of entering a room and uttering a phrase, retain these independent pieces when supported by the actual media:

- The recognized original phrase and its transcript time range.
- What is visible at each sampled frame time.
- A scene description of the sampled visual evidence. Precise entrance/action intervals are not extracted in this POC.
- Any legible on-screen text, preserving the original wording. Text localization stays null rather than inventing a frame timestamp.
- The supplied sound ID and title, even if another creator re-recorded a similar phrase.

The image-only model must not infer shouting or anger from a phrase or still frame. `visual.audio_delivery` and `visual.action_localization` are explicitly `not_analyzed`. Vocal delivery and perceptual audio fingerprints need a separate audio stage. Sparse sampling can miss a quick entrance; descriptions must not imply complete video coverage. Structured action intervals can be added later; the initial detailed visual schema exhausted the local model's token budget, so this POC uses a bounded summary-and-text response.

## Processing and storage

1. Collect one post and download its video through Apify.
2. Transcribe speech and detect its dominant language. Unsupported speech returns `unsupported_language`; low-confidence or absent speech remains explicit.
3. Describe up to eight ordered frames with a local vision model, including dense opening coverage. Silent videos can still receive a visual description.
4. Retain literal text sequences and matching hints. Compose a readable description with source attribution.
5. Add Laya classifications for supported English/Romanian speech when language confidence is sufficient.
6. Persist the JSON, raw Actor output, and (by default) source video and sampled frames once per TikTok video. Repeated links reuse the saved entry. Opening a saved result does not refresh its engagement observation; future refreshes should append observations under the same video identity.

Models validate data shape and frame references; they do not guarantee interpretation accuracy. A complete status means required stages executed, not that all inferences are correct. Missing components return a partial record with limitations.

## Later: determine whether a trend forms

Compare common phrases, learned phrase templates, sound IDs, and described actions across distinct posts and creators. Measure changes in occurrence share across comparable publication windows; repeated observations support engagement growth measurements. Deduplicate posts found through multiple queries, and keep collection strategy comparable between windows.

A matching numeric hint, shared profanity, or a single high view count is insufficient by itself. Keep candidate matches explainable with original text, frames, sounds, timestamps, and example posts. Return insufficient evidence when the collection cannot support a growth claim.

## Implemented candidate trends

The `/trends` page now groups saved analyses into candidate recurring patterns, with source clips, matching evidence, suggested execution guides, and per-trend JSON. Growth is not inferred. See [the grouping decision](docs/decisions/trend-grouping.md) for weights, thresholds, assignment rules, and limits, and [trend.schema.json](trend.schema.json) for the trend contract.
