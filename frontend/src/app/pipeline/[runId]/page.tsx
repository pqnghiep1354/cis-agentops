"use client";
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import {
  CheckCircle2, Loader2, XCircle, Clock, AlertTriangle,
  ChevronDown, ChevronUp, DollarSign, Zap,
} from "lucide-react";
import { api, Run } from "@/lib/api";
import { PageShell, PageHeader, Card, Badge, ScoreRing } from "@/components/ui";
import clsx from "clsx";

const NODES = [
  { id: "ingestion", label: "Ingestion",      desc: "Excel schema validation" },
  { id: "seo",       label: "SEO Intel",       desc: "DataForSEO keywords + PAA" },
  { id: "rag",       label: "RAG Retrieval",   desc: "Query rewrite → ChromaDB → rerank" },
  { id: "generate",  label: "Content Gen",     desc: "Claude Sonnet / Haiku / GPT-4.1" },
  { id: "validate",  label: "Validation",      desc: "29 brand & quality rules" },
  { id: "export",    label: "Export",          desc: "PostgreSQL publish" },
  { id: "hitl",      label: "HITL Review",     desc: "Human-in-the-loop" },
];

type NodeStatus = "pending" | "running" | "complete" | "error" | "skipped";

function NodeStep({ node, status, timing, isLast }: {
  node: typeof NODES[0]; status: NodeStatus; timing?: number; isLast: boolean;
}) {
  const icon = {
    pending:  <div className="w-5 h-5 rounded-full border border-white/20" />,
    running:  <Loader2 className="w-5 h-5 text-gold animate-spin" />,
    complete: <CheckCircle2 className="w-5 h-5 text-green-400" />,
    error:    <XCircle className="w-5 h-5 text-red-400" />,
    skipped:  <div className="w-5 h-5 rounded-full border border-white/10 bg-white/5" />,
  }[status];

  const labelColor = {
    pending:  "text-mist/30",
    running:  "text-gold",
    complete: "text-mist",
    error:    "text-red-400",
    skipped:  "text-mist/20",
  }[status];

  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className={clsx(
          "flex items-center justify-center w-9 h-9 rounded-full border transition-all duration-300",
          status === "running"  && "border-gold bg-gold/10 animate-pulse-gold",
          status === "complete" && "border-green-500/30 bg-green-500/10",
          status === "error"    && "border-red-500/30 bg-red-500/10",
          status === "pending"  && "border-white/10 bg-white/2",
          status === "skipped"  && "border-white/5",
        )}>
          {icon}
        </div>
        {!isLast && <div className="w-px flex-1 mt-1 bg-white/8 min-h-[24px]" />}
      </div>
      <div className={clsx("pb-6 flex-1 transition-all duration-300", labelColor)}>
        <div className="flex items-center gap-2 mt-1.5">
          <span className="text-sm font-medium">{node.label}</span>
          {timing && <span className="text-[10px] font-mono text-mist/30">{timing.toFixed(0)}ms</span>}
          {node.id === "hitl" && status === "running" && (
            <Badge label="awaiting human" color="yellow" />
          )}
        </div>
        <p className="text-xs text-mist/30 mt-0.5">{node.desc}</p>
      </div>
    </div>
  );
}

