"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { TrendingUp, Zap, DollarSign, CheckCircle, XCircle, Clock, ArrowRight, Activity } from "lucide-react";
import { api, Stats, Run } from "@/lib/api";
import { PageShell, PageHeader, Card, Badge, StatusDot, Skeleton, ScoreRing } from "@/components/ui";
import clsx from "clsx";

function StatCard({ icon: Icon, label, value, sub, color }: {
  icon: any; label: string; value: string; sub?: string; color?: string;
}) {
  return (
    <Card className="flex items-start gap-4">
      <div className={clsx("p-2.5 rounded-lg", color ?? "bg-gold/10")}>
        <Icon className={clsx("w-5 h-5", color ? "text-white" : "text-gold")} />
      </div>
      <div>
        <p className="text-mist/50 text-xs">{label}</p>
        <p className="text-2xl font-display text-mist mt-0.5">{value}</p>
        {sub && <p className="text-mist/30 text-[11px] mt-0.5">{sub}</p>}
      </div>
    </Card>
  );
}

function RunRow({ run }: { run: Run }) {
  const score = run.result?.quality_score ?? 0;
  return (
    <Link href={`/pipeline/${run.run_id}`} className="flex items-center gap-4 px-4 py-3 rounded-lg hover:bg-white/5 transition-colors group">
      <StatusDot status={run.status} />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-mist truncate">{run.tour_name}</p>
        <p className="text-xs text-mist/40">{run.destination} · {new Date(run.created_at).toLocaleTimeString()}</p>
      </div>
      {run.result && <ScoreRing score={score} size={36} />}
      <Badge
        label={run.status}
        color={run.status === "complete" ? "green" : run.status === "error" ? "red" : run.status === "running" ? "gold" : "default"}
      />
      <ArrowRight className="w-4 h-4 text-mist/20 group-hover:text-gold transition-colors" />
    </Link>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [runs, setRuns]   = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const [s, r] = await Promise.all([api.stats(), api.runs(10)]);
      setStats(s);
      setRuns(r.runs);
    } catch { /* API offline */ }
    setLoading(false);
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  return (
    <PageShell>
      <PageHeader
        title="Command Centre"
        sub="Real-time view of the content intelligence pipeline"
      />

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {loading ? (
          Array(4).fill(0).map((_, i) => <Skeleton key={i} className="h-24" />)
        ) : (
          <>
            <StatCard icon={Activity}    label="Total Runs"       value={String(stats?.total_runs ?? 0)} />
            <StatCard icon={CheckCircle} label="Avg Quality"      value={`${stats?.avg_quality_score ?? 0}/10`} sub="LangGraph + 29 rules" />
            <StatCard icon={DollarSign}  label="Avg Cost / Tour"  value={`$${stats?.avg_cost_per_tour ?? 0}`} sub="Claude Sonnet baseline" />
            <StatCard icon={Zap}         label="Running Now"       value={String(stats?.running ?? 0)} sub={`${stats?.errors ?? 0} errors`} />
          </>
        )}
      </div>

      {/* Pipeline diagram — always visible */}
      <Card className="mb-8">
        <p className="text-xs text-mist/40 font-mono mb-4 uppercase tracking-widest">Pipeline Architecture</p>
        <div className="flex items-center gap-0 overflow-x-auto pb-2">
          {["ingestion", "seo", "rag", "generate", "validate", "export"].map((node, i, arr) => (
            <div key={node} className="flex items-center gap-0 flex-shrink-0">
              <div className="flex flex-col items-center gap-1.5">
                <div className="px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 text-xs text-mist/70 font-mono">
                  {node}
                </div>
                <div className="text-[9px] text-mist/30">
                  {["Schema check", "DataForSEO", "ChromaDB+rerank", "Claude/GPT", "29 rules", "PostgreSQL"][i]}
                </div>
              </div>
              {i < arr.length - 1 && (
                <div className="w-8 h-px bg-gold/30 flex-shrink-0 mx-1" />
              )}
            </div>
          ))}
          <div className="flex items-center gap-0 flex-shrink-0 ml-1">
            <div className="w-8 h-px bg-yellow-500/30 mx-1" />
            <div className="px-3 py-1.5 rounded-lg border border-yellow-500/30 bg-yellow-500/5 text-xs text-yellow-400/70 font-mono">
              hitl
            </div>
          </div>
        </div>
      </Card>

      {/* Recent runs */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <p className="text-xs text-mist/40 font-mono uppercase tracking-widest">Recent Runs</p>
          <Link href="/pipeline" className="text-xs text-gold hover:text-gold-light transition-colors flex items-center gap-1">
            View all <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        {loading ? (
          <div className="space-y-2">{Array(5).fill(0).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
        ) : runs.length === 0 ? (
          <div className="text-center py-12">
            <Zap className="w-8 h-8 text-mist/20 mx-auto mb-3" />
            <p className="text-mist/40 text-sm">No runs yet.</p>
            <Link href="/upload" className="mt-3 inline-flex items-center gap-2 px-4 py-2 bg-gold text-ink rounded-lg text-sm font-medium hover:bg-gold-light transition-colors">
              Start your first run <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        ) : (
          <div className="space-y-1">
            {runs.map(run => <RunRow key={run.run_id} run={run} />)}
          </div>
        )}
      </Card>
    </PageShell>
  );
}
