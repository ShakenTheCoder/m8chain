"use client";

import React, { useState } from "react";
import {
  CheckCircle2,
  Copy,
  Download,
  Rocket,
  Send,
  X,
} from "lucide-react";
import {
  OptimizationHandoffBundle,
  PersonaProfile,
  ValidatedTrendView,
} from "@/lib/types";

interface Props {
  trend: ValidatedTrendView | null;
  persona: PersonaProfile;
  onClose: () => void;
  onConfirm: (input: {
    trend_id: string;
    user_notes: string;
    optimization_webhook_url?: string;
  }) => Promise<OptimizationHandoffBundle>;
}

export function HandoffConfirmModal({
  trend,
  persona,
  onClose,
  onConfirm,
}: Props) {
  const [notes, setNotes] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [bundle, setBundle] = useState<OptimizationHandoffBundle | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!trend) return null;

  const handleConfirm = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const created = await onConfirm({
        trend_id: trend.trend_id,
        user_notes: notes,
        optimization_webhook_url: webhookUrl.trim() || undefined,
      });
      setBundle(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopy = async () => {
    if (!bundle) return;
    await navigator.clipboard.writeText(JSON.stringify(bundle, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!bundle) return;
    const blob = new Blob([JSON.stringify(bundle, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `n8chain-optimization-handoff-${bundle.handoff_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl border border-slate-800 bg-[#0d111a] shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-800 p-5">
          <div>
            <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-emerald-400">
              <Rocket className="h-3.5 w-3.5" />
              Step 3 · Validation → Optimization Handoff
            </div>
            <h2 className="mt-1 text-xl font-bold text-white">
              {bundle
                ? "Winning Trend Packaged & Handed Off!"
                : "Confirm Winning Trend for Optimization"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-800 bg-slate-900 p-2 text-slate-400 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 space-y-4 overflow-y-auto p-5 text-xs">
          {!bundle ? (
            <>
              <p className="text-sm text-slate-300">
                Confirming this selection packages the{" "}
                <strong className="text-white">selected trend</strong> (with its{" "}
                {trend.records.length} supporting v1.2 records),{" "}
                <strong className="text-violet-300">matched niche</strong>,{" "}
                <strong className="text-indigo-300">active persona</strong>, and{" "}
                <strong className="text-emerald-300">suitability verdict</strong>{" "}
                for Part 3 (<code className="text-slate-200">optimization</code>)
                to initialize GA/EP post candidates and ad budgets.
              </p>

              <div className="grid grid-cols-1 gap-3 rounded-xl border border-slate-800 bg-slate-950/80 p-4 md:grid-cols-2">
                <div>
                  <div className="text-slate-400">Selected Trend</div>
                  <div className="mt-0.5 text-sm font-semibold text-white">
                    {trend.title}
                  </div>
                  <div className="mt-1 text-slate-400">
                    {trend.records.length} Organ v1.2 record(s) · Hook:{" "}
                    <span className="text-slate-200">
                      {trend.dominant_features.hook_type}
                    </span>
                  </div>
                </div>
                <div>
                  <div className="text-slate-400">Matched Niche & Verdict</div>
                  <div className="mt-0.5 text-sm font-semibold text-violet-300">
                    {trend.matched_niche.name}
                  </div>
                  <div className="mt-1 text-emerald-300">
                    {trend.suitability_verdict.fit_status.replace("_", " ")} (
                    {trend.suitability_verdict.overall_score.toFixed(1)}/100) ·{" "}
                    {persona.type === "content_creator"
                      ? "Content Creator"
                      : "Business"}
                  </div>
                </div>
              </div>

              <div>
                <label className="block font-medium text-slate-300">
                  Campaign / Creative Guidance Notes for Optimization Stage
                  (optional)
                </label>
                <textarea
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. Emphasize 72-hour barrier reset hook; cap initial test CPA budget at $150/day..."
                  className="mt-1.5 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-xs text-white focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-400">
                  Optional Optimization Ingest Webhook URL (leave blank to
                  persist & serve via{" "}
                  <code>GET /api/validation/handoffs/latest</code>)
                </label>
                <input
                  type="url"
                  value={webhookUrl}
                  onChange={(e) => setWebhookUrl(e.target.value)}
                  placeholder="http://127.0.0.1:8002/api/optimization/ingest"
                  className="mt-1.5 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              {error && (
                <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-rose-300">
                  {error}
                </div>
              )}
            </>
          ) : (
            <>
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-emerald-200">
                <div className="flex items-center gap-2 text-sm font-semibold text-emerald-300">
                  <CheckCircle2 className="h-4 w-4" />
                  Handoff Bundle Confirmed ({bundle.handoff_id})
                </div>
                <p className="mt-1 text-xs">
                  {bundle.delivery?.webhook_message}
                </p>
                <div className="mt-2 font-mono text-[11px] text-emerald-300/90">
                  Saved to: {bundle.delivery?.persisted_path}
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-950 p-3.5">
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-semibold text-slate-300">
                    GA / EP Seed Hints Included for Part 3 Optimization
                  </span>
                  <span className="rounded bg-indigo-500/20 px-2 py-0.5 text-[11px] text-indigo-300">
                    Pop Size:{" "}
                    {
                      bundle.optimization_seed_hints
                        .suggested_initial_population_size
                    }{" "}
                    · Posture:{" "}
                    {bundle.optimization_seed_hints.budget_allocation_posture}
                  </span>
                </div>
                <pre className="max-h-60 overflow-auto rounded-lg bg-[#07090e] p-3 font-mono text-[11px] text-slate-300">
                  {JSON.stringify(bundle, null, 2)}
                </pre>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2.5 border-t border-slate-800 p-5">
          {!bundle ? (
            <>
              <button
                type="button"
                onClick={onClose}
                className="rounded-xl border border-slate-700 px-4 py-2 text-xs font-medium text-slate-300 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={handleConfirm}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-50"
              >
                <Send className="h-3.5 w-3.5" />
                {submitting
                  ? "Packaging Bundle..."
                  : "Confirm & Pass to Optimization"}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs font-medium text-slate-200 hover:text-white"
              >
                <Copy className="h-3.5 w-3.5" />
                {copied ? "Copied JSON!" : "Copy Bundle JSON"}
              </button>
              <button
                type="button"
                onClick={handleDownload}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
              >
                <Download className="h-3.5 w-3.5" />
                Download Handoff .json
              </button>
              <button
                type="button"
                onClick={onClose}
                className="rounded-xl border border-slate-700 px-4 py-2 text-xs font-medium text-slate-300 hover:text-white"
              >
                Done
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
