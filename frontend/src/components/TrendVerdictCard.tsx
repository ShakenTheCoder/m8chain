"use client";

import React from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Eye,
  FileSearch,
  Heart,
  Share2,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { FitStatus, ValidatedTrendView } from "@/lib/types";

interface Props {
  trend: ValidatedTrendView;
  confirmedHandoffId?: string;
  onInspectEvidence: (trend: ValidatedTrendView) => void;
  onSelectForHandoff: (trend: ValidatedTrendView) => void;
}

const FIT_BADGE_STYLES: Record<
  FitStatus,
  { label: string; badge: string; bar: string }
> = {
  strong_fit: {
    label: "Strong Fit",
    badge: "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
    bar: "bg-emerald-500",
  },
  conditional_fit: {
    label: "Conditional Fit",
    badge: "border-amber-500/40 bg-amber-500/15 text-amber-300",
    bar: "bg-amber-500",
  },
  weak_fit: {
    label: "Weak Fit",
    badge: "border-orange-500/40 bg-orange-500/15 text-orange-300",
    bar: "bg-orange-500",
  },
  disqualified: {
    label: "Disqualified",
    badge: "border-rose-500/40 bg-rose-500/15 text-rose-300",
    bar: "bg-rose-500",
  },
};

export function TrendVerdictCard({
  trend,
  confirmedHandoffId,
  onInspectEvidence,
  onSelectForHandoff,
}: Props) {
  const verdict = trend.suitability_verdict;
  const style = FIT_BADGE_STYLES[verdict.fit_status];
  const dims = verdict.dimension_scores;
  const bm = trend.benchmark_metrics;
  const isEmergent = trend.matched_niche.origin === "emergent_cluster";

  return (
    <article className="flex flex-col justify-between rounded-2xl border border-slate-800/90 bg-slate-900/70 p-5 shadow-md transition hover:border-slate-700">
      <div>
        {/* Top Row: Niche Pill + Verdict Badge + Overall Score */}
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                isEmergent
                  ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                  : "border-violet-500/30 bg-violet-500/10 text-violet-300"
              }`}
            >
              {isEmergent && <Sparkles className="h-3 w-3" />}
              {trend.matched_niche.name}
            </span>

            {confirmedHandoffId && (
              <span className="inline-flex items-center gap-1 rounded-full border border-indigo-400/40 bg-indigo-500/20 px-2.5 py-0.5 text-xs font-semibold text-indigo-200">
                <CheckCircle2 className="h-3 w-3" />
                Handed Off ({confirmedHandoffId})
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${style.badge}`}
            >
              {style.label}
            </span>
            <div className="rounded-xl border border-slate-700/80 bg-slate-950 px-3 py-1 text-right">
              <div className="text-base font-bold text-white">
                {verdict.overall_score.toFixed(1)}
                <span className="text-[11px] font-normal text-slate-400">
                  /100
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Title & Summary */}
        <h3 className="mt-3 text-lg font-semibold text-white">{trend.title}</h3>
        <p className="mt-1 text-sm leading-relaxed text-slate-300">
          {trend.summary}
        </p>

        {/* Dominant Organ Features */}
        <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
          <span className="rounded-md bg-slate-800/90 px-2 py-1 text-slate-200">
            Hook:{" "}
            <strong className="text-indigo-300">
              {trend.dominant_features.hook_type}
            </strong>
          </span>
          <span className="rounded-md bg-slate-800/90 px-2 py-1 text-slate-200">
            Format:{" "}
            <strong className="text-indigo-300">
              {trend.dominant_features.format}
            </strong>
          </span>
          <span className="rounded-md bg-slate-800/90 px-2 py-1 text-slate-200">
            CTA:{" "}
            <strong className="text-emerald-300">
              {trend.dominant_features.call_to_action || "none"}
            </strong>
          </span>
        </div>

        {/* Engagement & Record Status Strip */}
        <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl border border-slate-800/80 bg-slate-950/70 p-3 text-xs">
          <div className="flex items-center gap-2">
            <Eye className="h-4 w-4 text-slate-400" />
            <div>
              <div className="text-slate-400">Avg Views</div>
              <div className="font-semibold text-slate-100">
                {Math.round(bm.avg_views).toLocaleString()}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Heart className="h-4 w-4 text-pink-400" />
            <div>
              <div className="text-slate-400">Like Rate</div>
              <div className="font-semibold text-slate-100">
                {(bm.avg_like_rate * 100).toFixed(1)}%
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Share2 className="h-4 w-4 text-cyan-400" />
            <div>
              <div className="text-slate-400">Share Rate</div>
              <div className="font-semibold text-slate-100">
                {(bm.avg_share_rate * 100).toFixed(2)}%
              </div>
            </div>
          </div>
        </div>

        {/* Dimension Breakdown Mini Bars */}
        <div className="mt-4 space-y-2 text-xs">
          {[
            { label: "Domain Relevance", val: dims.domain_relevance },
            { label: "Persona Alignment", val: dims.persona_alignment },
            { label: "Engagement Momentum", val: dims.engagement_momentum },
            {
              label:
                verdict.persona_type === "business"
                  ? "Brand Safety Guardrail"
                  : "Execution Feasibility",
              val: dims.execution_or_brand_safety,
            },
            { label: "CTA & Conversion Fit", val: dims.cta_and_conversion_fit },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-3">
              <span className="w-40 truncate text-slate-400">{item.label}</span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                <div
                  className={`h-full rounded-full ${style.bar}`}
                  style={{ width: `${Math.min(100, Math.max(4, item.val))}%` }}
                />
              </div>
              <span className="w-8 text-right font-mono text-slate-300">
                {Math.round(item.val)}
              </span>
            </div>
          ))}
        </div>

        {/* Verdict Rationale & Strengths / Limitations */}
        <p className="mt-4 rounded-xl border border-slate-800/70 bg-slate-950/50 p-3 text-xs leading-relaxed text-slate-300">
          {verdict.rationale}
        </p>

        {verdict.strengths.length > 0 && (
          <ul className="mt-3 space-y-1 text-xs text-emerald-300/90">
            {verdict.strengths.slice(0, 2).map((s, idx) => (
              <li key={idx} className="flex items-start gap-1.5">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
                <span>{s}</span>
              </li>
            ))}
          </ul>
        )}

        {verdict.risks_and_limitations.length > 0 && (
          <ul className="mt-2.5 space-y-1 text-xs text-amber-300/90">
            {verdict.risks_and_limitations.slice(0, 2).map((r, idx) => (
              <li key={idx} className="flex items-start gap-1.5">
                {verdict.fit_status === "disqualified" ? (
                  <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-400" />
                ) : (
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
                )}
                <span>{r}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Footer: v1.2 Record Badges + Actions */}
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-800/80 pt-4">
        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
          <span className="text-slate-400">v1.2 Records:</span>
          {bm.complete_count > 0 && (
            <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-emerald-300">
              {bm.complete_count} complete
            </span>
          )}
          {bm.partial_count > 0 && (
            <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-amber-300">
              {bm.partial_count} partial
            </span>
          )}
          {bm.unsupported_language_count > 0 && (
            <span className="rounded bg-rose-500/15 px-1.5 py-0.5 text-rose-300">
              {bm.unsupported_language_count} unsupported_lang
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onInspectEvidence(trend)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-2 text-xs font-medium text-slate-200 transition hover:border-slate-500 hover:text-white"
          >
            <FileSearch className="h-3.5 w-3.5" />
            v1.2 Evidence & Laya
          </button>

          <button
            type="button"
            disabled={verdict.fit_status === "disqualified"}
            onClick={() => onSelectForHandoff(trend)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
          >
            Select Winning Trend
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </article>
  );
}
