"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, RefreshCw } from "lucide-react";
import { api, Run } from "@/lib/api";
import { PageShell, PageHeader, Card, Badge, StatusDot, ScoreRing, Skeleton } from "@/components/ui";

export default function PipelinePage() {
  const [runs, setRuns]     = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const r = await api.runs(50);
      setRuns(r.runs);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  return (
    <PageShell>
      <div className="flex items-center justify-between mb-8">
        <PageHeader title="Pipeline Runs" sub="All pipeline executions" />
        <button onClick={load} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-sm text-mist/60 transition-colors">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <Card>
        {loading ? (
          <div className="space-y-2">{Array(8).fill(0).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
        ) : runs.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-mist/40">No runs yet. <Link href="/upload" className="text-gold hover:underline">Start one</Link></p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {runs.map(run => (
              <Link key={run.run_id} href={`/pipeline/${run.run_id}`}
                className="flex items-center gap-4 px-2 py-3.5 hover:bg-white/3 transition-colors group rounded-lg"
              >
                <StatusDot status={run.status} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-mist">{run.tour_name}</p>
                  <p className="text-xs text-mist/40">{run.destination} · {new Date(run.created_at).toLocaleString()}</p>
                </div>
                {run.result && <ScoreRing score={run.result.quality_score} size={36} />}
                {run.result?.cost_usd != null && (
                  <span className="text-xs font-mono text-mist/30">${run.result.cost_usd.toFixed(4)}</span>
                )}
                <Badge
                  label={run.status}
                  color={run.status === "complete" ? "green" : run.status === "error" ? "red" : run.status === "running" ? "gold" : "default"}
                />
                <ArrowRight className="w-4 h-4 text-mist/20 group-hover:text-gold transition-colors" />
              </Link>
            ))}
          </div>
        )}
      </Card>
    </PageShell>
  );
}
