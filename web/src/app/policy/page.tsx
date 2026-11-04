"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Lock, RotateCcw, Save, TriangleAlert, X } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

type Policy = {
  max_refund_total_usd: number; max_emails_per_run: number; max_delete_pct: number; protected_tables: string[];
  block_schema_changes: boolean; block_network_attempts: boolean; block_over_refunds: boolean; block_broken_templates: boolean;
  block_data_leaks: boolean; warn_vip_emails: boolean; block_marketing_to_opted_out: boolean;
  glossary: { term: string; definition: string }[];
};

const TOGGLES: { key: keyof Policy; title: string; body: string; kind: "block" | "warn" }[] = [
  { key: "block_over_refunds", title: "Block risky refunds", body: "Refunds larger than the original charge, of charges already refunded, refunded twice, or that don't exist.", kind: "block" },
  { key: "block_broken_templates", title: "Block broken emails", body: "Emails with unfilled placeholders like {{first_name}} never reach customers.", kind: "block" },
  { key: "block_marketing_to_opted_out", title: "Respect unsubscribes", body: "Marketing emails to customers who opted out are blocked. Transactional emails (like refund notices) are fine.", kind: "block" },
  { key: "block_data_leaks", title: "Block data leaks", body: "Emails that contain another customer's email address or a card-like number.", kind: "block" },
  { key: "block_network_attempts", title: "Block plans that reach for the internet", body: "Any connection or DNS attempt from the sandbox locks approval.", kind: "block" },
  { key: "block_schema_changes", title: "Block schema changes", body: "DROP or CREATE TABLE are never applied automatically.", kind: "block" },
  { key: "warn_vip_emails", title: "Flag VIP recipients", body: "Show which VIP customers would be emailed.", kind: "warn" },
];

const NUMBERS: { key: keyof Policy; title: string; body: string; unit: string; kind: "block" | "warn" }[] = [
  { key: "max_delete_pct", title: "Max rows deleted", body: "Deleting more than this share of any table is blocked.", unit: "% of a table", kind: "block" },
  { key: "max_refund_total_usd", title: "Large payout review", body: "Flag rehearsals that pay out more than this in total.", unit: "USD", kind: "warn" },
  { key: "max_emails_per_run", title: "Bulk email review", body: "Flag rehearsals that send more emails than this.", unit: "emails", kind: "warn" },
];

function Kind({ kind }: { kind: "block" | "warn" }) {
  return kind === "block"
    ? <span className="inline-flex items-center gap-1 rounded-full bg-foreground px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-background"><Lock className="size-3" />blocks</span>
    : <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground"><TriangleAlert className="size-3" />warns</span>;
}

