"use client";

import { useEffect, useState } from "react";
import { RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AppHeader } from "@/components/app-header";
import { num, usd } from "@/lib/api";

type Delivery = { id: number; connector: string; method: string; path: string; body: string; run_id: string; created_at: string; status: number };
type Ledger = { count: number; total_cents: number; refunds: { id: string; charge_id: number; amount_cents: number; reason: string; run_id: string; created_at: string }[] };

export default function LedgerPage() {
  const [data, setData] = useState<Ledger | null>(null);
  const [out, setOut] = useState<{ count: number; deliveries: Delivery[] } | null>(null);
  const load = () => {
    fetch("/api/beanpay/ledger", { cache: "no-store" }).then((r) => r.json()).then(setData).catch(() => setData(null));
    fetch("/api/outbox", { cache: "no-store" }).then((r) => r.json()).then(setOut).catch(() => setOut(null));
  };
  useEffect(() => { load(); }, []);
  return (
    <div className="min-h-dvh">
      <AppHeader right={<Button variant="outline" className="h-8 rounded-full px-3" onClick={load}><RotateCw className="size-3.5" /> Refresh</Button>} />
      <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <div className="eyebrow">Outbox · what actually left the building</div>
        <h1 className="mt-2 font-display text-5xl">Only after <em>approval.</em></h1>
        <p className="mt-2 max-w-xl text-muted-foreground">Every refund, API call and email here happened for real, and only after a human approved a rehearsal. Rehearsals never reach any of them. Emails land in the <a href="/mail/" target="_blank" rel="noreferrer" className="underline underline-offset-4">inbox</a>.</p>
        <h2 className="mt-10 font-display text-3xl">BeanPay refunds</h2>
        <div className="mt-8 grid grid-cols-2 gap-3 sm:max-w-md">
          <div className="rounded-xl border bg-card p-4"><div className="text-[11px] uppercase tracking-wider text-muted-foreground">Refunds</div><div className="mt-1 font-mono text-3xl tabular">{data ? num(data.count) : "—"}</div></div>
          <div className="rounded-xl border bg-card p-4"><div className="text-[11px] uppercase tracking-wider text-muted-foreground">Total</div><div className="mt-1 font-mono text-3xl tabular">{data ? usd(data.total_cents) : "—"}</div></div>
        </div>
        <div className="mt-8 overflow-x-auto rounded-2xl border bg-card">
          <table className="w-full min-w-[640px] font-mono text-[13px]">
            <thead><tr className="border-b text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              {["refund", "charge", "amount", "reason", "approved run", "time (UTC)"].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}
            </tr></thead>
            <tbody>
              {data?.refunds.length ? data.refunds.map((r) => (
                <tr key={r.id} className="border-b last:border-0">
                  <td className="px-4 py-2.5">{r.id}</td><td className="px-4 py-2.5">#{r.charge_id}</td><td className="px-4 py-2.5">{usd(r.amount_cents)}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{r.reason}</td><td className="px-4 py-2.5 text-muted-foreground">{r.run_id}</td><td className="px-4 py-2.5 text-muted-foreground">{r.created_at}</td>
                </tr>
              )) : <tr><td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">No refunds yet. Approve a rehearsal in the console.</td></tr>}
            </tbody>
          </table>
        </div>
        <h2 className="mt-12 font-display text-3xl">API deliveries</h2>
        <p className="mt-1 text-sm text-muted-foreground">Recorded in the sandbox as <span className="font-mono">ctx.http</span> calls, delivered through a connector with server-side credentials after approval.</p>
        <div className="mt-4 space-y-2">
          {out?.deliveries.length ? out.deliveries.map((d) => (
            <div key={d.id} className="rounded-xl border bg-card p-4">
              <div className="flex flex-wrap items-center gap-2 font-mono text-[12px]">
                <span className="rounded bg-foreground px-1.5 py-0.5 text-background">{d.connector}</span><span>{d.method} {d.path}</span>
                <span className="ml-auto text-muted-foreground">{d.run_id} · {d.created_at} UTC</span>
              </div>
              <pre className="mt-2 overflow-x-auto font-mono text-[12px] text-muted-foreground">{d.body}</pre>
            </div>
          )) : <div className="rounded-xl border bg-card p-6 text-center text-sm text-muted-foreground">No API deliveries yet. Try the “Post the refund summary to Slack” preset and approve it.</div>}
        </div>
      </main>
    </div>
  );
}
