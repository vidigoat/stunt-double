"use client";

import { useEffect, useState } from "react";
import { Database, FileCheck2, KeyRound, Mail, Scale, Undo2, Users, Webhook, CreditCard } from "lucide-react";
import { num, usd } from "@/lib/api";

const CONNECTORS = [
  { icon: Database, name: "Your database", line: "Every changed row is measured on a clone and replayed only if nobody touched it since. Upload your own SQLite to try it on your schema." },
  { icon: CreditCard, name: "Payments", line: "Refunds are recorded, checked against the real charge and the ledger, and paid once per charge. Never twice." },
  { icon: Mail, name: "Email", line: "One real customer per message, no broken templates, no leaked data, and unsubscribes are respected." },
  { icon: Webhook, name: "Any HTTP API", line: "Slack, your CRM, anything. Calls are recorded in the sandbox and delivered through a connector after approval." },
];

const CONTROLS = [
  { icon: Scale, name: "Policy simulator", line: "Change a rule and see which recent rehearsals it would have blocked or sent to two approvers, before you save it." },
  { icon: FileCheck2, name: "Every row, inspectable", line: "Search and page through every changed row of the recorded effects. Not a sample: exactly what approval replays." },
  { icon: Users, name: "Two-person rule", line: "Big payouts, large changes and every undo need two different people. One click can't move $37,404." },
  { icon: Undo2, name: "Rehearsed undo", line: "Regret an approval? Roll the data back. The undo is rehearsed, drift-checked and approved like any change." },
  { icon: FileCheck2, name: "Evidence, not vibes", line: "Each approval is bound to a SHA-256 of the plan and its effects. Download the evidence bundle for any run." },
  { icon: Scale, name: "Policy + glossary", line: "Blocking rules you control, plus your company's definitions, so the verifier judges plans the way you would." },
];

export function Platform() {
  return (
    <section id="platform" className="mx-auto max-w-6xl scroll-mt-20 px-4 pb-24 sm:px-6">
      <div className="max-w-2xl">
        <div className="font-mono text-xs uppercase tracking-wider text-muted-foreground">The platform</div>
        <h2 className="mt-3 font-display text-4xl sm:text-5xl">Everything your agent touches. <em>Rehearsed.</em></h2>
      </div>
      <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {CONNECTORS.map((c) => (
          <div key={c.name} className="rounded-2xl border bg-card p-6">
            <c.icon className="size-5" />
            <div className="mt-5 font-display text-2xl">{c.name}</div>
            <p className="mt-1.5 text-[15px] leading-relaxed text-muted-foreground">{c.line}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-start gap-3 rounded-2xl border bg-foreground p-6 text-background">
        <KeyRound className="mt-0.5 size-5 shrink-0" />
        <p className="text-[15px] leading-relaxed"><span className="font-medium">The sandbox never sees a secret.</span> <span className="opacity-75">Plans describe API calls; real credentials are injected on the server only after a human approves, and only for configured connectors. A call to anywhere else locks approval.</span></p>
      </div>

      <div className="mt-24 max-w-2xl">
        <div className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Controls</div>
        <h2 className="mt-3 font-display text-4xl sm:text-5xl">Controls a bank <em>would sign off on.</em></h2>
      </div>
      <div className="mt-10 grid gap-3 sm:grid-cols-2">
        {CONTROLS.map((c) => (
          <div key={c.name} className="flex gap-4 rounded-2xl border bg-card p-6">
            <c.icon className="mt-1 size-5 shrink-0" />
            <div><div className="font-display text-2xl">{c.name}</div><p className="mt-1 text-[15px] leading-relaxed text-muted-foreground">{c.line}</p></div>
          </div>
        ))}
      </div>
    </section>
  );
}

const MCP = `$ claude mcp add --transport http \\
    stunt-double https://<host>/mcp

> rehearse(task, plan_code)
{ "refunds": 104, "money_out_usd": 5136.0,
  "blocked_by_policy": [],
  "approval_url": "https://<host>/app?run=…" }`;

const SDK = `from stunt_double import StuntDouble
sd = StuntDouble("https://<host>")

@sd.plan("Refund everyone who was double-charged")
def run(ctx):
    ...                         # ctx.db · ctx.payments · ctx.email · ctx.http

r = run.rehearse()              # on the double, in a sandbox
print(r.summary, r.approval_url)
sd.wait_for_decision(r.run_id)  # a human approves. Never the agent.`;

export function ForAgents() {
  return (
    <section id="mcp" className="mx-auto max-w-6xl scroll-mt-20 px-4 pb-24 sm:px-6">
      <div className="max-w-2xl">
        <div className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Built for agents</div>
        <h2 className="mt-3 font-display text-4xl sm:text-5xl">One call <em>before it acts.</em></h2>
        <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">Claude Code, Cursor or your own agent rehearses through MCP or three lines of Python. There is no approve tool and no approve method: an agent can never approve its own plan.</p>
      </div>
      <div className="mt-10 grid gap-4 lg:grid-cols-2">
        {[["MCP · any agent", MCP], ["Python SDK", SDK]].map(([t, code]) => (
          <div key={t} className="min-w-0 rounded-2xl border bg-card p-4">
            <div className="px-1 pb-3 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">{t}</div>
            <pre className="overflow-x-auto rounded-xl bg-foreground p-5 font-mono text-[13px] leading-relaxed text-background">{code}</pre>
          </div>
        ))}
      </div>
    </section>
  );
}

type Stats = { rehearsals: number; stopped: number; money_prevented_cents: number; rows_protected: number; applied: number };

export function LiveStats() {
  const [s, setS] = useState<Stats | null>(null);
  useEffect(() => { fetch("/api/stats", { cache: "no-store" }).then((r) => r.json()).then(setS).catch(() => setS(null)); }, []);
  if (!s || !s.rehearsals) return null;
  return (
    <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
      <div className="rounded-2xl border bg-card p-6">
        <div className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Live on this server · since the last demo reset</div>
        <div className="mt-4 grid grid-cols-2 gap-6 lg:grid-cols-4">
          {[["rehearsals", num(s.rehearsals)], ["stopped before damage", num(s.stopped)], ["money kept", usd(s.money_prevented_cents)], ["rows protected", num(s.rows_protected)]].map(([k, v]) => (
            <div key={k}><div className="font-mono text-3xl tabular">{v}</div><div className="mt-1 text-sm text-muted-foreground">{k}</div></div>
          ))}
        </div>
      </div>
    </section>
  );
}