export default function PolicyPage() {
  const [saved, setSaved] = useState<Policy | null>(null);
  const [draft, setDraft] = useState<Policy | null>(null);
  const [table, setTable] = useState("");
  const [term, setTerm] = useState("");
  const [definition, setDefinition] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { fetch("/api/policy").then((r) => r.json()).then((d) => { setSaved(d.policy); setDraft(d.policy); }).catch(() => toast.error("Couldn't load the policy")); }, []);
  const dirty = useMemo(() => JSON.stringify(saved) !== JSON.stringify(draft), [saved, draft]);
  const set = <K extends keyof Policy>(k: K, v: Policy[K]) => setDraft((d) => (d ? { ...d, [k]: v } : d));

  async function save() {
    if (!draft) return;
    setBusy(true);
    const r = await fetch("/api/policy", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draft) });
    const d = await r.json().catch(() => ({}));
    setBusy(false);
    if (!r.ok) return toast.error(d.detail || "Couldn't save");
    setSaved(d.policy); setDraft(d.policy); toast.success("Policy saved. It applies to the next rehearsal.");
  }

  return (
    <div className="min-h-dvh">
      <AppHeader right={
        <>
          <Button variant="outline" className="h-8 rounded-full px-3" disabled={!dirty || busy} onClick={() => setDraft(saved)}><RotateCcw className="size-3.5" /> Discard</Button>
          <Button className="h-8 rounded-full px-3" disabled={!dirty || busy} onClick={save}><Save className="size-3.5" /> Save policy</Button>
        </>
      } />
      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <div className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Approval policy</div>
        <h1 className="mt-2 font-display text-5xl">The rules every <em>rehearsal</em> must pass.</h1>
        <p className="mt-3 max-w-xl text-muted-foreground">These checks run on the measured outcome of every rehearsal, with no AI involved. Anything that <b className="font-medium text-foreground">blocks</b> locks the Approve button. Anything that <b className="font-medium text-foreground">warns</b> is shown to the approver.</p>

        {!draft ? <div className="mt-10 h-64 animate-pulse rounded-2xl bg-muted" /> : (
          <div className="mt-10 space-y-8">
            <section className="divide-y rounded-2xl border bg-card">
              {TOGGLES.map((t) => (
                <label key={t.key} className="flex cursor-pointer items-start justify-between gap-6 p-5">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 font-medium">{t.title} <Kind kind={t.kind} /></div>
                    <p className="mt-1 text-sm text-muted-foreground">{t.body}</p>
                  </div>
                  <Switch checked={draft[t.key] as boolean} onCheckedChange={(v) => set(t.key, v as never)} className="mt-1" />
                </label>
              ))}
            </section>

            <section className="divide-y rounded-2xl border bg-card">
              {NUMBERS.map((n) => (
                <div key={n.key} className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 font-medium">{n.title} <Kind kind={n.kind} /></div>
                    <p className="mt-1 text-sm text-muted-foreground">{n.body}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Input type="number" min={0} value={String(draft[n.key])} onChange={(e) => set(n.key, Math.max(0, Number(e.target.value) || 0) as never)} className="h-9 w-28 text-right font-mono" />
                    <span className="w-24 text-sm text-muted-foreground">{n.unit}</span>
                  </div>
                </div>
              ))}
            </section>

            <section className="rounded-2xl border bg-card p-5">
              <div className="flex flex-wrap items-center gap-2 font-medium">Protected tables <Kind kind="block" /></div>
              <p className="mt-1 text-sm text-muted-foreground">Any delete in these tables is blocked, even a single row.</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {draft.protected_tables.map((t) => (
                  <span key={t} className="inline-flex items-center gap-1.5 rounded-full border bg-background py-1 pl-3 pr-1.5 font-mono text-sm">
                    {t}<button aria-label={`Unprotect ${t}`} onClick={() => set("protected_tables", draft.protected_tables.filter((x) => x !== t))} className="rounded-full p-0.5 hover:bg-muted"><X className="size-3.5" /></button>
                  </span>
                ))}
                <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); const t = table.trim(); if (/^[A-Za-z_]\w*$/.test(t) && !draft.protected_tables.includes(t)) set("protected_tables", [...draft.protected_tables, t]); setTable(""); }}>
                  <Input value={table} onChange={(e) => setTable(e.target.value)} placeholder="orders" className="h-8 w-32 font-mono" />
                  <Button type="submit" variant="outline" className="h-8 rounded-full px-3">Protect</Button>
                </form>
              </div>
            </section>
            <section className="rounded-2xl border bg-card p-5">
              <div className="flex flex-wrap items-center gap-2 font-medium">Business glossary <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">verifier only</span></div>
              <p className="mt-1 text-sm text-muted-foreground">How your company defines its terms. Stunt Double&apos;s verifier checks every plan against these definitions, even when the agent that wrote the plan never knew them.</p>
              <ul className="mt-4 space-y-2">
                {draft.glossary.map((g, i) => (
                  <li key={g.term + i} className="flex items-start justify-between gap-3 rounded-xl border bg-background p-3">
                    <div className="min-w-0"><div className="font-mono text-sm">{g.term}</div><p className="mt-0.5 text-sm text-muted-foreground">{g.definition}</p></div>
                    <button aria-label={`Remove ${g.term}`} onClick={() => set("glossary", draft.glossary.filter((_, j) => j !== i))} className="rounded-full p-1 hover:bg-muted"><X className="size-3.5" /></button>
                  </li>
                ))}
              </ul>
              <form className="mt-3 grid gap-2 sm:grid-cols-[180px_1fr_auto]" onSubmit={(e) => { e.preventDefault(); if (term.trim() && definition.trim()) { set("glossary", [...draft.glossary, { term: term.trim(), definition: definition.trim() }]); setTerm(""); setDefinition(""); } }}>
                <Input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="churned" maxLength={80} className="h-9 font-mono" />
                <Input value={definition} onChange={(e) => setDefinition(e.target.value)} placeholder="no order in the last 90 days" maxLength={600} className="h-9" />
                <Button type="submit" variant="outline" className="h-9 rounded-full px-4">Add</Button>
              </form>
            </section>
            <p className={cn("text-sm", dirty ? "text-foreground" : "text-muted-foreground")}>{dirty ? "You have unsaved changes." : "Saved. The demo's Reset button restores the defaults."}</p>
          </div>
        )}
      </main>
    </div>
  );
}
