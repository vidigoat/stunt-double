"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, Mail, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Wordmark } from "@/components/brand";
import { num, usd } from "@/lib/api";

type Ledger = { count: number; total_cents: number; refunds: { id: string; charge_id: number; amount_cents: number; reason: string; run_id: string; created_at: string }[] };

export default function LedgerPage() {
  const [data, setData] = useState<Ledger | null>(null);
  const load = () => fetch("/api/beanpay/ledger", { cache: "no-store" }).then((r) => r.json()).then(setData).catch(() => setData(null));
  useEffect(() => { load(); }, []);
  return (
    <div className="min-h-dvh">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex items-center gap-4">
            <Link href="/app" className="text-muted-foreground hover:text-foreground" aria-label="Back to console"><ArrowLeft className="size-4" /></Link>
            <Wordmark />
          </div>
          <div className="flex gap-2">
            <a href="/mail/" target="_blank" rel="noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-sm hover:bg-muted"><Mail className="size-3.5" /> Inbox</a>
            <Button variant="outline" className="h-8 rounded-full px-3" onClick={load}><RotateCw className="size-3.5" /> Refresh</Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <div className="font-mono text-xs uppercase tracking-wider text-muted-foreground">BeanPay · payments provider of Bean There Coffee Co.</div>
        <h1 className="mt-2 font-display text-5xl">Refund ledger</h1>
        <p className="mt-2 max-w-xl text-muted-foreground">Real refunds, issued only after a human approved a rehearsal. Rehearsals never reach BeanPay.</p>
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
      </main>
    </div>
  );
}