function ContentPanel({ result }: { result: NonNullable<Run["result"]> }) {
  const [open, setOpen] = useState(true);
  const gc = result.generated;
  const vr = result.validation;

  return (
    <div className="space-y-4">
      {/* Score + cost */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="flex flex-col items-center gap-2 py-6" gold>
          <ScoreRing score={result.quality_score} size={72} />
          <p className="text-xs text-mist/50">Quality Score</p>
        </Card>
        <Card className="flex flex-col items-center justify-center gap-1">
          <p className="font-display text-2xl text-gold">${result.cost_usd.toFixed(4)}</p>
          <p className="text-xs text-mist/40">Pipeline Cost</p>
          <p className="text-[10px] font-mono text-mist/30">{result.model_used}</p>
        </Card>
        <Card className="flex flex-col items-center justify-center gap-1">
          <p className="font-display text-2xl text-mist">{vr.passed}/{vr.passed + vr.failed}</p>
          <p className="text-xs text-mist/40">Rules Passed</p>
          {vr.failed > 0 && <p className="text-[10px] text-red-400">{vr.failed} failed</p>}
        </Card>
      </div>

      {/* Stage timings */}
      <Card>
        <p className="text-xs text-mist/40 font-mono uppercase tracking-widest mb-3">Stage Timings</p>
        <div className="space-y-2">
          {Object.entries(result.stage_timings).map(([stage, ms]) => {
            const total = Object.values(result.stage_timings).reduce((a, b) => a + b, 0);
            const pct = (ms / total) * 100;
            return (
              <div key={stage} className="flex items-center gap-3">
                <span className="text-xs font-mono text-mist/40 w-20">{stage}</span>
                <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gold/60 rounded-full"
                    style={{ width: `${pct}%`, transition: "width 0.8s ease" }}
                  />
                </div>
                <span className="text-[10px] font-mono text-mist/30 w-14 text-right">{ms.toFixed(0)}ms</span>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Generated content */}
      <Card>
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center justify-between w-full mb-3"
        >
          <p className="text-xs text-mist/40 font-mono uppercase tracking-widest">Generated Content</p>
          {open ? <ChevronUp className="w-4 h-4 text-mist/40" /> : <ChevronDown className="w-4 h-4 text-mist/40" />}
        </button>
        {open && (
          <div className="space-y-4">
            <div>
              <p className="text-xs text-mist/30 mb-1">Title</p>
              <p className="font-display text-lg text-mist">{gc.title}</p>
            </div>
            <div>
              <p className="text-xs text-mist/30 mb-1">Tagline</p>
              <p className="text-mist/70 text-sm italic">{gc.tagline}</p>
            </div>
            <div>
              <p className="text-xs text-mist/30 mb-1">Description</p>
              <p className="text-mist/60 text-sm leading-relaxed">{gc.description}</p>
            </div>
            <div>
              <p className="text-xs text-mist/30 mb-2">Highlights</p>
              <div className="space-y-1">
                {gc.highlights.map((h, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-mist/60">
                    <span className="text-gold mt-1">·</span>
                    {h}
                  </div>
                ))}
              </div>
            </div>
            <div className="border-t border-white/5 pt-4 grid grid-cols-1 gap-2">
              <div>
                <p className="text-[10px] text-mist/30 font-mono">SEO Meta Title</p>
                <p className="text-xs text-mist/60 mt-0.5">{gc.seo_meta_title}</p>
              </div>
              <div>
                <p className="text-[10px] text-mist/30 font-mono">SEO Meta Description</p>
                <p className="text-xs text-mist/60 mt-0.5">{gc.seo_meta_description}</p>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Before / after */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <p className="text-xs text-mist/30 font-mono mb-2">BEFORE — Raw Input</p>
          <p className="text-xs text-mist/50 leading-relaxed">{result.raw_input.description}</p>
        </Card>
        <Card gold>
          <p className="text-xs text-mist/50 font-mono mb-2">AFTER — AI Generated</p>
          <p className="text-xs text-mist/80 leading-relaxed">{gc.description?.slice(0, 300)}…</p>
        </Card>
      </div>

      {/* Failed rules */}
      {vr.failed_rules.length > 0 && (
        <Card>
          <p className="text-xs text-mist/40 font-mono uppercase tracking-widest mb-3">Failed Rules</p>
          <div className="space-y-1">
            {vr.failed_rules.map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-xs text-red-400">
                <XCircle className="w-3 h-3 flex-shrink-0" /> {r}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

export default function PipelinePage() {
  const params = useParams();
  const runId = params.runId as string;

  const [run, setRun]           = useState<Run | null>(null);
  const [nodeStatus, setNodeStatus] = useState<Record<string, NodeStatus>>({});
  const [nodeTimings, setNodeTimings] = useState<Record<string, number>>({});
  const [events, setEvents]     = useState<string[]>([]);
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  // SSE connection
  useEffect(() => {
    if (!runId) return;

    // Initial fetch
    api.getRun(runId).then(setRun).catch(() => {});

    const es = new EventSource(`/api/run/${runId}/stream`);
    esRef.current = es;

    es.addEventListener("started", (e) => {
      const d = JSON.parse(e.data);
      setEvents(prev => [...prev, `Pipeline started: ${d.tour}`]);
      setCurrentNode("ingestion");
      setNodeStatus(prev => ({ ...prev, ingestion: "running" }));
    });

    es.addEventListener("node_complete", (e) => {
      const d = JSON.parse(e.data);
      const node = d.node;
      setNodeStatus(prev => ({ ...prev, [node]: "complete" }));
      if (d.timings) {
        setNodeTimings(prev => ({ ...prev, ...d.timings }));
      }
      setEvents(prev => [...prev, `✓ ${node} complete`]);
      // Set next node as running
      const idx = NODES.findIndex(n => n.id === node);
      if (idx >= 0 && idx < NODES.length - 1) {
        const nextNode = NODES[idx + 1].id;
        setCurrentNode(nextNode);
        setNodeStatus(prev => ({ ...prev, [nextNode]: "running" }));
      }
    });

    es.addEventListener("complete", (e) => {
      const d = JSON.parse(e.data);
      setRun(prev => prev ? { ...prev, status: "complete", result: d } : null);
      setCurrentNode(null);
      api.getRun(runId).then(setRun).catch(() => {});
    });

    es.addEventListener("error", (e) => {
      try {
        const d = JSON.parse((e as MessageEvent).data);
        setEvents(prev => [...prev, `Error: ${d.error}`]);
      } catch {}
      setRun(prev => prev ? { ...prev, status: "error" } : null);
    });

    es.addEventListener("done", () => { es.close(); });

    // Fallback polling if SSE isn't updating
    const poll = setInterval(() => {
      api.getRun(runId).then(r => {
        setRun(r);
        if (r.status === "complete" || r.status === "error") clearInterval(poll);
      }).catch(() => {});
    }, 3000);

    return () => { es.close(); clearInterval(poll); };
  }, [runId]);

  // Determine effective node statuses
  const effectiveStatus = (nodeId: string): NodeStatus => {
    if (nodeStatus[nodeId]) return nodeStatus[nodeId];
    if (run?.status === "complete") {
      // Mark all non-hitl nodes as complete if not explicitly set
      if (nodeId !== "hitl") return "complete";
      return "skipped";
    }
    return "pending";
  };

  return (
    <PageShell>
      <PageHeader
        title={run?.tour_name ?? "Pipeline Run"}
        sub={run ? `${run.destination} · Run ID: ${runId}` : runId}
      />

      <div className="grid grid-cols-[280px_1fr] gap-6 items-start">
        {/* Left: node steps */}
        <div>
          <Card>
            <p className="text-xs text-mist/40 font-mono uppercase tracking-widest mb-5">Pipeline Stages</p>
            <div>
              {NODES.map((node, i) => (
                <NodeStep
                  key={node.id}
                  node={node}
                  status={effectiveStatus(node.id)}
                  timing={nodeTimings[node.id]}
                  isLast={i === NODES.length - 1}
                />
              ))}
            </div>

            {/* Live status */}
            <div className="mt-4 pt-4 border-t border-white/5">
              <div className="flex items-center gap-2">
                {run?.status === "running" && <Loader2 className="w-3.5 h-3.5 text-gold animate-spin" />}
                {run?.status === "complete" && <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />}
                {run?.status === "error" && <XCircle className="w-3.5 h-3.5 text-red-400" />}
                {run?.status === "queued" && <Clock className="w-3.5 h-3.5 text-mist/30" />}
                <span className="text-xs text-mist/50 capitalize">{run?.status ?? "loading…"}</span>
              </div>
            </div>

            {/* Event log */}
            {events.length > 0 && (
              <div className="mt-3 space-y-1 max-h-32 overflow-y-auto">
                {events.slice(-8).map((e, i) => (
                  <p key={i} className="text-[10px] font-mono text-mist/30">{e}</p>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right: results */}
        <div>
          {run?.status === "complete" && run.result ? (
            <ContentPanel result={run.result} />
          ) : run?.status === "running" || run?.status === "queued" ? (
            <Card className="flex flex-col items-center gap-4 py-16">
              <Loader2 className="w-10 h-10 text-gold animate-spin" />
              <p className="text-mist/50">
                {currentNode ? `Running: ${currentNode}…` : "Initialising pipeline…"}
              </p>
              <p className="text-xs text-mist/30 font-mono">Live updates via SSE</p>
            </Card>
          ) : run?.status === "error" ? (
            <Card className="flex flex-col items-center gap-4 py-16">
              <XCircle className="w-10 h-10 text-red-400" />
              <p className="text-red-300">Pipeline error</p>
              <p className="text-xs text-mist/30">Check API logs for details</p>
            </Card>
          ) : (
            <Card className="flex flex-col items-center gap-4 py-16">
              <Clock className="w-10 h-10 text-mist/20" />
              <p className="text-mist/40">Waiting to start…</p>
            </Card>
          )}
        </div>
      </div>
    </PageShell>
  );
}
