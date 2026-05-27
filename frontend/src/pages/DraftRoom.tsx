import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Play, Loader2, ExternalLink } from "lucide-react";
import { api } from "../api";
import { useDraftStream } from "../hooks/useDraftStream";
import type { DraftSnapshot, DraftSnapshotTeam, PlayerOut, Position } from "../types";

function TeamPanel({ team }: { team: DraftSnapshotTeam }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="border-b border-gray-100 pb-3">
        <h3 className="font-semibold">{team.name}</h3>
        <p className="text-sm text-[#888888]">{team.strategy}</p>
      </div>
      <ul className="mt-4 space-y-2">
        {team.picks.length === 0 ? (
          <li className="text-sm text-[#888888]">No picks yet.</li>
        ) : (
          team.picks.map((p) => (
            <li key={p.id} className="rounded border border-gray-100 p-3">
              <div className="flex items-center justify-between">
                <span className="font-medium">{p.player_name}</span>
                <span className="rounded bg-[#209dd7]/10 px-2 py-0.5 text-xs font-medium text-[#209dd7]">
                  {p.position}
                </span>
              </div>
              <p className="mt-1 text-xs text-[#888888]">
                Round {p.round} · Pick #{p.pick_number}
              </p>
              {p.rationale && <p className="mt-1.5 text-sm">{p.rationale}</p>}
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

function PickFeed({
  events,
}: {
  events: ReturnType<typeof useDraftStream>["events"];
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <h3 className="mb-3 font-semibold">Pick Feed</h3>
      {events.length === 0 ? (
        <p className="text-sm text-[#888888]">Waiting for the engine…</p>
      ) : (
        <ul className="max-h-96 space-y-2 overflow-y-auto pr-2 text-sm">
          {events.slice().reverse().map((ev) => (
            <li key={ev.id} className="rounded border border-gray-100 p-2">
              <div className="font-mono text-xs text-[#888888]">
                {ev.type} #{ev.id}
              </div>
              {renderEventBody(ev)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function renderEventBody(ev: Record<string, unknown>): React.ReactNode {
  if (ev.type === "pick_completed") {
    const pick = (ev.pick ?? {}) as { player_name?: string; position?: string; rationale?: string };
    return (
      <div className="mt-1">
        <span className="font-medium">{pick.player_name}</span>{" "}
        <span className="text-[#888888]">({pick.position})</span>
        {pick.rationale && <p className="mt-0.5">{pick.rationale}</p>}
      </div>
    );
  }
  if (ev.type === "research_complete") {
    const candidates = (ev.candidates ?? []) as Array<{ player_name?: string; rank?: number }>;
    return (
      <p className="mt-1 text-[#888888]">
        {candidates.length} candidates considered.
      </p>
    );
  }
  if (ev.type === "team_graded") {
    return (
      <p className="mt-1">
        <span className="font-medium">{String(ev.team_name ?? "Team")}</span>:{" "}
        {String(ev.letter ?? "")} ({String(ev.alignment_score ?? "")})
      </p>
    );
  }
  return null;
}

function PlayersBoard({ drafted }: { drafted: Set<number> }) {
  const [players, setPlayers] = useState<PlayerOut[]>([]);
  const [position, setPosition] = useState<Position | "">("");

  useEffect(() => {
    void api
      .listPlayers(position ? { position } : {})
      .then(setPlayers)
      .catch(() => setPlayers([]));
  }, [position]);

  const available = useMemo(
    () => players.filter((p) => !drafted.has(p.id)).slice(0, 50),
    [players, drafted],
  );

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Available Players</h3>
        <select
          className="rounded border border-gray-300 bg-white px-2 py-1 text-sm"
          value={position}
          onChange={(e) => setPosition(e.target.value as Position | "")}
        >
          <option value="">All</option>
          <option value="C">C</option>
          <option value="1B">1B</option>
          <option value="OF">OF</option>
          <option value="P">P</option>
        </select>
      </div>
      <ul className="mt-3 max-h-96 space-y-1 overflow-y-auto pr-2 text-sm">
        {available.map((p) => (
          <li key={p.id} className="flex items-center justify-between rounded px-2 py-1 hover:bg-gray-50">
            <span>{p.name}</span>
            <span className="text-xs text-[#888888]">{p.position} · {p.mlb_team}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DraftRoom() {
  const { draftId } = useParams<{ draftId: string }>();
  const [snapshot, setSnapshot] = useState<DraftSnapshot | null>(null);
  const [starting, setStarting] = useState(false);
  // Open the SSE stream as soon as we have a draftId; the backend stream
  // handles all statuses (pending / running / completed) and closes itself
  // on completion. Gating on status would race with the engine and miss events.
  const { events, connected } = useDraftStream(draftId ?? null);

  async function reload() {
    if (!draftId) return;
    const snap = await api.getDraft(draftId);
    setSnapshot(snap);
  }

  useEffect(() => {
    void reload();
  }, [draftId]);

  // Re-fetch snapshot when a pick event arrives so team panels stay current
  useEffect(() => {
    if (events.length === 0) return;
    const latest = events[events.length - 1];
    if (latest.type === "pick_completed" || latest.type === "draft_completed") {
      void reload();
    }
  }, [events]);

  if (!snapshot) return <p className="text-[#888888]">Loading…</p>;

  const drafted = new Set<number>(snapshot.teams.flatMap((t) => t.picks.map((p) => p.player_id)));
  const draftCompleted = snapshot.status === "completed";

  async function startDraft() {
    if (!draftId) return;
    setStarting(true);
    try {
      await api.runDraft(draftId);
      await reload();
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{snapshot.name}</h1>
          <p className="text-sm text-[#888888]">
            Status: {snapshot.status}
            {connected && snapshot.status === "running" && <span className="ml-2 text-[#209dd7]">● live</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {snapshot.status === "pending" && (
            <button
              onClick={startDraft}
              disabled={starting}
              className="flex items-center gap-2 rounded bg-[#753991] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {starting ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
              Start Draft
            </button>
          )}
          {draftCompleted && (
            <Link
              to={`/drafts/${snapshot.draft_id}/grade`}
              className="flex items-center gap-1 rounded bg-[#ecad0a] px-4 py-2 text-sm font-semibold text-[#032147]"
            >
              View Grade <ExternalLink size={14} />
            </Link>
          )}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {snapshot.teams[0] && <TeamPanel team={snapshot.teams[0]} />}
        <PickFeed events={events} />
        {snapshot.teams[1] && <TeamPanel team={snapshot.teams[1]} />}
      </div>

      <PlayersBoard drafted={drafted} />
    </div>
  );
}
