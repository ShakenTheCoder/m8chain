# n8chain API Contract & Integration Guide
**Part 3: Evolutionary Optimization (`optimization` branch)**

This document defines the interface between **Part 2 (`validation`)**, **Part 3 (`optimization`)**, and the **Next.js frontend application**.

---

## 1. Service Overview

- **Base URL:** `http://localhost:8000`
- **Swagger Docs:** `http://localhost:8000/docs`
- **CORS:** Enabled for all origins (`*`) for frictionless local frontend development.

---

## 2. Part 2 (`validation`) → Part 3 (`optimization`) Handoff

### Endpoint: `POST /api/v1/optimize/init`
Initializes **Generation 0** candidate creatives, seeds chromosome diversity across platforms, evaluates baseline simulated metrics, and equally distributes the campaign budget.

#### Supported Request Payloads
The endpoint accepts **either** direct root fields or a wrapped object.

##### Option A: Direct Root Payload (Standard Part 2 Output)
```json
{
  "trend_id": "trend_9f81a20c",
  "trend_name": "Autonomous Multi-Agent Marketing Workflows",
  "keywords": ["AI Agent", "Workflow Automation", "Ad Optimization", "Content Engine"],
  "niche": "B2B MarTech & SaaS",
  "persona": {
    "type": "business",
    "tone": "authoritative and cutting-edge",
    "target_audience": "VP of Growth, Performance Marketers, and Tech Founders",
    "risk_tolerance": "medium",
    "primary_goal": "roas"
  },
  "recommended_formats": ["short_form_video", "carousel_infographic", "high_contrast_post"],
  "total_budget": 1000.00
}
```

##### Option B: Wrapped Payload (With Optional GA Hyperparameters)
```json
{
  "validation_input": {
    "trend_id": "trend_9f81a20c",
    "trend_name": "Autonomous Multi-Agent Marketing Workflows",
    "keywords": ["AI Agent", "Workflow Automation", "Ad Optimization"],
    "niche": "B2B MarTech & SaaS",
    "persona": {
      "type": "content_creator",
      "tone": "authentic, high-energy",
      "target_audience": "Digital Creators & Solo Builders",
      "risk_tolerance": "high",
      "primary_goal": "engagement"
    },
    "total_budget": 850.00
  },
  "config": {
    "population_size": 10,
    "mutation_rate": 0.20,
    "elitism_ratio": 0.20,
    "tournament_size": 3
  }
}
```

#### Field Specifications: `ValidationInput`

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `trend_id` | `string` | No (auto-generated) | Unique ID of validated trend from Part 2. |
| `trend_name` | `string` | **Yes** | Human-readable title of selected trend. |
| `keywords` | `string[]` | No | Associated keywords for gene synthesis. |
| `niche` | `string` | **Yes** | Target industry vertical. |
| `persona.type` | `"business" \| "content_creator"` | **Yes** | Determines fitness function optimization priorities. |
| `persona.tone` | `string` | No | Brand voice guidelines. |
| `persona.target_audience` | `string` | No | Segment definition. |
| `persona.risk_tolerance` | `"low" \| "medium" \| "high"` | No | Creative variance tolerance (default: `"medium"`). |
| `persona.primary_goal` | `"reach" \| "conversions" \| "engagement" \| "roas"` | No | Fitness bonus target. |
| `total_budget` | `number` | No (default: `1000.0`) | Total ad spend in USD across all active candidates. |

---

### Response: `InitCampaignResponse` (HTTP 200 OK)
```json
{
  "campaign_id": "camp_e9d21af8",
  "message": "Initialized campaign 'Autonomous Multi-Agent Marketing Workflows' with 10 candidates.",
  "generation": {
    "generation": 0,
    "best_candidate_id": "cand_g0_03",
    "best_fitness": 1.317,
    "avg_fitness": 0.615,
    "diversity_score": 0.70,
    "total_budget_allocated": 1000.0,
    "eliminated_candidate_ids": [],
    "active_candidates": [
      {
        "id": "cand_g0_01",
        "generation_index": 0,
        "status": "active",
        "fitness_score": 1.15,
        "metrics": {
          "impressions": 3846,
          "clicks": 96,
          "ctr": 0.025,
          "engagement_rate": 0.045,
          "conversions": 8,
          "conversion_rate": 0.083,
          "spend": 100.0,
          "cpc": 1.04,
          "cac": 12.5,
          "roas": 3.4
        },
        "budget": {
          "daily_budget": 100.0,
          "spend_weight": 0.10,
          "bid_aggressiveness": 1.0
        },
        "post": {
          "hook": "Why is nobody in B2B MarTech & SaaS talking about Autonomous Multi-Agent Marketing Workflows?",
          "caption_body": "In B2B MarTech & SaaS, the rules just shifted...",
          "visual_asset_prompt": "Adobe Express kinetic typography with bold neon accents, 9:16 vertical ratio.",
          "hashtags": ["#aiagent", "#b2bmartech&saas", "#growth", "#marketing"],
          "call_to_action": "Book a 15-minute product walkthrough to unlock higher ROAS 🎯",
          "target_platform": "LinkedIn"
        },
        "parent_ids": []
      }
    ]
  }
}
```

