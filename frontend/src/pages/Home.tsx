import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Sparkles, Calendar, ChevronRight } from "lucide-react";
import { api } from "../api";
import { ALL_STRATEGIES, type DraftSummary, type StrategyName } from "../types";

function StartDraftForm({ onCreated }: { onCreated: () => void }) {
  const navigate = useNavigate();
  const [strategyA, setStrategyA] = useState<StrategyName | "">("");
  const [strategyB, setStrategyB] = useState<StrategyName | "">("");
  const [numRounds, setNumRounds] = useState(4);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setErr(null);
    try {
      const draft = await api.createDraft({
        strategy_a: strategyA || undefined,
        strategy_b: strategyB || undefined,
        num_rounds: numRounds,
      });
      onCreated();
      navigate(`/drafts/${draft.id}`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
    >
      <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
        <Sparkles size={18} className="text-[#ecad0a]" />
        Start a New Draft
      </h2>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <label className="text-sm">
          <span className="mb-1 block text-[#888888]">Team A strategy</span>
          <select
            className="w-full rounded border border-gray-300 bg-white px-2 py-1.5"
            value={strategyA}
            onChange={(e) => setStrategyA(e.target.value as StrategyName | "")}
          >
            <option value="">(random)</option>
            {ALL_STRATEGIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm">
          <span className="mb-1 block text-[#888888]">Team B strategy</span>
          <select
            className="w-full rounded border border-gray-300 bg-white px-2 py-1.5"
            value={strategyB}
            onChange={(e) => setStrategyB(e.target.value as StrategyName | "")}
          >
            <option value="">(random)</option>
            {ALL_STRATEGIES.map((s) => (
              <option key={s} value={s} disabled={s === strategyA}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm">
          <span className="mb-1 block text-[#888888]">Rounds</span>
          <input
            type="number"
            min={1}
            max={20}
            value={numRounds}
            onChange={(e) => setNumRounds(Number(e.target.value))}
            className="w-full rounded border border-gray-300 bg-white px-2 py-1.5"
          />
        </label>
      </div>

      {err && <p className="mt-3 text-sm text-red-600">{err}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="mt-5 rounded bg-[#753991] px-5 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
      >
        {submitting ? "Creating…" : "Create Draft"}
      </button>
    </form>
  );
}

function DraftList({ drafts }: { drafts: DraftSummary[] }) {
  if (drafts.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center text-[#888888]">
        No drafts yet — create your first one above.
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {drafts.map((d) => (
        <li key={d.id}>
          <Link
            to={`/drafts/${d.id}`}
            className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 transition hover:border-[#209dd7]"
          >
            <div>
              <div className="font-medium">{d.name}</div>
              <div className="mt-0.5 flex items-center gap-3 text-xs text-[#888888]">
                <span className="inline-flex items-center gap-1">
                  <Calendar size={12} />
                  {new Date(d.created_at).toLocaleString()}
                </span>
                <span className="rounded bg-gray-100 px-2 py-0.5">{d.status}</span>
                <span>
                  {d.teams.map((t) => t.strategy).join(" vs ")}
                </span>
              </div>
            </div>
            <ChevronRight size={18} className="text-[#888888]" />
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function Home() {
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const rows = await api.listDrafts();
    setDrafts(rows);
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="space-y-8">
      <StartDraftForm onCreated={() => void load()} />
      <section>
        <h2 className="mb-3 text-lg font-semibold">Past Drafts</h2>
        {loading ? <p className="text-sm text-[#888888]">Loading…</p> : <DraftList drafts={drafts} />}
      </section>
    </div>
  );
}
