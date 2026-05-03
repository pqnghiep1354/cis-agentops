"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Upload, Zap, BookOpen, BarChart3,
  Mountain, ChevronRight,
} from "lucide-react";
import clsx from "clsx";

const NAV = [
  { href: "/",        icon: LayoutDashboard, label: "Dashboard" },
  { href: "/upload",  icon: Upload,          label: "Upload & Run" },
  { href: "/pipeline",icon: Zap,             label: "Pipeline" },
  { href: "/results", icon: BookOpen,        label: "Published Tours" },
  { href: "/eval",    icon: BarChart3,       label: "Evaluation" },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="fixed left-0 top-0 h-screen w-56 bg-ink-light border-r border-white/5 flex flex-col z-40">
      {/* Logo */}
      <div className="px-5 py-6 border-b border-white/5">
        <div className="flex items-center gap-2.5">
          <Mountain className="w-5 h-5 text-gold" />
          <div>
            <p className="font-display text-sm text-mist leading-none">Adventure Asia</p>
            <p className="text-[10px] text-mist/40 font-mono mt-0.5">CIS AgentOps</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = path === href || (href !== "/" && path.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150",
                active
                  ? "bg-gold/10 text-gold border border-gold/20"
                  : "text-mist/50 hover:text-mist hover:bg-white/5 border border-transparent"
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="flex-1">{label}</span>
              {active && <ChevronRight className="w-3 h-3 opacity-50" />}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-white/5">
        <p className="text-[10px] text-mist/25 font-mono">v1.0 · Capstone 2026</p>
      </div>
    </aside>
  );
}

export function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 ml-56 min-h-screen p-8">
        {children}
      </main>
    </div>
  );
}

export function PageHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-8">
      <h1 className="font-display text-3xl text-mist">{title}</h1>
      {sub && <p className="text-mist/50 mt-1 text-sm">{sub}</p>}
    </div>
  );
}

export function Card({
  children, className, gold, onClick,
}: { children: React.ReactNode; className?: string; gold?: boolean; onClick?: () => void }) {
  return (
    <div
      onClick={onClick}
      className={clsx(
        "rounded-xl border p-5",
        gold
          ? "bg-gold/5 border-gold/20"
          : "bg-ink-light border-white/5",
        className
      )}
    >
      {children}
    </div>
  );
}

export function Badge({ label, color = "default" }: { label: string; color?: "gold" | "green" | "red" | "yellow" | "default" }) {
  const cls = {
    gold:    "bg-gold/15 text-gold border-gold/30",
    green:   "bg-green-500/15 text-green-400 border-green-500/30",
    red:     "bg-red-500/15 text-red-400 border-red-500/30",
    yellow:  "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
    default: "bg-white/5 text-mist/60 border-white/10",
  }[color];
  return (
    <span className={clsx("inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono border", cls)}>
      {label}
    </span>
  );
}

export function ScoreRing({ score, size = 64 }: { score: number; size?: number }) {
  const r = (size / 2) - 6;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(score / 10, 1);
  const dash = pct * circ;
  const color = score >= 7 ? "#22c55e" : score >= 5 ? "#f59e0b" : "#ef4444";
  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="4" />
      <circle
        cx={size/2} cy={size/2} r={r}
        fill="none" stroke={color} strokeWidth="4"
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.8s ease" }}
      />
      <text
        x="50%" y="50%" textAnchor="middle" dominantBaseline="middle"
        className="rotate-90" style={{ fill: color, fontSize: size * 0.24, fontFamily: "monospace", transform: `rotate(90deg)`, transformOrigin: "50% 50%" }}
      >
        {score.toFixed(1)}
      </text>
    </svg>
  );
}

export function StatusDot({ status }: { status: string }) {
  const cls = {
    queued:   "bg-white/20",
    running:  "bg-gold animate-pulse",
    complete: "bg-green-500",
    error:    "bg-red-500",
  }[status] ?? "bg-white/20";
  return <span className={clsx("inline-block w-2 h-2 rounded-full", cls)} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("rounded bg-white/5 shimmer", className)} />;
}
