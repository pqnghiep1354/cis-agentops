"use client";
import { useEffect, useState } from "react";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell,
} from "recharts";
import { BarChart3, Brain, TrendingUp, CheckCircle } from "lucide-react";
import { api, EvalResult } from "@/lib/api";
import { PageShell, PageHeader, Card, Badge, ScoreRing, Skeleton } from "@/components/ui";

const DIM_LABELS: Record<string, string> = {
  brand_voice:         "Brand Voice",
  seo_quality:         "SEO Quality",
  content_accuracy:    "Accuracy",
  writing_quality:     "Writing",
  target_audience_fit: "Audience Fit",
  commercial_readiness:"Pub Ready",
};

function DimBar({ dim, score }: { dim: string; score: number }) {
  const pct = (score / 10) * 100;
  const color = score >= 7 ? "#22c55e" : score >= 5 ? "#f59e0b" : "#ef4444";
  return (
    <div className="flex items-center gap-3">
      <p className="text-xs text-mist/50 w-28 flex-shrink-0">{DIM_LABELS[dim] ?? dim}</p>
      <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <p className="text-xs font-mono text-mist/60 w-8 text-right">{score.toFixed(1)}</p>
    </div>
  );
}

export default function EvalPage() {
  const [data, setData] = useState<EvalResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.evalLatest().then(d => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const agg = data?.aggregate;
  const results = data?.results ?? [];

  const radarData = agg
    ? Object.entries(agg.dimension_averages).map(([key, val]) => ({
        subject: DIM_LABELS[key] ?? key,
        score: val,
        fullMark: 10,
      }))
    : [];

  const barData = results.slice(0, 10).map(r => ({
    name: r.tour_name.split(" ").slice(0, 2).join(" "),
    judge: r.judge_scores?.overall ?? 0,
    pipeline: r.pipeline?.quality_score ?? 0,
    cost: (r.pipeline?.cost_usd ?? 0) * 1000,
  }));

  return (
    <PageShell>
      <PageHeader
        title="Evaluation Dashboard"
        sub="LLM-as-judge scoring on 20-tour golden dataset"
      />

      {loading ? (
        <div className="grid grid-cols-2 gap-4">{Array(6).fill(0).map((_, i) => <Skeleton key={i} className="h-40" />)}</div>
      ) : !data?.available ? (
        <Card className="text-center py-20">
          <BarChart3 className="w-10 h-10 text-mist/20 mx-auto mb-4" />
          <p className="text-mist/50 mb-2">No eval results yet</p>
          <p className="text-xs text-mist/30 font-mono">python -m eval.run_eval run</p>
        </Card>
      ) : (
        <div className="space-y-6">

          {/* Top stats */}
          <div className="grid grid-cols-4 gap-4">
            <Card gold className="flex flex-col items-center py-5">
              <ScoreRing score={agg?.judge_score_avg ?? 0} size={64} />
              <p className="text-xs text-mist/40 mt-2">Judge Score Avg</p>
            </Card>
            <Card className="flex flex-col items-center justify-center gap-1">
              <p className="font-display text-3xl text-mist">{((agg?.success_rate ?? 0) * 100).toFixed(0)}%</p>
              <p className="text-xs text-mist/40">Success Rate</p>
            </Card>
            <Card className="flex flex-col items-center justify-center gap-1">
              <p className="font-display text-3xl text-gold">${agg?.total_cost_usd?.toFixed(3)}</p>
              <p className="text-xs text-mist/40">Total Cost ({results.length} tours)</p>
            </Card>
            <Card className="flex flex-col items-center justify-center gap-1">
              <p className="font-display text-3xl text-mist">{agg?.pipeline_score_avg?.toFixed(1)}/10</p>
              <p className="text-xs text-mist/40">Pipeline Score Avg</p>
            </Card>
          </div>

          <div className="grid grid-cols-2 gap-6">
            {/* Radar chart */}
            <Card>
              <p className="text-xs text-mist/40 font-mono uppercase tracking-widest mb-4">Dimension Scores — Radar</p>
              <ResponsiveContainer width="100%" height={240}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="rgba(255,255,255,0.06)" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: "rgba(248,246,242,0.4)", fontSize: 11 }} />
                  <Radar name="Score" dataKey="score" stroke="#DB9628" fill="#DB9628" fillOpacity={0.15} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </Card>

            {/* Dimension bars */}
            <Card>
              <p className="text-xs text-mist/40 font-mono uppercase tracking-widest mb-5">Dimension Breakdown</p>
              <div className="space-y-3">
                {Object.entries(agg?.dimension_averages ?? {}).map(([dim, score]) => (
                  <DimBar key={dim} dim={dim} score={score} />
                ))}
              </div>
            </Card>
          </div>

          {/* Per-tour bar chart */}
          {barData.length > 0 && (
            <Card>
              <p className="text-xs text-mist/40 font-mono uppercase tracking-widest mb-4">Judge vs Pipeline Score (per tour)</p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={barData} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="name" tick={{ fill: "rgba(248,246,242,0.3)", fontSize: 10 }} />
                  <YAxis domain={[0, 10]} tick={{ fill: "rgba(248,246,242,0.3)", fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{ background: "#1F2933", border: "1px solid rgba(219,150,40,0.2)", borderRadius: 8 }}
                    labelStyle={{ color: "#F8F6F2" }}
                  />
                  <Bar dataKey="judge" name="Judge Score" fill="#DB9628" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="pipeline" name="Pipeline Score" fill="#22c55e" radius={[3, 3, 0, 0]} fillOpacity={0.7} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Tour results table */}
          <Card>
            <p className="text-xs text-mist/40 font-mono uppercase tracking-widest mb-4">All Tours — LLM Judge</p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-white/5">
                    {["Tour", "Destination", "Judge", "Pipeline", "Model", "Cost"].map(h => (
                      <th key={h} className="px-3 py-2 text-left text-mist/30 font-mono font-normal">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {results.map((r, i) => (
                    <tr key={i} className="hover:bg-white/2">
                      <td className="px-3 py-2.5 text-mist/70">{r.tour_name}</td>
                      <td className="px-3 py-2.5 text-mist/50">{r.destination}</td>
                      <td className="px-3 py-2.5">
                        <span className={r.judge_scores?.overall >= 7 ? "text-green-400" : "text-yellow-400"}>
                          {r.judge_scores?.overall ?? "—"}/10
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-mist/50">{r.pipeline?.quality_score?.toFixed(1) ?? "—"}/10</td>
                      <td className="px-3 py-2.5"><Badge label={r.pipeline?.model_used?.split("-")[0] ?? "—"} /></td>
                      <td className="px-3 py-2.5 font-mono text-mist/30">${r.pipeline?.cost_usd?.toFixed(4) ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="flex items-center gap-2 text-xs text-mist/30 font-mono">
            <Brain className="w-3.5 h-3.5" />
            Run ID: {agg?.run_id} · Judge model: claude-haiku-4-5 · {results.length} tours evaluated
          </div>
        </div>
      )}
    </PageShell>
  );
}
