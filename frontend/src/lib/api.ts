import {
  NicheCluster,
  OptimizationHandoffBundle,
  PersonaProfile,
  ValidatedTrendView,
  ValidationWorkspaceResponse,
} from "./types";

const API_BASE = "/api/validation";

async function parseOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail = err.detail || JSON.stringify(err);
    } catch {
      detail = await res.text();
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function fetchWorkspace(): Promise<ValidationWorkspaceResponse> {
  const res = await fetch(`${API_BASE}/workspace`, { cache: "no-store" });
  return parseOrThrow<ValidationWorkspaceResponse>(res);
}

export async function evaluatePersona(persona: PersonaProfile): Promise<{
  active_persona: PersonaProfile;
  niches: NicheCluster[];
  trends: ValidatedTrendView[];
}> {
  const res = await fetch(`${API_BASE}/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ persona }),
  });
  return parseOrThrow(res);
}

export async function ingestOrganPayload(
  payload: unknown,
  replace: boolean = false
): Promise<{
  ingested_trend_count: number;
  total_trends_in_workspace: number;
  ingested_trend_ids: string[];
  warnings: Record<string, string[]>;
  niches: NicheCluster[];
  evaluated_trends: ValidatedTrendView[];
}> {
  const res = await fetch(`${API_BASE}/ingest?replace=${replace}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res);
}

export async function resetMockFixtures(): Promise<void> {
  const res = await fetch(`${API_BASE}/seed-fixtures?replace=true`, {
    method: "POST",
  });
  await parseOrThrow(res);
}

export async function createCustomNiche(input: {
  name: string;
  description: string;
  keywords: string[];
}): Promise<NicheCluster[]> {
  const res = await fetch(`${API_BASE}/niches/custom`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseOrThrow<NicheCluster[]>(res);
}

export async function confirmOptimizationHandoff(input: {
  trend_id: string;
  persona: PersonaProfile;
  user_notes: string;
  optimization_webhook_url?: string;
}): Promise<OptimizationHandoffBundle> {
  const res = await fetch(`${API_BASE}/handoff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return parseOrThrow<OptimizationHandoffBundle>(res);
}
