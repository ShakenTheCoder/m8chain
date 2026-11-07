# Candidate trend grouping

The `/trends` page reads saved analyses through `GET /api/organ/trends`, proxied to Python `GET /trends`. `backend/trends.py` owns matching, grouping, classification, evidence, and suggested execution guides. `trend.schema.json` and `GET /trends/schema` describe each trend record.

A trend currently means a **candidate recurring pattern**, not demonstrated growth or virality. At least two distinct video IDs are required. Repeated analyses cannot create extra support. No example records are inserted into the database.

## Matching and assignment

- Sound: exact, nonempty platform sound ID; weight 35/90 (38.89%). Titles alone never establish identity. This is not audio fingerprinting.
- Spoken script: weight 30/90 (33.33%).
- On-screen text: weight 12/90 (13.33%).
- Post caption: weight 8/90 (8.89%).
- Visual description: weight 5/90 (5.56%).

Text similarity blends 50% normalized token-set Jaccard overlap and 50% multilingual embedding cosine similarity, clamped to 0–1. Eligibility requires at least two informative words (four for visual descriptions). A connection needs combined similarity >=0.20 plus either informative word overlap (at least two shared words, Jaccard >=0.15) or meaning similarity >=0.80. It is strong at combined >=0.80 for text or >=0.75 for visual descriptions. Exact sound IDs always connect independently of text. Evidence keeps pair-specific wording, meaning, combined score, basis, and strength; paraphrases are never presented as verbatim shared scripts. Comparisons use up to 500 words per field. Visual descriptions remain model inferences about sampled frames.

One qualifying signal can establish a pair. Weights rank groups, rather than preventing script-only or caption-only patterns. Matching scores sum qualified weighted similarities and average over all pairs in a group; they are not calibrated probabilities. Sound has the largest individual weight. Relative weights 35:30:12:8:5 total 90 and are normalized to 100%, preserving their proportions. Scoring uses full precision; the page displays percentages to two decimal places.

Groups require strong evidence for the same specific cue; weak graph similarities never establish candidate membership. Sound groups share an exact platform ID. Other cues are keyed by signal and matching evidence value. For each cue, deterministic greedy complete-link assignment requires every pair in a group to support that cue. Groups can overlap across cues, but an A–B–C path alone cannot establish a three-clip trend. This bounded algorithm favors precision and does not enumerate every possible overlapping clique. Groups with identical memberships combine their defining cues. Scores average the supporting pair evidence; IDs hash sorted video IDs.

Generic visual staging (a person indoors facing a camera, clothing/background words) is removed for visual eligibility; at least four remaining distinct informative words are required. This deliberately favors precision over recall. Text and meaning thresholds remain heuristic, so candidate groups still need review.


## Scope and limits

Graph and trend comparisons use all saved videos from the same database revision. The earlier 1,000-record trend cap has been removed so all saved videos are considered for matching. The optional storage query limit remains available to other callers. Each successful insert of a distinct analyzed video invalidates a persisted trend snapshot via a SQLite trigger. The save path immediately rebuilds the snapshot before the analysis job completes. Reusing a saved video does not insert or recompute. Concurrent rebuilds serialize and recheck the revision, so readers never publish an older snapshot over newer data. GET /trends and the Refresh button reuse the published snapshot; the open page checks every three seconds and updates when its revision changes. This polling retrieves results and does not set the analysis frequency. No aggregation is written back to the analyses table.

The snapshot lives in trend_state alongside a source revision and computed revision. Inserts and invalidation commit together. If rebuilding fails or the process exits after the video commits, the saved analysis remains intact, the revision stays dirty, and the next snapshot request retries. Existing databases bootstrap a snapshot on first access. Snapshots survive restarts; a grouping method version change also invalidates them. Direct SQL inserts mark the snapshot dirty but bypass the application save hook, so they rebuild on the next request. The supported ingestion path is AnalysisStore.save.

Guides are deterministic suggestions based on the matched sound, phrases, or visual descriptions. They preserve evidence references and distinguish recognizable elements from adaptable details. They do not infer unavailable choreography, audio timing, success forecasts, or growth. Meaning similarities can suggest paraphrases and translated wording; they are not proof of equivalent meaning. Re-recorded sounds still need audio fingerprinting, and variable-slot templates need further validation.

Validation: `python -m pytest` covers exact sound identity, priority weighting, text/visual matches, deduplication, relationship-chain grouping, generic text rejection, determinism, guides, and the saved-database API. Frontend gates: `npm run typecheck` and `npm run build`.


## Video connection graph

`/graph` visualizes every distinct saved video, including isolated videos. `GET /graph` returns nodes and pairwise edges from the persisted snapshot. Graph and trend generation read the same complete set of saved records. It runs on the same per-new-save rebuild; the page picks up changed revisions every three seconds. `/trends` omits the graph payload to keep ordinary trend reads smaller.

Solid edges show strong matching evidence. Dashed edges expose weaker lexical/semantic similarities for exploration and do not establish trends. The graph defaults to strong edges, with weak edges available through its filter. Deterministic grid placement keeps nodes apart and orders neighbors nearby; captions appear in the inspector and native tooltips rather than overlapping the map. Narrow screens scroll the map to preserve node spacing. Graph proximity is for layout only; edge evidence explains actual relationships.

Current graph comparisons are pairwise across all saved videos, appropriate for the demo library; large libraries will need indexed candidate generation and viewport rendering. Semantic similarity is approximate. Re-recorded audio is not fingerprinted, and cross-language equivalence is not guaranteed.


## Importing real trend examples

`python -m backend.import_trends --directory <collection-directory> --per-trend 7 --minutes 60` resumes an English example import from actual Apify collection files. It reuses the same `analyze_collected` pipeline as single-URL analysis, avoiding a second paid collection for each candidate. It verifies detected English speech, a nonempty transcript, and content supporting the intended source trend; it never assigns group membership from the discovery query alone. The manifest distinguishes accepted clips from rejected/failed attempts and excludes videos present before the import. Accepted records save through the ordinary store, refreshing graph and trends after each new clip. Raw collection and import manifests belong in ignored `.data/imports/`, not project documentation.


## Semantic encoder implementation

Meaning matching uses the local multilingual `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` checkpoint at revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`. Original text is split into overflowing 128-subword-token chunks, mean-pooled with attention masks, combined by token count, and unit-normalized. Comparisons use up to 500 original whitespace-separated words; wording retains the existing normalized-token representation. Unique texts are batched, with up to 8,192 vectors reused in memory. Model weights download on first use. Semantic failures return HTTP 503 for graph/trend reads rather than silently substituting lexical-only scores; saved analyses remain intact.

Unit tests use controlled vectors without model downloads. Separate real-model smoke checks covered English paraphrases, English/Romanian equivalents, and an unrelated sentence, including the exact 50/50 pairwise score formula. Semantic similarity is approximate and may miss negation, slang, or joke context. The blend does not bypass the current strength and trend-membership rules.
