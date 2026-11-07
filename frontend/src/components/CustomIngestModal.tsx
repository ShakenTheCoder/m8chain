"use client";

import React, { useState } from "react";
import { Upload, X } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
  onIngest: (payload: unknown, replace: boolean) => Promise<void>;
}

const SAMPLE_SNIPPET = `{
  "trend_id": "trend-colleague-sample",
  "title": "Minimalist Morning Protein Espresso",
  "summary": "Creators blend double espresso over vanilla whey ice shake for a 30g protein morning ritual.",
  "records": [
    {
      "schema_version": "1.2",
      "analysis_version": "organ-mvp-2",
      "id": "org-sample-01",
      "status": "complete",
      "video": {
        "platform": "tiktok",
        "id": "tt-882101",
        "url": "https://www.tiktok.com/@fitcafe/video/882101",
        "creator_id": "fitcafe",
        "published_at": "2026-11-07T09:00:00Z",
        "duration_seconds": 22
      },
      "language": { "code": "en", "confidence": 0.99, "source": "lid", "supported": true, "allowed": ["en"] },
      "elements": {
        "post_description": "30g protein iced espresso in 45 seconds. Grab our shaker code PROFF20 in bio!",
        "hashtags": ["proffee", "protein", "espresso", "fitness", "morningroutine"]
      },
      "observation": {
        "views": 410000,
        "likes": 45100,
        "shares": 11200,
        "comments": 820,
        "saves": 19400,
        "like_rate": 0.11,
        "share_rate": 0.0273
      },
      "features": {
        "topic": "protein espresso morning workout drink",
        "hook_type": "three_ingredient_hack",
        "format": "recipe_demo",
        "call_to_action": "Use code PROFF20 in bio",
        "opening_text": "Stop skipping protein with your morning coffee.",
        "evidence_sources": ["transcript", "post_description"]
      },
      "limitations": []
    }
  ]
}`;

export function CustomIngestModal({ open, onClose, onIngest }: Props) {
  const [rawJson, setRawJson] = useState(SAMPLE_SNIPPET);
  const [replace, setReplace] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setRawJson(text);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const parsed = JSON.parse(rawJson);
      await onIngest(parsed, replace);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs">
      <form
        onSubmit={handleSubmit}
        className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl border border-slate-800 bg-[#0d111a] shadow-2xl"
      >
        <div className="flex items-start justify-between border-b border-slate-800 p-5">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-indigo-400">
              Organ → Validation Runtime Contract
            </div>
            <h2 className="mt-1 text-lg font-bold text-white">
              Import Trend Description JSON (Schema v1.2)
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

        <div className="flex-1 space-y-4 overflow-y-auto p-5 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 font-medium text-slate-200 hover:border-indigo-500">
              <Upload className="h-3.5 w-3.5 text-indigo-400" />
              Load .json File from Organ Branch
              <input
                type="file"
                accept=".json,application/json"
                onChange={handleFileUpload}
                className="hidden"
              />
            </label>

            <label className="inline-flex items-center gap-2 text-slate-300">
              <input
                type="checkbox"
                checked={replace}
                onChange={(e) => setReplace(e.target.checked)}
                className="rounded border-slate-700 bg-slate-900"
              />
              Replace existing workspace trends
            </label>
          </div>

          <textarea
            rows={14}
            value={rawJson}
            onChange={(e) => setRawJson(e.target.value)}
            className="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-[11px] leading-relaxed text-slate-200 focus:border-indigo-500 focus:outline-none"
          />

          {error && (
            <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-rose-300">
              {error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2.5 border-t border-slate-800 p-5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-700 px-4 py-2 text-xs font-medium text-slate-300 hover:text-white"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {submitting ? "Validating v1.2 Records..." : "Ingest & Score Trend"}
          </button>
        </div>
      </form>
    </div>
  );
}
