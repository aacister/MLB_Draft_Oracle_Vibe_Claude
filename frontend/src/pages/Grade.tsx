import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import type { GradeOut } from "../types";

function GradeCard({ grade }: { grade: GradeOut }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold">{grade.team_name}</h3>
          <p className="text-sm text-[#888888]">{grade.strategy}</p>
        </div>
        <div className="text-right">
          <div className="text-4xl font-bold text-[#032147]">{grade.letter}</div>
          <div className="text-xs text-[#888888]">{grade.alignment_score} / 100</div>
        </div>
      </div>
      <p className="mt-4 text-sm">{grade.rationale}</p>
    </div>
  );
}

export function Grade() {
  const { draftId } = useParams<{ draftId: string }>();
  const [grades, setGrades] = useState<GradeOut[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!draftId) return;
    void api
      .getGrades(draftId)
      .then(setGrades)
      .catch((e) => setErr(String(e)));
  }, [draftId]);

  if (err) {
    return (
      <div className="text-red-600">
        Could not load grades: {err}
      </div>
    );
  }

  const chartData = grades.map((g) => ({
    team: g.team_name,
    score: g.alignment_score,
  }));

  return (
    <div className="space-y-6">
      <Link to={`/drafts/${draftId}`} className="flex items-center gap-1 text-sm text-[#209dd7]">
        <ArrowLeft size={14} /> Back to Draft Room
      </Link>

      <h1 className="text-2xl font-bold">Draft Grades</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {grades.map((g) => (
          <GradeCard key={g.team_id} grade={g} />
        ))}
      </div>

      {grades.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="mb-4 font-semibold">Alignment Score Comparison</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="team" stroke="#888888" />
              <YAxis stroke="#888888" domain={[0, 100]} />
              <Tooltip />
              <Bar dataKey="score" fill="#209dd7" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
