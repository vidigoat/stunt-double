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
  const load = () => api.runs().then(setRuns).catch(() => setRuns([]));
  useEffect(() => { load(); }, []);
  const applied = runs?.filter((r) => r.status === "applied") ?? [];
  const contained = runs?.filter((r) => r.blocked || r.status === "rejected") ?? [];
  return (
    <div className="min-h-dvh">
      <AppHeader right={<Button variant="outline" className="h-8 rounded-full px-3" onClick={load}><RotateCw className="size-3.5" /> Refresh</Button>} />
      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <div className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Audit trail</div>
        <h1 className="mt-2 font-display text-5xl">Every rehearsal, <em>on the record.</em></h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">Each approval is bound to a fingerprint of the exact plan and the exact recorded effects. What was applied is provably what was approved.</p>
        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[["rehearsals", num(runs?.length ?? 0)], ["applied", num(applied.length)], ["stopped before damage", num(contained.length)],
            ["money moved after approval", usd(applied.reduce((s, r) => s + (r.apply_result?.refund_total_cents ?? 0), 0))]].map(([k, v]) => (
            <div key={k} className="rounded-xl border bg-card p-4"><div className="text-[11px] uppercase tracking-wider text-muted-foreground">{k}</div><div className="mt-1 font-mono text-2xl tabular">{v}</div></div>
          ))}
        </div>
        <div className="mt-8 overflow-x-auto rounded-2xl border bg-card">
          <table className="w-full min-w-[860px] text-sm">
            <thead><tr className="border-b text-left font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              {["when", "request", "status", "money out", "emails", "rows", "attempts", "plan fingerprint", ""].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}
            </tr></thead>
            <tbody>
              {runs === null ? <tr><td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">Loading…</td></tr>
                : runs.length === 0 ? <tr><td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">No rehearsals yet. <Link href="/app" className="underline underline-offset-4">Run one in the console.</Link></td></tr>
                : runs.map((r) => (
                  <tr key={r.id} className="border-b last:border-0 hover:bg-muted/40">
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-[12px] text-muted-foreground">{new Date(r.created_at * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</td>
                    <td className="max-w-[320px] truncate px-4 py-3" title={r.task}>{r.task}</td>
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
