"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Check, Fingerprint, Lock, RotateCw, ShieldAlert, X } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { api, num, usd, type RunSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

const LABEL: Record<string, string> = { review: "awaiting approval", applied: "applied", rejected: "rejected", drifted: "drift: not applied", failed: "failed",
  queued: "queued", planning: "planning", rehearsing: "rehearsing", verifying: "verifying", applying: "applying" };

function StatusPill({ r }: { r: RunSummary }) {
  const icon = r.status === "applied" ? <Check className="size-3" /> : r.status === "rejected" ? <X className="size-3" /> : r.blocked ? <Lock className="size-3" /> : r.status === "drifted" || r.status === "failed" ? <ShieldAlert className="size-3" /> : null;
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 font-mono text-[11px]",
      r.status === "applied" && "border-foreground bg-foreground text-background", (r.blocked || r.status === "drifted" || r.status === "failed") && r.status !== "applied" && "border-damage/40 text-damage")}>
      {icon}{r.blocked && r.status === "review" ? "blocked by policy" : LABEL[r.status] ?? r.status}
    </span>
  );
}

export default function HistoryPage() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [filter, setFilter] = useState<"all" | "waiting" | "applied" | "blocked" | "undo">("all");
  const [q, setQ] = useState("");
  const load = () => api.runs().then(setRuns).catch(() => setRuns([]));
  useEffect(() => { load(); }, []);
  const applied = runs?.filter((r) => r.status === "applied") ?? [];
  const FILTERS: { key: typeof filter; label: string; test: (r: RunSummary) => boolean }[] = [
    { key: "all", label: "All", test: () => true },
    { key: "waiting", label: "Awaiting approval", test: (r) => r.status === "review" && !r.blocked },
    { key: "applied", label: "Applied", test: (r) => r.status === "applied" },
    { key: "blocked", label: "Stopped", test: (r) => r.blocked || r.status === "rejected" || r.status === "drifted" },
    { key: "undo", label: "Undos", test: (r) => r.mode === "rollback" },
  ];
  const shown = (runs ?? []).filter((r) => FILTERS.find((f) => f.key === filter)!.test(r) && (!q || r.task.toLowerCase().includes(q.toLowerCase()) || r.id.includes(q)));
  const contained = runs?.filter((r) => r.blocked || r.status === "rejected") ?? [];
  return (
    <div className="min-h-dvh">
      <AppHeader right={<div className="flex gap-2"><a href="/api/runs.csv" className="inline-flex h-8 items-center rounded-full border px-3 text-sm hover:bg-accent">Export CSV ↓</a><Button variant="outline" className="h-8 rounded-full px-3" onClick={load}><RotateCw className="size-3.5" /> Refresh</Button></div>} />
      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <div className="eyebrow">Audit trail</div>
        <h1 className="mt-2 font-display text-5xl">Every rehearsal, <em>on the record.</em></h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">Each approval is bound to a fingerprint of the exact plan and the exact recorded effects. What was applied is provably what was approved.</p>
        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[["rehearsals", num(runs?.length ?? 0)], ["applied", num(applied.length)], ["stopped before damage", num(contained.length)],
            ["money moved after approval", usd(applied.reduce((s, r) => s + (r.apply_result?.refund_total_cents ?? 0), 0))]].map(([k, v]) => (
            <div key={k} className="rounded-xl border bg-card p-4"><div className="text-[11px] uppercase tracking-wider text-muted-foreground">{k}</div><div className="mt-1 font-mono text-2xl tabular">{v}</div></div>
          ))}
        </div>
        <div className="mt-8 flex flex-wrap items-center gap-2">
          {FILTERS.map((f) => {
            const n = (runs ?? []).filter(f.test).length;
            return (
              <button key={f.key} onClick={() => setFilter(f.key)} className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm", filter === f.key ? "border-foreground bg-foreground text-background" : "text-muted-foreground hover:text-foreground")}>
                {f.label}<span className={cn("font-mono text-[11px]", filter === f.key ? "opacity-70" : "")}>{n}</span>
              </button>
            );
          })}
          <input aria-label="Search runs" placeholder="Search requests or run ids…" value={q} onChange={(e) => setQ(e.target.value)}
            className="ml-auto h-9 w-full rounded-full border bg-background px-4 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50 sm:w-72" />
        </div>
        <div className="mt-4 overflow-x-auto rounded-2xl border bg-card">
          <table className="w-full min-w-[860px] text-sm">
            <thead><tr className="border-b text-left font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              {["when", "request", "status", "money out", "emails", "rows", "attempts", "plan fingerprint", ""].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}
            </tr></thead>
            <tbody>
              {runs === null ? <tr><td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">Loading…</td></tr>
                : runs.length === 0 ? <tr><td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">No rehearsals yet. <Link href="/app" className="underline underline-offset-4">Run one in the console.</Link></td></tr>
                : shown.length === 0 ? <tr><td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">Nothing matches this filter.</td></tr>
                : shown.map((r) => (
                  <tr key={r.id} className="border-b last:border-0 hover:bg-muted/40">
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-[12px] text-muted-foreground">{new Date(r.created_at * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</td>
                    <td className="max-w-[320px] truncate px-4 py-3" title={r.task}>{r.mode === "rollback" ? <span className="mr-1.5 rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase">undo</span> : null}{r.task}</td>
                    <td className="px-4 py-3"><StatusPill r={r} /></td>
                    <td className={cn("px-4 py-3 font-mono tabular", r.money_cents && r.status !== "applied" && r.verdict && r.verdict !== "looks_right" && "text-damage")}>{usd(r.money_cents)}</td>
                    <td className="px-4 py-3 font-mono tabular">{num(r.emails)}</td>
                    <td className="px-4 py-3 font-mono tabular">{num(r.rows)}</td>
                    <td className="px-4 py-3 font-mono tabular">{r.attempts}</td>
                    <td className="px-4 py-3 font-mono text-[12px] text-muted-foreground">{r.plan_sha256 ? <span className="inline-flex items-center gap-1"><Fingerprint className="size-3.5" />{r.plan_sha256.slice(0, 12)}</span> : "—"}</td>
                    <td className="px-4 py-3 text-right"><Link href={`/app?run=${r.id}`} className="whitespace-nowrap text-[13px] underline-offset-4 hover:underline">Open →</Link></td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
