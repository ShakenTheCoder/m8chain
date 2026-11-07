"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Cpu,
  Database,
  ExternalLink,
  RefreshCcw,
  Upload,
} from "lucide-react";
import {
  confirmOptimizationHandoff,
  createCustomNiche,
  evaluatePersona,
  fetchWorkspace,
  ingestOrganPayload,
  resetMockFixtures,
} from "@/lib/api";
import {
  LayaEngineRuntime,
  NicheCluster,
  OptimizationHandoffBundle,
  PersonaProfile,
  PersonaType,
  ValidatedTrendView,
} from "@/lib/types";
import { PersonaConfigPanel } from "@/components/PersonaConfigPanel";
import { NicheClusterBar } from "@/components/NicheClusterBar";
import { TrendVerdictCard } from "@/components/TrendVerdictCard";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { HandoffConfirmModal } from "@/components/HandoffConfirmModal";
import { CustomIngestModal } from "@/components/CustomIngestModal";

export default function ValidationStudioPage() {
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [persona, setPersona] = useState<PersonaProfile | null>(null);
  const [presets, setPresets] = useState<Record<PersonaType, PersonaProfile> | null>(
    null
  );
  const [layaEngine, setLayaEngine] = useState<LayaEngineRuntime | null>(null);
  const [niches, setNiches] = useState<NicheCluster[]>([]);
  const [trends, setTrends] = useState<ValidatedTrendView[]>([]);
  const [handoffs, setHandoffs] = useState<OptimizationHandoffBundle[]>([]);

  const [selectedNicheId, setSelectedNicheId] = useState<string | null>(null);
  const [inspectingTrend, setInspectingTrend] =
    useState<ValidatedTrendView | null>(null);
  const [handoffCandidate, setHandoffCandidate] =
    useState<ValidatedTrendView | null>(null);
  const [showIngestModal, setShowIngestModal] = useState(false);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWorkspace();
      setPersona(data.active_persona);
      setPresets(data.persona_presets);
      setLayaEngine(data.laya_engine);
      setNiches(data.niches);
      setTrends(data.trends);
      setHandoffs(data.handoffs);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to connect to Validation Python backend on port 8000."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const handleUpdateAndEvaluate = async (nextPersona: PersonaProfile) => {
    setPersona(nextPersona);
    setEvaluating(true);
    try {
      const res = await evaluatePersona(nextPersona);
      setPersona(res.active_persona);
      setNiches(res.niches);
      setTrends(res.trends);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setEvaluating(false);
    }
  };

  const handleIngest = async (payload: unknown, replace: boolean) => {
    const res = await ingestOrganPayload(payload, replace);
    setNiches(res.niches);
    setTrends(res.evaluated_trends);
  };

  const handleResetFixtures = async () => {
    await resetMockFixtures();
    setSelectedNicheId(null);
    await loadWorkspace();
  };

  const handleAddCustomNiche = async (input: {
    name: string;
    description: string;
    keywords: string[];
  }) => {
    await createCustomNiche(input);
    await loadWorkspace();
  };

  const handleConfirmHandoff = async (input: {
    trend_id: string;
    user_notes: string;
    optimization_webhook_url?: string;
  }) => {
    if (!persona) throw new Error("Persona not loaded");
    const bundle = await confirmOptimizationHandoff({
      trend_id: input.trend_id,
      persona,
      user_notes: input.user_notes,
      optimization_webhook_url: input.optimization_webhook_url,
    });
    setHandoffs((prev) => [bundle, ...prev]);
    return bundle;
  };

  const filteredTrends = useMemo(() => {
    if (!selectedNicheId) return trends;
    return trends.filter((t) => t.matched_niche.niche_id === selectedNicheId);
  }, [trends, selectedNicheId]);

  const handoffByTrendId = useMemo(() => {
    const map: Record<string, string> = {};
    for (const h of handoffs) {
      if (!map[h.selected_trend.trend_id]) {
        map[h.selected_trend.trend_id] = h.handoff_id;
      }
    }
    return map;
  }, [handoffs]);

  return (
    <div className="min-h-screen bg-[#090b10]">
      {/* Top Studio Header */}
      <header className="border-b border-slate-800/80 bg-[#0b0e16]/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 font-bold text-white shadow">
              n8
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-white">
                  n8chain · Part 2: Validation Studio
                </h1>
                <span className="rounded-full border border-indigo-500/40 bg-indigo-500/15 px-2.5 py-0.5 font-mono text-[11px] text-indigo-300">
                  branch: validation
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Organ Schema v1.2 Ingestion → Hybrid Niche Matching → Persona
                Suitability Verdict → Optimization Handoff
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {layaEngine && (
              <a
                href={layaEngine.huggingface_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-xl border border-violet-500/30 bg-violet-950/30 px-3 py-1.5 text-xs text-violet-200 hover:border-violet-400"
              >
                <Cpu className="h-3.5 w-3.5 text-violet-400" />
                <span className="font-mono">{layaEngine.model_id}</span>
                <span className="text-slate-400">(ModernBERT-L · 512 ctx)</span>
                <ExternalLink className="h-3 w-3 opacity-70" />
              </a>
            )}

            <button
              type="button"
              onClick={() => setShowIngestModal(true)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-500/50 bg-indigo-600/20 px-3.5 py-2 text-xs font-semibold text-indigo-200 transition hover:bg-indigo-600/30"
            >
              <Upload className="h-3.5 w-3.5" />
              Import Organ Trend JSON
            </button>

            <button
              type="button"
              onClick={handleResetFixtures}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-300 transition hover:border-slate-700 hover:text-white"
            >
              <RefreshCcw className="h-3.5 w-3.5" />
              Reset v1.2 Mock Fixtures
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-6">
        {error && (
          <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
            <strong>Backend Connection Notice:</strong> {error}
            <div className="mt-1 font-mono text-xs text-rose-300/90">
              Ensure FastAPI is running:{" "}
              <code>
                backend\validation\.venv\Scripts\uvicorn.exe
                backend.validation.main:app --port 8000
              </code>
            </div>
          </div>
        )}

        {loading ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-12 text-center text-sm text-slate-400">
            Loading Organ v1.2 trends, Laya ModernBERT-large hybrid niches, and
            suitability verdicts...
          </div>
        ) : (
          persona &&
          presets && (
            <>
              {/* Confirmed Handoff Banner if user already passed a trend to Part 3 */}
              {handoffs.length > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-950/20 px-5 py-3.5 text-xs text-emerald-200">
                  <div className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    <span>
                      Latest Optimization Bundle{" "}
                      <strong className="font-mono text-white">
                        {handoffs[0].handoff_id}
                      </strong>{" "}
                      ready for Part 3 (<code className="text-white">optimization</code>
                      ):{" "}
                      <strong>{handoffs[0].selected_trend.title}</strong> →{" "}
                      <span className="text-violet-300">
                        {handoffs[0].niche.name}
                      </span>
                    </span>
                  </div>
                  <a
                    href="/api/validation/handoffs/latest"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 font-mono text-emerald-300 underline hover:text-white"
                  >
                    GET /api/validation/handoffs/latest
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}

              {/* Step 1: Persona Config */}
              <PersonaConfigPanel
                persona={persona}
                presets={presets}
                evaluating={evaluating}
                onUpdateAndEvaluate={handleUpdateAndEvaluate}
              />

              {/* Step 2: Hybrid Niches */}
              <NicheClusterBar
                niches={niches}
                selectedNicheId={selectedNicheId}
                onSelectNiche={setSelectedNicheId}
                onAddCustomNiche={handleAddCustomNiche}
              />

              {/* Step 3: Ranked Trend Verdicts */}
              <section>
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-400">
                    <Database className="h-3.5 w-3.5" />
                    Step 3 · Review Suitability Verdicts & Select Winning Trend
                    ({filteredTrends.length})
                  </div>
                  <div className="text-xs text-slate-400">
                    Sorted by{" "}
                    <strong className="text-slate-200">
                      {persona.type === "content_creator"
                        ? "Content Creator"
                        : "Business"}
                    </strong>{" "}
                    Suitability Score
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                  {filteredTrends.map((trend) => (
                    <TrendVerdictCard
                      key={trend.trend_id}
                      trend={trend}
                      confirmedHandoffId={handoffByTrendId[trend.trend_id]}
                      onInspectEvidence={setInspectingTrend}
                      onSelectForHandoff={setHandoffCandidate}
                    />
                  ))}
                </div>
              </section>
            </>
          )
        )}
      </main>

      <EvidenceDrawer
        trend={inspectingTrend}
        onClose={() => setInspectingTrend(null)}
      />

      {persona && (
        <HandoffConfirmModal
          trend={handoffCandidate}
          persona={persona}
          onClose={() => setHandoffCandidate(null)}
          onConfirm={handleConfirmHandoff}
        />
      )}

      <CustomIngestModal
        open={showIngestModal}
        onClose={() => setShowIngestModal(false)}
        onIngest={handleIngest}
      />
    </div>
  );
}
