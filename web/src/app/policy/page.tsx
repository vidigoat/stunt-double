"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Lock, RotateCcw, Save, TriangleAlert, Users, X } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

type Policy = {
  max_refund_total_usd: number; max_emails_per_run: number; max_delete_pct: number; max_update_pct_protected: number; protected_tables: string[];
  block_schema_changes: boolean; block_network_attempts: boolean; block_over_refunds: boolean; block_broken_templates: boolean;
  block_data_leaks: boolean; warn_vip_emails: boolean; block_marketing_to_opted_out: boolean;
  glossary: { term: string; definition: string }[];
  two_person_over_usd: number; two_person_over_rows: number; two_person_for_rollbacks: boolean; max_http_per_run: number; approval_expires_hours: number; protect_production_servers: boolean; max_servers_deleted: number;
};

const TOGGLES: { key: keyof Policy; title: string; body: string; kind: "block" | "warn" | "two" }[] = [
  { key: "block_over_refunds", title: "Block risky refunds", body: "Refunds larger than the original charge, of charges already refunded, refunded twice, or that don't exist.", kind: "block" },
  { key: "block_broken_templates", title: "Block broken emails", body: "Emails with unfilled placeholders like {{first_name}} never reach customers.", kind: "block" },
  { key: "protect_production_servers", title: "Protect production servers", body: "An agent can never delete, stop or resize a Vultr server tagged 'production'.", kind: "block" },
  { key: "block_marketing_to_opted_out", title: "Respect unsubscribes", body: "Marketing emails to customers who opted out are blocked. Transactional emails (like refund notices) are fine.", kind: "block" },
  { key: "block_data_leaks", title: "Block data leaks", body: "Emails that contain another customer's email address or a card-like number.", kind: "block" },
  { key: "block_network_attempts", title: "Block plans that reach for the internet", body: "Any connection or DNS attempt from the sandbox locks approval.", kind: "block" },
  { key: "block_schema_changes", title: "Block schema changes", body: "DROP or CREATE TABLE are never applied automatically.", kind: "block" },
  { key: "two_person_for_rollbacks", title: "Two approvers for every undo", body: "Rolling back an applied run always needs two different people.", kind: "two" },
  { key: "warn_vip_emails", title: "Flag VIP recipients", body: "Show which VIP customers would be emailed.", kind: "warn" },
];

const NUMBERS: { key: keyof Policy; title: string; body: string; unit: string; kind: "block" | "warn" | "two" }[] = [
  { key: "max_delete_pct", title: "Max rows deleted", body: "Deleting more than this share of any table is blocked.", unit: "% of a table", kind: "block" },
  { key: "max_update_pct_protected", title: "Max rows rewritten in protected tables", body: "Updating more than this share of a protected table is blocked.", unit: "% of a table", kind: "block" },
  { key: "two_person_over_usd", title: "Two approvers above", body: "Payouts above this need two different people to approve.", unit: "USD", kind: "two" },
  { key: "two_person_over_rows", title: "Two approvers for large changes", body: "Changing more rows than this needs two different people.", unit: "rows", kind: "two" },
  { key: "approval_expires_hours", title: "Rehearsals expire after", body: "An old rehearsal can't be approved. The business moved on, so rehearse again (0 = never).", unit: "hours", kind: "block" },
  { key: "max_servers_deleted", title: "Server deletion review", body: "Flag rehearsals that delete more Vultr servers than this.", unit: "servers", kind: "warn" },
  { key: "max_refund_total_usd", title: "Large payout review", body: "Flag rehearsals that pay out more than this in total.", unit: "USD", kind: "warn" },
  { key: "max_emails_per_run", title: "Bulk email review", body: "Flag rehearsals that send more emails than this.", unit: "emails", kind: "warn" },
];

