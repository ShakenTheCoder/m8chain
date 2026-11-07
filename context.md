# n8chain — Project Context

## Overview

n8chain is a marketing optimization system being built at an Adobe hackathon whose theme is marketing. The project connects social media trend discovery, audience validation, and iterative content and budget optimization.

The product is named **n8chain**. Its current GitHub repository is named **m8chain**.

## End-to-end workflow

1. Analyze social media posts and their elements, then group them to identify trends.
2. Match trends to niches and assess their suitability for a content creator or business.
3. Generate posts and budgets for a selected trend, evaluate performance, and evolve the campaign while reallocating resources.

## Part 1: Organ — `organ` branch

Treat each social media post as an **organ** composed of individual elements. Analyze both the complete post and its constituent elements, then group similar posts and elements to identify trends.

Possible elements include visual assets, captions, hooks, topics, formats, hashtags, and calls to action. These are examples for defining the analysis schema, rather than a finalized implementation contract.

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
| Laya classification model | Classification model described by the team as a copy of the Jev model; exact model identity, interface, and integration details remain to be specified. |
| Evolutionary programming (EP) | Evolution of candidate content and campaign strategies. |
| Genetic algorithms (GA) | Selection, replication, and variation of candidates to improve performance and resource allocation. |

## Integration boundaries

- **Organ → Validation:** identified trends and their supporting post and element groups.
- **Validation → Optimization:** a user-selected trend, its niche, the user's persona, and the suitability verdict.
- **Optimization feedback:** post ratings and campaign results inform subsequent candidate selection and resource allocation.

These describe the intended flow. Shared data schemas and API contracts have not yet been agreed.

## Decisions still needed

- Social platforms and Apify actors used for initial data collection.
- The post element schema and method for grouping posts and elements into trends.
- The exact Laya/Jev model reference and classification inputs and outputs.
- Niche definitions and criteria for persona suitability verdicts.
- Performance metrics, fitness scoring, budget limits, and stopping criteria for optimization.
- API and data contracts between the three parts.
