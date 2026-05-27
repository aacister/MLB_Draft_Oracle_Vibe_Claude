import { useEffect, useState } from "react";
import { LineChart as LineIcon } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import type {
  IgnoredPositionRow,
  OverdraftedRow,
  SeasonShiftRow,
} from "../types";

type View = "overdrafted" | "ignored_positions" | "season_shift";

const TABS: { key: View; label: string }[] = [
  { key: "overdrafted", label: "Overdrafted Players" },
  { key: "ignored_positions", label: "Ignored Positions" },
  { key: "season_shift", label: "Season Shift" },
];

export function AdpTrends() {
  const [view, setView] = useState<View>("overdrafted");
  const [rows, setRows] = useState<OverdraftedRow[] | IgnoredPositionRow[] | SeasonShiftRow[]>([]);
  // Track which view the rows belong to so we never render a view-specific
  // component (e.g. OverdraftedView) with rows fetched for a different view —
  // the type cast would be a lie and accessing missing fields throws,
  // unmounting the route.
  const [rowsView, setRowsView] = useState<View | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .adpTrends(view)
      .then((r) => {
        if (cancelled) return;
        setRows(r);
        setRowsView(view);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [view]);

  const dataReady = !loading && rowsView === view;

  return (
    <div className="space-y-6">
      <h1 className="flex items-center gap-2 text-2xl font-bold">
        <LineIcon size={24} className="text-[#ecad0a]" /> ADP Trends
      </h1>

      <div className="flex gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setView(t.key)}
            className={`rounded px-4 py-1.5 text-sm transition ${
              view === t.key
                ? "bg-[#209dd7] text-white"
                : "bg-white text-[#032147] hover:bg-gray-100"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {!dataReady ? (
        <p className="text-sm text-[#888888]">Loading…</p>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center text-[#888888]">
          Not enough drafts yet for this view.
        </div>
      ) : view === "overdrafted" ? (
        <OverdraftedView rows={rows as OverdraftedRow[]} />
      ) : view === "ignored_positions" ? (
        <IgnoredView rows={rows as IgnoredPositionRow[]} />
      ) : (
        <SeasonShiftView rows={rows as SeasonShiftRow[]} />
      )}
    </div>
  );
}

function OverdraftedView({ rows }: { rows: OverdraftedRow[] }) {
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-[#888888]">
          <tr>
            <th className="px-4 py-2 text-left font-medium">Player</th>
            <th className="px-4 py-2 text-left font-medium">Pos</th>
            <th className="px-4 py-2 text-right font-medium">Mean Pick</th>
            <th className="px-4 py-2 text-right font-medium">Appearances</th>
            <th className="px-4 py-2 text-right font-medium">HR</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.player_id} className={i % 2 === 0 ? "bg-white" : "bg-gray-50/50"}>
              <td className="px-4 py-2 font-medium">{r.player_name}</td>
              <td className="px-4 py-2">{r.position}</td>
              <td className="px-4 py-2 text-right">{r.mean_pick.toFixed(1)}</td>
              <td className="px-4 py-2 text-right">{r.appearances}</td>
              <td className="px-4 py-2 text-right text-[#888888]">{r.hr}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IgnoredView({ rows }: { rows: IgnoredPositionRow[] }) {
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-[#888888]">
          <tr>
            <th className="px-4 py-2 text-left font-medium">Position</th>
            <th className="px-4 py-2 text-right font-medium">Mean Pick</th>
            <th className="px-4 py-2 text-right font-medium">Above Median?</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.position}>
              <td className="px-4 py-2 font-medium">{r.position}</td>
              <td className="px-4 py-2 text-right">{r.mean_pick.toFixed(1)}</td>
              <td className="px-4 py-2 text-right">
                {r.above_median ? (
                  <span className="rounded bg-[#ecad0a]/20 px-2 py-0.5 text-xs font-medium text-[#ecad0a]">
                    Ignored
                  </span>
                ) : (
                  <span className="text-[#888888]">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SeasonShiftView({ rows }: { rows: SeasonShiftRow[] }) {
  const data = rows.map((r, i) => ({
    index: i + 1,
    rolling: r.rolling_mean_pick,
  }));
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h3 className="mb-4 font-semibold">Rolling Mean Pick Number</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="index" stroke="#888888" />
          <YAxis stroke="#888888" />
          <Tooltip />
          <Line type="monotone" dataKey="rolling" stroke="#753991" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
