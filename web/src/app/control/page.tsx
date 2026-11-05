"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bot, Cloud, CreditCard, Database, Mail, MousePointerClick, ShieldCheck, User, Webhook } from "lucide-react";
import { Mark } from "@/components/brand";
import { BrandLogo } from "@/components/brand-logos";
import { cn } from "@/lib/utils";
import { CountUp } from "@/components/count-up";
import { usd } from "@/lib/api";

type Row = {
  id: string; task: string; mode: string; status: string; created_at: number; verdict: string | null; blocked: boolean;
  money_cents: number; rows: number; headline?: string | null; top_flag?: string | null; kind?: string | null;
  sandbox?: { id?: string; runtime?: string; wall_ms?: number; profile?: string; isolation?: string } | null;
  approval?: { auto?: boolean } | null;
};
type Stats = { rehearsals: number; stopped: number; money_prevented_cents: number; rows_protected: number; applied: number };
type Health = { sandbox_runtime?: string; agent_model?: string; inference_configured?: boolean };

const KIND: Record<string, { icon: typeof Database; label: string }> = {
  data: { icon: Database, label: "database double" }, money: { icon: CreditCard, label: "payments double" }, email: { icon: Mail, label: "email double" },
  api: { icon: Webhook, label: "API double" }, browser: { icon: MousePointerClick, label: "browser double" }, cloud: { icon: Cloud, label: "Vultr fleet double" },
};
const STAGES = ["plan", "rehearse", "verify", "decide"] as const;
function stageOf(r: Row): number {
  if (r.status === "queued" || r.status === "planning") return 0;
  if (r.status === "rehearsing") return 1;
  if (r.status === "verifying") return 2;
  return 3;
}

function Pipeline({ r, live }: { r: Row; live: boolean }) {
  const at = stageOf(r);
  const skippedAi = !live && r.blocked && !r.verdict;
  return (
    <div className="mt-1.5 flex items-center gap-1" aria-label={`stage: ${STAGES[at]}`}>
      {STAGES.map((st, i) => (
        <span key={st} className={cn("h-1 w-7 rounded-full transition-colors duration-500",
          i < at ? (st === "verify" && skippedAi ? "bg-white/15" : "bg-white/45") : i === at ? (live ? "animate-pulse bg-[#5B8CFF]" : "bg-white/70") : "bg-white/10")} title={st} />
      ))}
      <span className="ml-1 whitespace-nowrap text-[10px] uppercase tracking-[0.14em] text-white/35">{live ? `${STAGES[at]}…` : skippedAi ? "rules · no AI" : r.verdict ? "AI checked" : "done"}</span>
    </div>
  );
}

const ACTIVE = new Set(["queued", "planning", "rehearsing", "verifying", "applying"]);

function decision(r: Row): { label: string; tone: "run" | "bad" | "warn" | "ok" | "neutral" } {
  if (ACTIVE.has(r.status)) return { label: r.status === "verifying" ? "AI verifier investigating…" : r.status === "applying" ? "applying for real…" : "rehearsing…", tone: "run" };
  if (r.status === "applied") return { label: r.approval?.auto ? "auto-applied within the autonomy budget" : "applied after approval", tone: "ok" };
  if (r.status === "rejected") return { label: "rejected by a human", tone: "neutral" };
  if (r.status === "failed") return { label: "failed safely", tone: "neutral" };
  if (r.blocked) return { label: r.top_flag ? `blocked: ${r.top_flag}` : "blocked by policy", tone: "bad" };
  if (r.verdict === "concerns" || r.verdict === "dangerous") return { label: r.headline ?? "the AI objected", tone: "warn" };
  return { label: r.headline ?? "waiting for a human", tone: "ok" };
}

