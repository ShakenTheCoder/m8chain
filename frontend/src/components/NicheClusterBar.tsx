"use client";

import React, { useState } from "react";
import { Layers, Plus, Sparkles, Tag, X } from "lucide-react";
import { NicheCluster } from "@/lib/types";

interface Props {
  niches: NicheCluster[];
  selectedNicheId: string | null;
  onSelectNiche: (nicheId: string | null) => void;
  onAddCustomNiche: (input: {
    name: string;
    description: string;
    keywords: string[];
  }) => Promise<void>;
}

export function NicheClusterBar({
  niches,
  selectedNicheId,
  onSelectNiche,
  onAddCustomNiche,
}: Props) {
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onAddCustomNiche({
        name: name.trim(),
        description:
          description.trim() || `Custom target niche for ${name.trim()}`,
        keywords: keywords
          .split(",")
          .map((k) => k.trim())
          .filter(Boolean),
      });
      setName("");
      setDescription("");
      setKeywords("");
      setShowAdd(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="rounded-2xl border border-slate-800/80 bg-slate-900/50 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-violet-400">
            <Layers className="h-3.5 w-3.5" />
            Step 2 · Hybrid Niche Creation & Matching (convaiinnovations/laya)
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Matches trends against curated seed taxonomy via Laya{" "}
            <code className="rounded bg-slate-800 px-1 py-0.5 text-slate-200">
              choice
            </code>{" "}
            and dynamically spawns{" "}
            <span className="font-medium text-amber-300">Emergent Clusters</span>{" "}
            when novel motifs appear.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setShowAdd((prev) => !prev)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-violet-500 hover:text-white"
        >
          {showAdd ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
          {showAdd ? "Cancel" : "Add Custom Seed Niche"}
        </button>
      </div>

      {showAdd && (
        <form
          onSubmit={handleSubmit}
          className="mt-4 grid grid-cols-1 gap-3 rounded-xl border border-violet-500/30 bg-slate-950/90 p-4 md:grid-cols-4"
        >
          <input
            type="text"
            required
            placeholder="Niche Name (e.g. Stationery & EDC)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white focus:border-violet-500 focus:outline-none"
          />
          <input
            type="text"
            placeholder="Short criteria description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white focus:border-violet-500 focus:outline-none"
          />
          <input
            type="text"
            placeholder="Keywords (thermal, journal, notebook)"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-white focus:border-violet-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-violet-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-violet-500 disabled:opacity-50"
          >
            {saving ? "Re-clustering..." : "Register & Re-Match"}
          </button>
        </form>
      )}

      <div className="mt-4 flex flex-wrap gap-2.5">
        <button
          type="button"
          onClick={() => onSelectNiche(null)}
          className={`rounded-xl border px-3.5 py-2 text-left text-xs transition ${
            selectedNicheId === null
              ? "border-indigo-500 bg-indigo-500/15 text-white"
              : "border-slate-800 bg-slate-950/70 text-slate-400 hover:border-slate-700 hover:text-slate-200"
          }`}
        >
          <div className="font-semibold">All Matched Niches</div>
          <div className="mt-0.5 text-[11px] opacity-80">
            {niches.reduce((acc, n) => acc + n.matched_trend_ids.length, 0)} trends
          </div>
        </button>

        {niches.map((niche) => {
          const active = selectedNicheId === niche.niche_id;
          const isEmergent = niche.origin === "emergent_cluster";
          const isCustom = niche.origin === "custom_user";

          return (
            <button
              key={niche.niche_id}
              type="button"
              onClick={() =>
                onSelectNiche(active ? null : niche.niche_id)
              }
              className={`group rounded-xl border px-3.5 py-2 text-left text-xs transition ${
                active
                  ? "border-violet-500 bg-violet-500/15 text-white shadow"
                  : "border-slate-800 bg-slate-950/70 text-slate-300 hover:border-slate-700"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-100">
                  {niche.name}
                </span>
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    isEmergent
                      ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                      : isCustom
                      ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30"
                      : "bg-violet-500/15 text-violet-300 border border-violet-500/30"
                  }`}
                >
                  {isEmergent ? (
                    <>
                      <Sparkles className="h-2.5 w-2.5" />
                      Emergent
                    </>
                  ) : isCustom ? (
                    "Custom"
                  ) : (
                    <>
                      <Tag className="h-2.5 w-2.5" />
                      Seed
                    </>
                  )}
                </span>
              </div>
              <div className="mt-1 flex items-center gap-2 text-[11px] text-slate-400">
                <span>{niche.matched_trend_ids.length} trend(s)</span>
                <span>·</span>
                <span>Conf {(niche.confidence * 100).toFixed(0)}%</span>
                <span>·</span>
                <span>Cohesion {(niche.cohesion_score * 100).toFixed(0)}%</span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
