"use client";

import React, { useState } from "react";
import {
  AlertCircle,
  Cpu,
  ExternalLink,
  Film,
  Music2,
  Subtitles,
  X,
} from "lucide-react";
import { ValidatedTrendView } from "@/lib/types";

interface Props {
  trend: ValidatedTrendView | null;
  onClose: () => void;
}

export function EvidenceDrawer({ trend, onClose }: Props) {
  const [tab, setTab] = useState<"records" | "laya">("records");
  if (!trend) return null;

  const trace = trend.laya_trace;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-xs">
      <div className="flex h-full w-full max-w-3xl flex-col border-l border-slate-800 bg-[#0b0e15] shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-800 p-5">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-indigo-400">
              Deep Inspection · Organ Schema v1.2 + Laya Decision Trace
            </div>
            <h2 className="mt-1 text-xl font-bold text-white">{trend.title}</h2>
            <p className="mt-0.5 text-xs text-slate-400">
              Matched Niche:{" "}
              <strong className="text-violet-300">
                {trend.matched_niche.name}
              </strong>{" "}
              ({trend.matched_niche.origin})
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-800 bg-slate-900 p-2 text-slate-400 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-slate-800 px-5 py-3">
          <button
            type="button"
            onClick={() => setTab("records")}
            className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
              tab === "records"
                ? "bg-indigo-600 text-white"
                : "bg-slate-900 text-slate-400 hover:text-white"
            }`}
          >
            <Film className="h-3.5 w-3.5" />
            Supporting v1.2 Video Records ({trend.records.length})
          </button>
          <button
            type="button"
            onClick={() => setTab("laya")}
            className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
              tab === "laya"
                ? "bg-violet-600 text-white"
                : "bg-slate-900 text-slate-400 hover:text-white"
            }`}
          >
            <Cpu className="h-3.5 w-3.5" />
            convaiinnovations/laya Decision Trace
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          {tab === "records" ? (
            <>
              {trend.ingestion_warnings.length > 0 && (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3.5 text-xs text-amber-200">
                  <div className="mb-1.5 flex items-center gap-1.5 font-semibold text-amber-300">
                    <AlertCircle className="h-4 w-4" />
                    Ingestion & Quality Warnings
                  </div>
                  <ul className="list-disc space-y-1 pl-4">
                    {trend.ingestion_warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {trend.records.map((rec) => (
                <div
                  key={rec.id}
                  className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-indigo-300">
                        {rec.id}
                      </span>
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300">
                        {rec.video.platform} · {rec.video.duration_seconds}s
                      </span>
                      <span
                        className={`rounded px-2 py-0.5 text-[11px] font-semibold ${
                          rec.status === "complete"
                            ? "bg-emerald-500/15 text-emerald-300"
                            : rec.status === "partial"
                            ? "bg-amber-500/15 text-amber-300"
                            : "bg-rose-500/15 text-rose-300"
                        }`}
                      >
                        status: {rec.status}
                      </span>
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300">
                        lang: {rec.language.code} (
                        {(rec.language.confidence * 100).toFixed(0)}%)
                      </span>
                    </div>

                    {rec.video.url && (
                      <a
                        href={rec.video.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:underline"
                      >
                        @{rec.video.creator_id || "source"}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>

                  {/*Caption + Hashtags*/}
                  {rec.elements.post_description && (
                    <p className="mt-3 text-xs leading-relaxed text-slate-200">
                      {rec.elements.post_description}
                    </p>
                  )}

                  {rec.elements.hashtags.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {rec.elements.hashtags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded bg-slate-800/80 px-1.5 py-0.5 text-[11px] text-slate-400"
                        >
                          #{tag.replace(/^#/, "")}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Transcript Segments */}
                  <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div className="rounded-xl border border-slate-800/90 bg-slate-950/70 p-3">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
                        <Subtitles className="h-3.5 w-3.5 text-indigo-400" />
                        Transcript ({rec.elements.transcript.status})
                      </div>
                      {rec.elements.transcript.segments.length > 0 ? (
                        <div className="mt-2 space-y-1.5 text-xs text-slate-300">
                          {rec.elements.transcript.segments.map((seg, idx) => (
                            <div key={idx}>
                              <span className="mr-1.5 font-mono text-[10px] text-indigo-400">
                                [{seg.start_seconds.toFixed(1)}s-
                                {seg.end_seconds.toFixed(1)}s]
                              </span>
                              {seg.text}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-2 text-xs italic text-slate-500">
                          {rec.elements.transcript.text ||
                            "No spoken transcript available."}
                        </p>
                      )}
                    </div>

                    {/* Visual & OCR */}
                    <div className="rounded-xl border border-slate-800/90 bg-slate-950/70 p-3">
                      <div className="text-xs font-semibold text-slate-300">
                        Visual Summary & On-Screen OCR
                      </div>
                      <p className="mt-1.5 text-xs text-slate-300">
                        {rec.visual.summary || "No visual summary."}
                      </p>
                      {rec.elements.on_screen_text.items.length > 0 && (
                        <div className="mt-2 space-y-1 border-t border-slate-800 pt-2 text-[11px] text-cyan-300">
                          {rec.elements.on_screen_text.items.map((ocr, i) => (
                            <div key={i}>
                              <span className="font-mono text-slate-500">
                                @{ocr.timestamp_seconds.toFixed(1)}s:
                              </span>{" "}
                              “{ocr.text}”
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Sound + Metrics + Limitations */}
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
                    <span className="inline-flex items-center gap-1">
                      <Music2 className="h-3 w-3 text-violet-400" />
                      {rec.elements.sound.title || "Audio"} (
                      {rec.elements.sound.is_original
                        ? "Original Audio"
                        : "Trending Sound"}
                      )
                    </span>
                    <span>
                      Views: {rec.observation.views.toLocaleString()} · Likes:{" "}
                      {(rec.observation.like_rate * 100).toFixed(1)}% · Shares:{" "}
                      {(rec.observation.share_rate * 100).toFixed(2)}%
                    </span>
                  </div>

                  {rec.limitations.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {rec.limitations.map((lim, idx) => (
                        <span
                          key={idx}
                          className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] text-amber-300"
                        >
                          limitation: {lim}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </>
          ) : (
            <div className="space-y-4">
              <div className="rounded-2xl border border-violet-500/30 bg-violet-950/15 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="font-mono text-sm font-bold text-violet-300">
                      {trace.model_id}
                    </div>
                    <div className="text-xs text-slate-400">
                      {trace.backbone} · Mode:{" "}
                      <span className="text-slate-200">
                        {trace.execution_mode}
                      </span>
                    </div>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs">
                    Context Budget:{" "}
                    <strong className="text-white">
                      {trace.estimated_input_tokens} / {trace.max_context_tokens}
                    </strong>{" "}
                    tokens
                    {trace.input_truncated && (
                      <span className="ml-2 text-amber-300">(compressed)</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Typed Primitive 1: Choice */}
              <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  1. Laya <code className="text-violet-300">choice</code>{" "}
                  Primitive · Seed Niche Distribution (T={trace.temperature})
                </h4>
                <div className="mt-3 space-y-2">
                  {Object.entries(trace.choice_probabilities).map(
                    ([nid, prob]) => (
                      <div key={nid} className="flex items-center gap-3 text-xs">
                        <span className="w-56 truncate font-mono text-slate-300">
                          {nid}
                        </span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
                          <div
                            className="h-full rounded-full bg-violet-500"
                            style={{ width: `${Math.max(2, prob * 100)}%` }}
                          />
                        </div>
                        <span className="w-14 text-right font-mono text-slate-200">
                          {(prob * 100).toFixed(1)}%
                        </span>
                      </div>
                    )
                  )}
                </div>
                {trace.emergent_niche_triggered && (
                  <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-200">
                    Hybrid Emergent Triggered: Top seed confidence fell below
                    threshold — synthesized emergent niche{" "}
                    <strong>{trend.matched_niche.name}</strong>.
                  </div>
                )}
              </div>

              {/* Typed Primitives 2 & 3: Score & Noul */}
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-xs">
                  <h4 className="font-semibold uppercase tracking-wider text-slate-400">
                    2. Laya <code className="text-indigo-300">score</code>{" "}
                    Rubrics
                  </h4>
                  <div className="mt-3 space-y-2 text-slate-200">
                    <div className="flex justify-between">
                      <span>Virality Rubric:</span>
                      <strong>
                        {trace.virality_rubric_label.toUpperCase()} (
                        {(trace.virality_rubric_score * 100).toFixed(0)}%)
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Commercial Readiness:</span>
                      <strong>
                        {trace.commercial_rubric_label.toUpperCase()} (
                        {(trace.commercial_rubric_score * 100).toFixed(0)}%)
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Production Effort Estimate:</span>
                      <strong className="uppercase">
                        {trace.production_effort_label}
                      </strong>
                    </div>
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-xs">
                  <h4 className="font-semibold uppercase tracking-wider text-slate-400">
                    3. Laya <code className="text-emerald-300">noul</code>{" "}
                    Calibrated P(true)
                  </h4>
                  <div className="mt-3 space-y-2 text-slate-200">
                    <div className="flex justify-between">
                      <span>P(brand_safe):</span>
                      <strong className="text-emerald-300">
                        {(trace.brand_safe_probability * 100).toFixed(1)}%
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span>P(clear_cta):</span>
                      <strong className="text-cyan-300">
                        {(trace.clear_cta_probability * 100).toFixed(1)}%
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span>English Encoder Compatible:</span>
                      <strong>{trace.english_compatible ? "Yes" : "No"}</strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* Compact State Preview */}
              <div className="rounded-2xl border border-slate-800 bg-slate-950 p-4">
                <div className="text-xs font-semibold text-slate-400">
                  Packed 512-Token State Preview
                </div>
                <pre className="mt-2 whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-slate-300">
                  {trace.compact_state_preview}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
