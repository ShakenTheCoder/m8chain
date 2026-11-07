# n8chain · Organ

Paste a public TikTok video URL to retain its speech, phrases, sound metadata, visible actions, on-screen text, and engagement. Apify collects the post, Whisper transcribes speech, a local Qwen vision model describes sampled frames, and Laya adds text classifications. The page shows a grounded description and the full JSON with copy/download controls.

Work for this component stays on `organ`. See [context.md](context.md) for the team workflow and [structure.md](structure.md) for the original analysis design.

## Run locally

Requires Node.js 20.9+, Python 3.11 or 3.12, [uv](https://docs.astral.sh/uv/), ffmpeg, and an Apify account with remaining credit. On macOS, install ffmpeg with `brew install ffmpeg`.

```sh
npm ci
uv sync --python 3.12
cp .env.example .env
```

Add your `APIFY_TOKEN` to `.env`. Keep the token in that ignored file. The browser never receives it. Restart the Python service after changing `.env`.

Start the Python service in one terminal:

```sh
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Start Next.js in another:

```sh
npm run dev
```

For visual descriptions, install [Ollama](https://ollama.com/) and run `ollama pull qwen3-vl:4b-instruct` once. Keep Ollama running at `http://127.0.0.1:11434`. This checkpoint is roughly 3.3 GB. `VISION_ENABLED=false` disables it, returning partial text/audio-only records with explicit limitations. This model is separate from Laya.

Open **http://127.0.0.1:3000**. The page also provides an explicitly labeled illustrative sample that works without an Apify token. Sample values are fictional, and its Laya and visual analysis are intentionally marked as not run.

The first real analysis downloads the Whisper and Laya model weights from Hugging Face; this can take several minutes and needs disk space for the weights. Later requests reuse the loaded models. The default CPU setup works on this Apple Silicon development machine; `LAYA_DEVICE=mps` or `cuda` can be configured on compatible hardware.

## What happens to a link

1. Validate a full TikTok video URL or a TikTok short link and remove tracking parameters. Short-link resolution depends on the Actor; if it fails, paste the expanded `/@creator/video/id` URL.
2. Run `clockworks/tiktok-scraper` for exactly one post with video downloads enabled, related videos disabled, and optional paid transcripts and AI descriptions disabled. Default per-run charge cap: $0.50, the actor's required minimum cap. This is a ceiling, not a fixed per-video charge. Lower caps are rejected before starting a run. Apify account credit and actor pricing still apply.
3. Download the Actor-stored video, extract mono audio with ffmpeg, then run `faster-whisper` using the multilingual `small` model by default.
4. Detect the dominant speech language without forcing English or Romanian. Only `en` and `ro` proceed to Laya. Language confidence below 0.70 stops classification and returns a partial record. Other detected languages return `unsupported_language`. Silence or unavailable speech returns a partial record, without guessing language from the post description.
5. Describe up to eight ordered frames with local `qwen3-vl:4b-instruct`, densely covering the opening seconds and then the later video. They are composed into one labeled contact sheet. Return a brief scene description and original visible text. Frame timestamps come from the extraction code; individual text locations and action intervals are not extracted. Frames are analyzed without the transcript to avoid priming visual descriptions from speech.
6. Retain original text without censorship, stemming, or translation. Add normalized and diacritic-folded strings, token sequences, and generic digit-word matching hints. These do not name a meme or declare a trend. Build a readable description from the visual summary and attributed transcript/visible-text excerpts.
7. Run the actual `convaiinnovations/laya-multilingual` checkpoint on the transcript and description. The hook question receives only the first transcribed sentence from an opening segment starting before five seconds. These broad classifications supplement the retained elements rather than replacing them.
8. Store one analysis per TikTok video in `.data/organ.sqlite3`. Repeated full links, tracking-parameter variants, and known short-link aliases reuse the saved result. Pending requests for the same known video share one job. A unique database index also prevents duplicate records when different short links resolve to the same video.

Laya and Whisper run in the Python process. Sampled images go to the configured local Ollama service. By default, original video and sampled JPEG frames are retained under `.data/evidence/{analysis_id}/`; the output provides relative evidence paths and a SHA-256 digest of the video for review. Temporary audio is deleted after extraction. `RETAIN_SOURCE_MEDIA=false` keeps only the structured records and raw Apify output. Retained media has no automatic cleanup yet; monitor disk usage during bulk collection. This POC does not yet aggregate records into trends.

## Output contract

[output.schema.json](output.schema.json) is the JSON Schema generated from [backend/models.py](backend/models.py), the source of truth. A validated illustrative record is available in [public/sample-output.json](public/sample-output.json).

| Section | Returned information |
| --- | --- |
| `video` | Platform, video ID, original link, creator ID, publication time, duration |
| `collection` | Apify run ID, collection timestamp, submitted URL |
| `language` | Detected speech language, detection confidence, allowed languages, support verdict |
| `elements` | Description, hashtags, timed speech transcript, sound metadata, recognized visible text (unlocalized), original text/token sequences, numeric matching hints |
| `description` | Visual summary and attributed original-text excerpts, with source attribution |
| `visual` | Scene description, timestamped frame references, model identity, sampled-coverage limit; action localization explicitly not analyzed |
| `media_evidence` | Retained source-video path and hash; frame paths appear alongside frame descriptions |
| `observation` | Views, likes, shares, comments, saves, observation timestamp, like/share rates |
| `features` | Laya topic, hook type, format, and viewer-action decisions with full class distributions and review flags; opening text and input sources |
| `classifier` | Exact checkpoint, execution status, taxonomy version, confidence threshold, truncation indicator |
| `limitations` | Missing inputs, skipped capabilities, model limitations, and other reasons to inspect the result |

Missing counters are `null`; zero remains zero. Rates are fractions, not percentages. A record can be `complete`, `partial`, or `unsupported_language`. Complete means required visual/text extraction and classification ran, not that the interpretations are guaranteed correct. Visual descriptions cover sampled frames, not every movement. The image-only model cannot establish that someone shouts, identify a sound, or prove an emotion; vocal delivery and perceptual audio fingerprinting are explicitly not analyzed. Recognized visible text is model output, not a verified transcription.

Pin the explicit `qwen3-vl:4b-instruct` tag. The generic `qwen3-vl:4b` tag resolved to thinking weights during diagnosis and exhausted its allowance before producing JSON on a real video, even with `think=false`. Increasing the allowance alone did not fix it. The visual stage allows up to 1,600 output tokens with a 90-second timeout; truncated responses are rejected.

Schema v1.2 adds these evidence fields; existing v1.1 records remain stored as originally returned. See [structure.md](structure.md) for how this evidence supports later phrase, sound, and action matching without hardcoded trends.

Laya is a typed text decision model, not a video transcription or free-text summary generator. Its taxonomy is defined in [backend/classifier.py](backend/classifier.py). Classifications below the provisional 0.60 confidence threshold become `unknown`, with original probabilities preserved. The marketing labels have not been fine-tuned or calibrated on a labeled dataset. Local smoke checks found some confident misclassifications; inspect results before using them for trend ranking or budget decisions. Mixed-language speech is not resolved per segment; language detection reports the dominant language.

Real local smoke checks on synthesized English and Romanian speech detected both languages correctly. The Romanian `base` transcript contained word errors, so the default is now the larger multilingual `small` checkpoint. `WHISPER_MODEL=base` remains available for faster startup with lower accuracy. Language-detection confidence is not a measure of transcription accuracy; retain and review the source media when wording matters.

## HTTP API

| Method and path | Behavior |
| --- | --- |
| `GET /health` | Service readiness; never includes secrets |
| `GET /schema` | Current analysis JSON Schema |
| `GET /analyses?limit=20&offset=0` | Paginated saved-video summaries and processing times |
| `POST /analyses` | Accepts `{"url":"https://www.tiktok.com/@creator/video/123..."}`; returns HTTP 202 with a job ID, or HTTP 200 with `cached: true` and the existing result |
| `GET /jobs/{id}` | Current stage, progress message, and finished result when available |
| `GET /analyses/{id}` | Retrieves a saved analysis by its analysis ID |

FastAPI's interactive documentation is at **http://127.0.0.1:8000/docs**. Next.js proxies these endpoints under `/api/organ/` so the browser uses the same origin.

The local service runs one analysis worker with at most three active/queued submissions. Run one Uvicorn process; do not add `--workers`. Job progress exists in memory and is lost on restart; completed analysis records remain in SQLite. UI polling stops after 20 minutes. It does not cancel a remote Apify run; inspect Apify Console before retrying a stalled collection.

## Saved results

Open **http://127.0.0.1:3000/results_db** to browse all saved analyses. Each entry has a **View webpage** link to `/results_db/{analysis_id}`. The detail page reuses the main analyzer's video player, interpretation, metrics, captions, and JSON controls. Opening saved pages never starts collection or model inference, and cached submissions work even without an Apify token.

New analyses record actual processing time (including collection and model processing, excluding queue wait). Existing entries show that timing was not recorded. As an estimate, allow 30 seconds to two minutes for a new video; queueing, model downloads, and long videos may take longer. The measured visual step on the first real video was about 17 seconds; that is not a full-pipeline benchmark.

Startup consolidates legacy duplicate video records, preferring the most complete result and then the newest. Before consolidation, it backs up the SQLite database to `.data/organ-before-dedup-*.sqlite3`. Legacy analysis IDs redirect to the retained result; their original media stays on disk. The backup preserves previous records and raw output.

One saved entry represents one video. Reusing it does not refresh engagement counters. A future explicit refresh mechanism should append timestamped observations under that video rather than create duplicate video entries. A previously unseen short-link alias may still require collection to discover its actual video ID; database uniqueness prevents saving it twice.

The POC accepts public videos up to 120 seconds and downloaded files up to 60 MB. It downloads media only from Apify key-value-store record URLs. If media is unavailable, it returns a partial metadata record with a limitation rather than fabricated speech. A partial record whose classifier failed can be inspected in the JSON; check connectivity to Hugging Face and the configured checkpoint before retrying.

## Validation

```sh
uv run pytest -q
npm run typecheck
npm run build
```

Tests use controlled collection fixtures and do not spend Apify credit or require model downloads. They cover URL validation, counters, video identity, language gating, uncertainty handling, schema compatibility, and the job-to-persisted-record flow.

The dependency lockfiles pin the development environment. PyAV is constrained below version 17 because faster-whisper 1.2.1 calls an API removed in PyAV 19; a real audio smoke check caught that incompatible default resolution.

## Integration references

- [Laya source and Python API](https://github.com/NandhaKishorM/laya)
- [Multilingual Laya checkpoint](https://huggingface.co/convaiinnovations/laya-multilingual)
- [Faster Whisper source](https://github.com/SYSTRAN/faster-whisper)
- [Clockworks TikTok Scraper](https://apify.com/clockworks/tiktok-scraper)