/** Mission Control: every agent action flowing through its double on Vultr, live. */
export default function ControlPage() {
  const [runs, setRuns] = useState<Row[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const [r, s] = await Promise.all([fetch("/api/runs", { cache: "no-store" }).then((x) => x.json()), fetch("/api/stats", { cache: "no-store" }).then((x) => x.json())]);
        if (!stop) { setRuns(r.slice(0, 14)); setStats(s); }
      } catch { /* keep the last frame */ }
    };
    tick();
    fetch("/api/health", { cache: "no-store" }).then((x) => x.json()).then(setHealth).catch(() => {});
    const t = setInterval(tick, 1500);
    return () => { stop = true; clearInterval(t); };
  }, []);

  return (
    <div className="min-h-dvh bg-[#0A0A0B] text-white">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-white/10 px-6 py-4">
        <Link href="/" className="flex items-center gap-2"><Mark className="size-6 text-white" /><span className="font-display text-xl">Stunt <em>Double</em></span></Link>
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/50">Mission control</span>
        <span className="inline-flex items-center gap-2 rounded-full border border-white/15 px-3 py-1 font-mono text-[11px] text-white/70">
          <span className="relative flex size-2"><span className="absolute inline-flex size-full animate-ping rounded-full bg-[#3DD68C] opacity-60" /><span className="relative inline-flex size-2 rounded-full bg-[#3DD68C]" /></span>
          live · <BrandLogo name="vultr" tone="brand" className="size-3" /> {health?.sandbox_runtime === "runsc" ? "gVisor" : health?.sandbox_runtime ?? "sandbox"} · {health?.agent_model ?? "…"}
        </span>
        <Link href="/app" className="ml-auto rounded-full bg-white px-4 py-1.5 text-sm font-medium text-black hover:bg-white/90">Open the console</Link>
      </header>

      <div className="grid grid-cols-2 gap-px border-b border-white/10 bg-white/10 lg:grid-cols-4">
        {([["rehearsals", stats?.rehearsals ?? 0, "num"], ["stopped before damage", stats?.stopped ?? 0, "num"], ["money kept", stats?.money_prevented_cents ?? 0, "usd"], ["rows protected", stats?.rows_protected ?? 0, "num"]] as const).map(([k, v, f]) => (
          <div key={k} className="bg-[#0A0A0B] px-6 py-5"><div className={cn("font-mono text-3xl tabular", k === "stopped before damage" && v ? "text-[#FF8A8F]" : k === "money kept" && v ? "text-[#3DD68C]" : "")}><CountUp value={v} format={f} /></div><div className="mt-1 text-xs text-white/50">{k}</div></div>
        ))}
      </div>

      <div className="hidden grid-cols-[minmax(0,4fr)_minmax(0,3fr)_minmax(0,4fr)] gap-4 px-6 pt-5 font-mono text-[11px] uppercase tracking-[0.18em] text-white/40 md:grid">
        <div>The request</div><div>The double, on Vultr</div><div>The decision</div>
      </div>
      <ol className="space-y-2 px-6 py-4">
        {runs.length === 0 ? <li className="py-16 text-center text-white/50">No rehearsals yet. <Link className="underline underline-offset-4" href="/app">Run one in the console</Link> and watch it arrive here.</li> : null}
        {runs.map((r) => {
          const d = decision(r);
          const K = KIND[r.kind ?? "data"] ?? KIND.data;
          const live = ACTIVE.has(r.status);
          return (
            <li key={r.id} className={cn("animate-rise grid gap-3 rounded-xl border bg-white/[0.03] p-4 md:grid-cols-[minmax(0,4fr)_minmax(0,3fr)_minmax(0,4fr)] md:items-center md:gap-4",
              d.tone === "bad" ? "border-[#FF6369]/40" : d.tone === "warn" ? "border-[#FFB86B]/40" : d.tone === "ok" ? "border-white/10" : live ? "border-[#5B8CFF]/50" : "border-white/10")}>
              <div className="flex min-w-0 items-start gap-3">
                {r.mode === "agent" ? <Bot className="mt-0.5 size-4 shrink-0 text-white/60" /> : <User className="mt-0.5 size-4 shrink-0 text-white/60" />}
                <div className="min-w-0"><div className="truncate text-[15px]">“{r.task}”</div><div className="mt-0.5 font-mono text-[11px] text-white/40">{r.mode === "agent" ? "AI agent" : r.mode === "rollback" ? "undo" : "submitted plan"} · {r.id}</div></div>
              </div>
              <div className="flex min-w-0 items-center gap-3">
                <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg", live ? "bg-[#5B8CFF]/20 text-[#9FBCFF]" : "bg-white/5 text-white/70")}><K.icon className="size-4" /></span>
                <div className="min-w-0 font-mono text-[11px] leading-relaxed text-white/60">
                  <div className="text-white/85">{K.label}{r.sandbox?.isolation === "vultr_vm" ? <span className="ml-1.5 rounded bg-[#5B8CFF]/20 px-1.5 py-px text-[10px] text-[#9FBCFF]">own Vultr VM</span> : null}</div>
                  <div className="truncate">{r.sandbox?.id ?? "starting…"} · {r.sandbox?.runtime === "runsc" ? "gVisor" : r.sandbox?.runtime ?? "…"}{r.sandbox?.wall_ms ? ` · ${(r.sandbox.wall_ms / 1000).toFixed(1)} s` : ""}{r.sandbox?.id ? " · destroyed" : ""}</div>
                  <Pipeline r={r} live={live} />
                </div>
              </div>
              <div className="flex min-w-0 items-center gap-3">
                <span className={cn("size-2 shrink-0 rounded-full", d.tone === "bad" ? "bg-[#FF6369]" : d.tone === "warn" ? "bg-[#FFB86B]" : d.tone === "ok" ? "bg-[#3DD68C]" : d.tone === "run" ? "animate-pulse bg-[#5B8CFF]" : "bg-white/40")} />
                <Link href={`/app?run=${r.id}`} className="min-w-0 truncate text-[14px] hover:underline">{d.label}</Link>
                {r.money_cents ? <span className="ml-auto shrink-0 font-mono text-[11px] text-white/50">{usd(r.money_cents)}</span> : null}
              </div>
            </li>
          );
        })}
      </ol>
      <footer className="flex items-center gap-2 px-6 pb-8 text-xs text-white/40"><ShieldCheck className="size-3.5" /> Every row is a real rehearsal on this server. Production changes only after a human approves.</footer>
    </div>
  );
}
