// Typed fetch client over the /v1 backend endpoints.

import type {
  DraftSnapshot,
  DraftSummary,
  GradeOut,
  IgnoredPositionRow,
  LeaderboardRow,
  OverdraftedRow,
  PlayerOut,
  SeasonShiftRow,
  StrategyName,
} from "./types";

const BASE = "/v1";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return (await res.json()) as T;
}

export interface CreateDraftBody {
  strategy_a?: StrategyName;
  strategy_b?: StrategyName;
  num_rounds?: number;
}

export const api = {
  createDraft: (body: CreateDraftBody) =>
    http<DraftSummary>("/drafts", { method: "POST", body: JSON.stringify(body) }),

  listDrafts: () => http<DraftSummary[]>("/drafts"),

  getDraft: (id: string) => http<DraftSnapshot>(`/drafts/${id}`),

  runDraft: (id: string) =>
    http<{ status: string; draft_id: string }>(`/drafts/${id}/run`, { method: "POST" }),

  getGrades: (id: string) => http<GradeOut[]>(`/drafts/${id}/grade`),

  listPlayers: (params: { position?: string; q?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.position) search.set("position", params.position);
    if (params.q) search.set("q", params.q);
    const qs = search.toString();
    return http<PlayerOut[]>(`/players${qs ? `?${qs}` : ""}`);
  },

  leaderboard: (strategy?: string) =>
    http<LeaderboardRow[]>(`/leaderboard${strategy ? `?strategy=${encodeURIComponent(strategy)}` : ""}`),

  adpTrends: (view: "overdrafted" | "ignored_positions" | "season_shift") =>
    http<OverdraftedRow[] | IgnoredPositionRow[] | SeasonShiftRow[]>(
      `/adp/trends?view=${view}`,
    ),

  streamUrl: (id: string) => `${BASE}/drafts/${id}/stream`,
};
