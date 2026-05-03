"use client";
import { useEffect, useState } from "react";
import { Search, ExternalLink, MapPin, Clock, DollarSign } from "lucide-react";
import { api, Tour } from "@/lib/api";
import { PageShell, PageHeader, Card, Badge, ScoreRing, Skeleton } from "@/components/ui";

function TourCard({ tour }: { tour: Tour }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <Card className="flex flex-col gap-3 cursor-pointer hover:border-white/10 transition-colors" onClick={() => setExpanded(!expanded)}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="font-display text-base text-mist leading-tight">{tour.title || tour.tour_name}</p>
          <p className="text-xs text-gold/70 italic mt-0.5">{tour.tagline}</p>
        </div>
        <ScoreRing score={tour.quality_score} size={44} />
      </div>

      <div className="flex items-center gap-3 text-xs text-mist/40">
        <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{tour.destination}</span>
        <span className="flex items-center gap-1"><DollarSign className="w-3 h-3" />${tour.cost_usd?.toFixed(4)}</span>
        <Badge label={tour.model_used ?? "—"} />
      </div>

      {expanded && (
        <div className="border-t border-white/5 pt-3 space-y-3">
          <p className="text-sm text-mist/60 leading-relaxed">{tour.description?.slice(0, 400)}…</p>
          <div>
            <p className="text-[10px] font-mono text-mist/30 mb-1">SEO META TITLE</p>
            <p className="text-xs text-mist/50">{tour.seo_meta_title}</p>
          </div>
          <div>
            <p className="text-[10px] font-mono text-mist/30 mb-1">SEO META DESCRIPTION</p>
            <p className="text-xs text-mist/50">{tour.seo_meta_description}</p>
          </div>
          <p className="text-[10px] font-mono text-mist/20">
            Published: {new Date(tour.created_at).toLocaleString()} · ID: {tour.id.slice(0, 8)}
          </p>
        </div>
      )}
    </Card>
  );
}

export default function ResultsPage() {
  const [tours, setTours]   = useState<Tour[]>([]);
  const [total, setTotal]   = useState(0);
  const [loading, setLoading] = useState(true);
  const [q, setQ]           = useState("");

  useEffect(() => {
    api.tours(50).then(r => { setTours(r.tours); setTotal(r.total); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const filtered = tours.filter(t =>
    !q || t.tour_name.toLowerCase().includes(q.toLowerCase()) || t.destination.toLowerCase().includes(q.toLowerCase())
  );
  const avgScore = tours.length ? (tours.reduce((a, t) => a + t.quality_score, 0) / tours.length).toFixed(1) : "—";

  return (
    <PageShell>
      <PageHeader title="Published Tours" sub={`${total} tours in database`} />

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <Card><p className="text-xs text-mist/40">Total Published</p><p className="font-display text-3xl text-mist">{total}</p></Card>
        <Card gold><p className="text-xs text-mist/50">Avg Quality Score</p><p className="font-display text-3xl text-gold">{avgScore}</p></Card>
        <Card><p className="text-xs text-mist/40">Avg Cost / Tour</p>
          <p className="font-display text-3xl text-mist">
            {tours.length ? `$${(tours.reduce((a, t) => a + (t.cost_usd ?? 0), 0) / tours.length).toFixed(4)}` : "—"}
          </p>
        </Card>
      </div>

      {/* Search */}
      <div className="relative mb-5">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-mist/30" />
        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="Filter by tour name or destination…"
          className="w-full pl-9 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-lg text-sm text-mist placeholder-mist/30 focus:outline-none focus:border-gold/30"
        />
      </div>

      {/* Tours grid */}
      {loading ? (
        <div className="grid grid-cols-2 gap-4">
          {Array(6).fill(0).map((_, i) => <Skeleton key={i} className="h-32" />)}
        </div>
      ) : filtered.length === 0 ? (
        <Card className="text-center py-16">
          <p className="text-mist/40 text-sm">
            {tours.length === 0
              ? "No published tours yet. Run the pipeline to generate content."
              : `No tours matching "${q}"`}
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {filtered.map(t => <TourCard key={t.id} tour={t} />)}
        </div>
      )}
    </PageShell>
  );
}
