// TypeScript types mirroring backend/app/api/schemas.py.

export type StrategyName =
  | "Power Hitting"
  | "Speed & Defense"
  | "Balanced"
  | "Ace Pitching"
  | "Closer-Heavy"
  | "Contrarian Value";

export const ALL_STRATEGIES: StrategyName[] = [
  "Power Hitting",
  "Speed & Defense",
  "Balanced",
  "Ace Pitching",
  "Closer-Heavy",
  "Contrarian Value",
];

export type Position = "C" | "1B" | "OF" | "P";

export interface TeamSummary {
  id: string;
  name: string;
  strategy: StrategyName;
}

export interface DraftSummary {
  id: string;
  name: string;
  status: "pending" | "running" | "completed";
  created_at: string;
  config: { num_rounds?: number };
  teams: TeamSummary[];
}

export interface Pick {
  id: string;
  round: number;
  pick_number: number;
  player_id: number;
  player_name: string;
  position: Position;
  rationale: string;
}

export interface DraftSnapshotTeam {
  id: string;
  name: string;
  strategy: StrategyName;
  picks: Pick[];
}

export interface DraftSnapshot {
  draft_id: string;
  name: string;
  status: "pending" | "running" | "completed";
  config: { num_rounds?: number };
  teams: DraftSnapshotTeam[];
}

export interface PlayerOut {
  id: number;
  name: string;
  mlb_team: string;
  position: Position;
  stats: Record<string, number | string>;
}

export interface GradeOut {
  team_id: string;
  team_name: string;
  strategy: StrategyName;
  alignment_score: number;
  letter: "A" | "B" | "C" | "D" | "F";
  rationale: string;
}

export interface LeaderboardRow {
  strategy: StrategyName;
  avg_score: number;
  drafts: number;
}

export interface OverdraftedRow {
  player_id: number;
  player_name: string;
  position: Position;
  mean_pick: number;
  appearances: number;
  hr: number;
}

export interface IgnoredPositionRow {
  position: Position;
  mean_pick: number;
  above_median: boolean;
}

export interface SeasonShiftRow {
  draft_id: string;
  created_at: string | null;
  rolling_mean_pick: number;
}

// SSE event payloads.
export interface DraftEvent {
  id: string;
  type: string;
  ts: string;
  draft_id: string;
  [key: string]: unknown;
}
