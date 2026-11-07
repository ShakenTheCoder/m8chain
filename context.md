# n8chain — Project Context

## Overview

n8chain is a marketing optimization system being built at an Adobe hackathon whose theme is marketing. The project connects social media trend discovery, audience validation, and iterative content and budget optimization.

The product is named **n8chain**. Its current GitHub repository is named **m8chain**.

## End-to-end workflow

1. Analyze social media posts and their elements, then group them to identify trends.
2. Match trends to niches and assess their suitability for a content creator or business.
3. Generate posts and budgets for a selected trend, evaluate performance, and evolve the campaign while reallocating resources.

## Part 1: Organ — `organ` branch

Treat each TikTok video post as an **organ** composed of individual elements. Analyze each video into a structured record, store the records, then aggregate similar elements across posts and time windows to identify candidate trends.

The MVP retains the spoken transcript, post description, sound metadata, timestamped engagement counters, and original text sequences. A local vision model describes sampled frames, visible actions, and on-screen text. Original phrases, including slang and profanity, stay intact; normalized matching hints are stored separately. The analysis contract is in [structure.md](structure.md).

Domain terms: an **element** is an observed or extracted post component; a **feature** is a normalized signal derived from elements; an **observation** records engagement at a specific time; a **pattern** recurs across posts; a **trend** has evidence of increasing adoption across comparable time windows and multiple creators.

An **evidence reference** links a description to its transcript segment or sampled frame. A **matching hint** suggests possible equivalence, such as spoken digits and written digits; it is not proof that two posts belong to the same trend. Scene descriptions and recognized text remain model inferences, with original media available for review.

The intended output is a set of identified trends with the posts and elements that support them, ready for the validation stage.

**Our work is scoped to the `organ` branch.** Colleagues own the `validation` and `optimization` branches.

## Part 2: Validation — `validation` branch

This stage creates niches and supports two user personas:

- **Content creator:** a user producing content for an audience.
- **Business:** an organization using content to support its marketing objectives.

It matches each trend with a niche and gives a verdict on whether the trend is a suitable match for the user's persona. The result informs which trend the user selects for content creation and optimization.

## Part 3: Optimization — `optimization` branch

After the user identifies and selects a trend, this stage creates posts and budgets. It uses **evolutionary programming (EP)** and **genetic algorithms (GA)** to improve campaign performance over successive iterations.

The optimization loop is intended to:

1. Create an initial population of candidate posts and budget allocations.
2. Rate candidates using post ratings and observed results.
3. Eliminate poorly performing candidates.
4. Replicate successful candidates and evolve new variations.
5. Distribute resources according to candidate ratings and results.
6. Repeat as new performance evidence becomes available.

The exact fitness function, evolution operators, performance metrics, and budget constraints still need to be defined.

## Technology and models

| Technology | Intended role |
| --- | --- |
| Next.js | Application frontend and user experience. |
| Python | Analysis, classification, and optimization logic. |
| Apify | Social media data collection. |
| Laya classification model | The open Jev alternative from NandhaKishorM/laya; the Organ POC uses its multilingual text decision checkpoint for topics, hooks, formats, and calls to action. |
| Evolutionary programming (EP) | Evolution of candidate content and campaign strategies. |
| Genetic algorithms (GA) | Selection, replication, and variation of candidates to improve performance and resource allocation. |

## Integration boundaries

- **Organ → Validation:** identified trends and their supporting post and element groups.
- **Validation → Optimization:** a user-selected trend, its niche, the user's persona, and the suitability verdict.
- **Optimization feedback:** post ratings and campaign results inform subsequent candidate selection and resource allocation.

These describe the intended flow. Shared data schemas and API contracts have not yet been agreed.

## Decisions still needed

- Confirm the Apify actor configuration for TikTok collection.
- The post element schema and method for grouping posts and elements into trends.
- Marketing-domain evaluation and calibration of the multilingual Laya classifications.
- Niche definitions and criteria for persona suitability verdicts.
- Performance metrics, fitness scoring, budget limits, and stopping criteria for optimization.
- API and data contracts between the three parts.
