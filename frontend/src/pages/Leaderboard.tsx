import { useEffect, useState } from "react";
import { Trophy } from "lucide-react";
import { api } from "../api";
import type { LeaderboardRow } from "../types";

export function Leaderboard() {
  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void api
      .leaderboard()
      .then(setRows)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="flex items-center gap-2 text-2xl font-bold">
        <Trophy size={24} className="text-[#ecad0a]" /> Strategy Leaderboard
      </h1>

      {loading ? (
        <p className="text-sm text-[#888888]">Loading…</p>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center text-[#888888]">
          No grades yet. Run a draft to populate the leaderboard.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-[#888888]">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Strategy</th>
                <th className="px-4 py-2 text-right font-medium">Avg Score</th>
                <th className="px-4 py-2 text-right font-medium">Drafts</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.strategy} className={i % 2 === 0 ? "bg-white" : "bg-gray-50/50"}>
                  <td className="px-4 py-3 font-medium">{r.strategy}</td>
                  <td className="px-4 py-3 text-right">{r.avg_score.toFixed(1)}</td>
                  <td className="px-4 py-3 text-right text-[#888888]">{r.drafts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
