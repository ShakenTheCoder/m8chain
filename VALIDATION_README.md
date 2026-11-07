# n8chain — Part 2: Validation (`validation` branch)

This module implements **Part 2: Validation** of **n8chain**:
1. **Ingests Trend Description JSON** from the `organ` branch along with supporting `schema_version: "1.2"` (`analysis_version: "organ-mvp-2"`) video records, handling `complete`, `partial`, and `unsupported_language` statuses plus `limitations`.
2. **Hybrid Niche Creation & Matching** powered by **`convaiinnovations/laya`** (`ModernBERT-large`, 421M params, 512-token context window, English — [Hugging Face](https://huggingface.co/convaiinnovations/laya)):
   - Evaluates compact 512-token English states against Laya's `choice`, `score`, and `noul` primitives with temperature calibration.
   - Matches known verticals to the curated **Seed Niche Taxonomy** (or user-registered custom niches) and dynamically synthesizes **Emergent Niche Clusters** when novel trend signals appear below the seed confidence threshold.
3. **Persona Modeling & Suitability Verdict Engine** supporting **Content Creator** and **Business** personas with multi-dimensional scoring (`0–100`), fit classification (`strong_fit | conditional_fit | weak_fit | disqualified`), evidence citations, and surfaced limitations.
4. **Next.js Validation Studio & Optimization Handoff**: interactive persona switcher, hybrid niche filter, deep `v1.2` + Laya trace drawer, Organ JSON importer, and **Confirm & Pass to Optimization** bundler (`backend/validation/exports/latest_handoff.json` + `GET /api/validation/handoffs/latest` + optional webhook POST).

---

## Quick Start (Windows PowerShell)

### 1. Start the Python Validation API (Port `8000`)
```powershell
c:\Users\andvi\m8chain\backend\validation\.venv\Scripts\uvicorn.exe backend.validation.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Start the Next.js Validation Studio (Port `3000`)
```powershell
$env:PATH = "C:\Program Files\nodejs;" + $env:PATH
& "C:\Program Files\nodejs\npm.cmd" --prefix c:\Users\andvi\m8chain\frontend run dev
```
Open http://localhost:3000 in your browser.

---

## Optional: Live Neural Weights for `convaiinnovations/laya`

By default, `LAYA_BACKEND=auto` runs out-of-the-box with zero download wait and switches automatically when `laya` SDK weights or `HF_TOKEN` are present:

- **Hugging Face Inference API (`HF_TOKEN`)**:
  ```powershell
  $env:HF_TOKEN = "hf_..."
  $env:LAYA_BACKEND = "hf_api"
  ```
- **Local `convaiinnovations/laya` Checkpoint (ModernBERT-large, 421M params)**:
  ```powershell
  c:\Users\andvi\m8chain\backend\validation\.venv\Scripts\pip.exe install -r backend/validation/requirements-laya.txt
  $env:LAYA_BACKEND = "local"
  ```

---

## Integration Contracts Across Branches

- **Organ → Validation (`POST /api/validation/ingest`)**: JSON Schema at `contracts/organ_trend_input.schema.json`. Accepts single Trend Description JSON, `{ "trends": [...] }`, or arrays of `v1.2` records (also importable directly in the UI via **Import Organ Trend JSON**).
- **Validation → Optimization (`POST /api/validation/handoff` & `GET /api/validation/handoffs/latest`)**: JSON Schema at `contracts/optimization_handoff.schema.json`. Exports confirmed winning trend + supporting `v1.2` records, matched niche, active persona, suitability verdict, and GA/EP seed hints to `backend/validation/exports/latest_handoff.json`.

---

## Run Automated Tests
```powershell
c:\Users\andvi\m8chain\backend\validation\.venv\Scripts\python.exe -m pytest -v backend/validation/tests/test_validation_pipeline.py
```