function Kind({ kind }: { kind: "block" | "warn" | "two" }) {
  if (kind === "two") return <span className="inline-flex items-center gap-1 rounded-full border border-foreground px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider"><Users className="size-3" />2 people</span>;
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
  type Change = { at: number; by: string; changes: Record<string, [unknown, unknown]> };
  const [history, setHistory] = useState<Change[]>([]);
  const loadHistory = () => fetch("/api/policy/history").then((r) => r.json()).then((d) => setHistory(d.history ?? [])).catch(() => {});
  type Learned = { id: string; title: string; sql: string; source_run: string; by: string; created_at: number };
  const [learned, setLearned] = useState<Learned[]>([]);
  const loadRules = () => fetch("/api/rules").then((r) => r.json()).then((d) => setLearned(d.rules ?? [])).catch(() => {});
  useEffect(() => { loadRules(); }, []);
  useEffect(() => { loadHistory(); }, []);
  const dirty = useMemo(() => JSON.stringify(saved) !== JSON.stringify(draft), [saved, draft]);
  type Sim = { considered: number; newly_blocked: number; unblocked: number; now_two_person: number;
    changed: { id: string; task: string; blocked_before: boolean; blocked_after: boolean; approvers_before: number; approvers_after: number; new_reasons: string[] }[] };
  const [sim, setSim] = useState<Sim | null>(null);
  useEffect(() => {
    if (!dirty || !draft) { setSim(null); return; }
    const t = setTimeout(() => {
      fetch("/api/policy/simulate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draft) })
        .then((r) => (r.ok ? r.json() : null)).then(setSim).catch(() => setSim(null));
    }, 300);
    return () => clearTimeout(t);
  }, [dirty, draft]);
  const set = <K extends keyof Policy>(k: K, v: Policy[K]) => setDraft((d) => (d ? { ...d, [k]: v } : d));

  async function save() {
    if (!draft) return;
    setBusy(true);
    let by = "";
    try { by = localStorage.getItem("sd-approver") || ""; } catch { /* storage unavailable */ }
    const r = await fetch(`/api/policy?by=${encodeURIComponent(by)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draft) });
    const d = await r.json().catch(() => ({}));
    setBusy(false);
    if (!r.ok) return toast.error(d.detail || "Couldn't save");
    setSaved(d.policy); setDraft(d.policy); loadHistory(); toast.success("Policy saved. It also applies to rehearsals still waiting for approval.");
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
        <div className="eyebrow">Approval policy</div>
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
            {dirty && sim ? (
              <section className="rounded-2xl border border-foreground bg-card p-5">
                <div className="font-medium">Impact preview, before you save</div>
                <p className="mt-1 text-sm text-muted-foreground">Re-checked against the last {sim.considered} rehearsals on this server.</p>
                <div className="mt-4 grid grid-cols-3 gap-2 font-mono text-sm">
                  {[["newly blocked", sim.newly_blocked], ["unblocked", sim.unblocked], ["now need 2 approvers", sim.now_two_person]].map(([k, v]) => (
                    <div key={k as string} className="rounded-lg border bg-background px-3 py-2"><div className="text-xl tabular">{v as number}</div><div className="text-[11px] text-muted-foreground">{k as string}</div></div>
                  ))}
                </div>
                {sim.changed.length ? (
                  <ul className="mt-3 space-y-1.5 text-sm">
                    {sim.changed.slice(0, 6).map((c) => (
                      <li key={c.id} className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border bg-background px-3 py-2">
                        <span className="min-w-0 truncate">{c.task}</span>
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {c.blocked_before !== c.blocked_after ? (c.blocked_after ? "→ blocked" : "→ unblocked") : ""}{c.approvers_before !== c.approvers_after ? ` · ${c.approvers_before}→${c.approvers_after} approvers` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="mt-3 text-sm text-muted-foreground">No recent rehearsal would be affected.</p>}
              </section>
            ) : null}
            <p className={cn("text-sm", dirty ? "text-foreground" : "text-muted-foreground")}>{dirty ? "You have unsaved changes." : "Saved. The demo's Reset button restores the defaults."}</p>
            <section className="rounded-2xl border bg-card p-6">
              <div className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Learned rules · AI catches a human turned into checks · they run without AI</div>
              {learned.length ? (
                <ul className="mt-3 divide-y">
                  {learned.map((r) => (
                    <li key={r.id} className="py-3">
                      <div className="flex flex-wrap items-baseline gap-x-3">
                        <span className="font-medium">{r.title}</span>
                        <a href={`/app?run=${r.source_run}`} className="font-mono text-xs text-muted-foreground underline-offset-4 hover:underline">from {r.source_run}</a>
                        {r.by ? <span className="text-xs text-muted-foreground">by {r.by}</span> : null}
                        <button className="ml-auto text-xs text-muted-foreground underline-offset-4 hover:text-damage hover:underline" onClick={async () => {
                          await fetch(`/api/rules/${r.id}`, { method: "DELETE" }); loadRules(); toast.success("Rule removed");
                        }}>Remove</button>
                      </div>
                      <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-muted px-3 py-2 font-mono text-[11px]">{r.sql}</pre>
                    </li>
                  ))}
                </ul>
              ) : <p className="mt-3 text-sm text-muted-foreground">None yet. When the AI verifier catches a mistake, it proposes the check it used; &quot;Learn this rule&quot; on the run adds it here.</p>}
            </section>
            <section className="rounded-2xl border bg-card p-6">
              <div className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Change history · policy edits are on the record too</div>
              {history.length ? (
                <ul className="mt-3 divide-y text-sm">
                  {history.map((h) => (
                    <li key={h.at} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2">
                      <span className="font-mono text-xs text-muted-foreground">{new Date(h.at * 1000).toLocaleString()}</span>
                      <span className="font-medium">{h.by}</span>
                      <span className="min-w-0 break-words font-mono text-xs">
                        {Object.entries(h.changes).map(([k, [a, b]]) => `${k}: ${JSON.stringify(a)} → ${JSON.stringify(b)}`).join(" · ").slice(0, 400)}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : <p className="mt-3 text-sm text-muted-foreground">No changes since the last reset. These are the defaults.</p>}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
