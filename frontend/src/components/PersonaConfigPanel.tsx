"use client";

import React, { useState } from "react";
import { Briefcase, Sparkles, SlidersHorizontal, RefreshCw } from "lucide-react";
import { PersonaProfile, PersonaType } from "@/lib/types";

interface Props {
  persona: PersonaProfile;
  presets: Record<PersonaType, PersonaProfile>;
  evaluating: boolean;
  onUpdateAndEvaluate: (next: PersonaProfile) => void;
}

export function PersonaConfigPanel({
  persona,
  presets,
  evaluating,
  onUpdateAndEvaluate,
}: Props) {
  const [keywordsInput, setKeywordsInput] = useState(
    persona.domain_keywords.join(", ")
  );

  const handleSwitchType = (type: PersonaType) => {
    const base = presets[type] ?? persona;
    const next: PersonaProfile = {
      ...base,
      type,
    };
    setKeywordsInput(next.domain_keywords.join(", "));
    onUpdateAndEvaluate(next);
  };

  const commitKeywords = (raw: string) => {
    const parsed = raw
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
    onUpdateAndEvaluate({
      ...persona,
      domain_keywords: parsed,
    });
  };

  return (
    <section className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 shadow-lg backdrop-blur">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-400">
            <SlidersHorizontal className="h-3.5 w-3.5" />
            Step 1 · Persona & Target Domain Modeling
          </div>
          <h2 className="mt-1 text-lg font-semibold text-white">
            Active Suitability Rubric:{" "}
            <span className="text-indigo-300">
              {persona.type === "content_creator"
                ? "Content Creator"
                : "Business Marketing"}
            </span>
          </h2>
        </div>

        <div className="inline-flex rounded-xl border border-slate-800 bg-slate-950/90 p-1">
          <button
            type="button"
            onClick={() => handleSwitchType("content_creator")}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition ${
              persona.type === "content_creator"
                ? "bg-indigo-600 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Sparkles className="h-4 w-4" />
            Content Creator
          </button>
          <button
            type="button"
            onClick={() => handleSwitchType("business")}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition ${
              persona.type === "business"
                ? "bg-emerald-600 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Briefcase className="h-4 w-4" />
            Business
          </button>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="block text-xs font-medium text-slate-400">
            Target Domain / Vertical
          </label>
          <input
            type="text"
            value={persona.target_domain}
            onChange={(e) =>
              onUpdateAndEvaluate({ ...persona, target_domain: e.target.value })
            }
            className="mt-1.5 w-full rounded-lg border border-slate-700/80 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400">
            Domain Keywords (comma-separated)
          </label>
          <input
            type="text"
            value={keywordsInput}
            onChange={(e) => setKeywordsInput(e.target.value)}
            onBlur={() => commitKeywords(keywordsInput)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitKeywords(keywordsInput);
            }}
            placeholder="skincare, ceramide, saas, automation"
            className="mt-1.5 w-full rounded-lg border border-slate-700/80 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none"
          />
        </div>

        {persona.type === "content_creator" ? (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-400">
                Primary Creator Growth Goal
              </label>
              <select
                value={persona.creator_params.growth_goal}
                onChange={(e) =>
                  onUpdateAndEvaluate({
                    ...persona,
                    creator_params: {
                      ...persona.creator_params,
                      growth_goal: e.target.value as
                        | "virality"
                        | "engagement"
                        | "community",
                    },
                  })
                }
                className="mt-1.5 w-full rounded-lg border border-slate-700/80 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none"
              >
                <option value="virality">Virality (Shares & Reach)</option>
                <option value="engagement">Engagement (Like Rate)</option>
                <option value="community">Community (Saves & Comments)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400">
                Max Production Effort Cap
              </label>
              <select
                value={persona.creator_params.max_production_effort}
                onChange={(e) =>
                  onUpdateAndEvaluate({
                    ...persona,
                    creator_params: {
                      ...persona.creator_params,
                      max_production_effort: e.target.value as
                        | "low"
                        | "medium"
                        | "high",
                    },
                  })
                }
                className="mt-1.5 w-full rounded-lg border border-slate-700/80 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none"
              >
                <option value="low">Low (Fast single-shot / POV)</option>
                <option value="medium">Medium (Split-screen / Demo)</option>
                <option value="high">High (Multi-scene edit)</option>
              </select>
            </div>
          </>
        ) : (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-400">
                Campaign Objective
              </label>
              <select
                value={persona.business_params.campaign_objective}
                onChange={(e) =>
                  onUpdateAndEvaluate({
                    ...persona,
                    business_params: {
                      ...persona.business_params,
                      campaign_objective: e.target.value as
                        | "awareness"
                        | "lead_gen"
                        | "direct_conversion",
                    },
                  })
                }
                className="mt-1.5 w-full rounded-lg border border-slate-700/80 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
              >
                <option value="direct_conversion">Direct Conversion / Offer</option>
                <option value="lead_gen">Lead Gen / Template Opt-In</option>
                <option value="awareness">Brand Awareness</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400">
                Brand Safety Guardrail
              </label>
              <select
                value={persona.business_params.brand_safety_strictness}
                onChange={(e) =>
                  onUpdateAndEvaluate({
                    ...persona,
                    business_params: {
                      ...persona.business_params,
                      brand_safety_strictness: e.target.value as
                        | "standard"
                        | "strict",
                    },
                  })
                }
                className="mt-1.5 w-full rounded-lg border border-slate-700/80 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none"
              >
                <option value="strict">Strict (Disqualify Claim/Safety Risk)</option>
                <option value="standard">Standard Commercial</option>
              </select>
            </div>
          </>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/70 pt-3 text-xs text-slate-400">
        <div className="flex flex-wrap items-center gap-3">
          <span>
            Allowed Languages:{" "}
            <strong className="text-slate-200">
              {persona.allowed_languages.join(", ").toUpperCase()}
            </strong>
          </span>
          <span>·</span>
          <span>
            Audience:{" "}
            <strong className="text-slate-300">{persona.target_audience}</strong>
          </span>
        </div>
        {evaluating && (
          <span className="inline-flex items-center gap-1.5 text-indigo-400">
            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            Re-scoring trends...
          </span>
        )}
      </div>
    </section>
  );
}