---

## 3. Evolutionary Step Execution

### Endpoint: `POST /api/v1/optimize/step`
Triggers one evolutionary cycle ($N \to N+1$):
1. Ranks current candidates and preserves elites (top 20%).
2. Eliminates low performers.
3. Breeds offspring via genetic crossover and copy/budget mutations.
4. Dynamically shifts spend from eliminated variants to winners using Softmax / UCB reallocation.

#### Request Payload

##### Option A: Automated Simulation (Demo Mode)
```json
{
  "campaign_id": "camp_e9d21af8"
}
```

##### Option B: With Actual Ad-Network Telemetry (Live Production Mode)
```json
{
  "campaign_id": "camp_e9d21af8",
  "uploaded_metrics": [
    {
      "candidate_id": "cand_g0_01",
      "impressions": 4200,
      "clicks": 145,
      "ctr": 0.0345,
      "engagement_rate": 0.061,
      "conversions": 11,
      "conversion_rate": 0.076,
      "spend": 100.0,
      "cpc": 0.69,
      "cac": 9.09,
      "roas": 4.15
    }
  ]
}
```

#### Response: `StepCampaignResponse` (HTTP 200 OK)
```json
{
  "campaign_id": "camp_e9d21af8",
  "message": "Successfully evolved to Generation 1. Best fitness: 1.482",
  "budget_reallocation": {
    "cand_g0_01": 215.40,
    "cand_g0_03": 175.20,
    "cand_g1_03": 85.10,
    "cand_g1_04": 74.50
  },
  "generation": {
    "generation": 1,
    "best_candidate_id": "cand_g0_01",
    "best_fitness": 1.482,
    "avg_fitness": 0.842,
    "diversity_score": 0.58,
    "total_budget_allocated": 1000.0,
    "eliminated_candidate_ids": ["cand_g0_05", "cand_g0_07", "cand_g0_08"],
    "active_candidates": [ ... ]
  }
}
```

---

## 4. Diagnostic & Dashboard State

### Endpoint: `GET /api/v1/optimize/status/{campaign_id}`
Returns complete history, Pareto-optimal creatives, and convergence telemetry for the Next.js frontend.

#### Response: `CampaignStatusResponse` (HTTP 200 OK)
```json
{
  "campaign_id": "camp_e9d21af8",
  "trend_name": "Autonomous Multi-Agent Marketing Workflows",
  "niche": "B2B MarTech & SaaS",
  "persona_type": "business",
  "current_generation": 2,
  "convergence_curve": [
    { "generation": 0, "best_fitness": 1.317, "avg_fitness": 0.615 },
    { "generation": 1, "best_fitness": 1.482, "avg_fitness": 0.842 },
    { "generation": 2, "best_fitness": 1.691, "avg_fitness": 1.053 }
  ],
  "pareto_optimal_candidates": [
    {
      "id": "cand_g0_01",
      "fitness_score": 1.691,
      "post": { ... },
      "budget": { ... },
      "metrics": { ... }
    }
  ],
  "current_budget_breakdown": {
    "cand_g0_01": 280.50,
    "cand_g1_02": 195.20,
    "cand_g2_04": 65.10
  },
  "history": [ ... ]
}
```

---

## 5. Next.js Frontend UI Rendering Guidelines

1. **Candidate Cards:**
   - Display `post.hook` as the primary card title/headline.
   - Display `post.target_platform` badge (`LinkedIn`, `Instagram`, `TikTok`, `X`).
   - Display `post.visual_asset_prompt` as the visual preview / image generator prompt.
   - Display `post.call_to_action` as the highlighted CTA button text.
   - Show badge for `status`: `survived` (Green), `recombined` (Yellow), `active` (Cyan).

2. **Budget Allocation Charts (Bar / Pie / Donut):**
   - Bind slice values to `budget.daily_budget` (currency USD).
   - Show spend share percentage via `budget.spend_weight * 100`%.
   - Notice that $\sum \text{daily\_budget} \le \text{total\_budget}$ is mathematically guaranteed with zero budget leaks.

3. **Convergence Curve (Line Chart):**
   - X-Axis: `generation` (0, 1, 2, ...).
   - Y-Axis Series 1: `best_fitness` (Green line, showing peak creative performance).
   - Y-Axis Series 2: `avg_fitness` (Blue line, showing overall population progression).
