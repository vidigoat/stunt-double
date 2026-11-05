"use client";

import { useEffect, useState } from "react";
import { FileCheck2, KeyRound, Scale, Sparkles, Undo2, Users } from "lucide-react";
import { CountUp } from "@/components/count-up";
import { BrandLogo, type LogoName } from "@/components/brand-logos";
import { Code } from "@/components/code";
import { DoublesShowcase } from "@/components/doubles-showcase";


const CONTROLS = [
  { icon: Scale, name: "Policy simulator", line: "Change a rule and see which recent rehearsals it would have blocked or sent to two approvers, before you save it." },
  { icon: FileCheck2, name: "Every row, inspectable", line: "Search and page through every changed row of the recorded effects. Not a sample: exactly what approval replays." },
  { icon: Users, name: "Two-person rule", line: "Big payouts, large changes and every undo need two different people. One click can't move $37,404." },
  { icon: Undo2, name: "Rehearsed undo", line: "Regret an approval? Roll the data back. The undo is rehearsed, drift-checked and approved like any change." },
  { icon: FileCheck2, name: "Evidence, not vibes", line: "Each approval is bound to a SHA-256 of the plan and its effects, with who decided and why. Download any run's evidence, or the whole trail as CSV." },
  { icon: KeyRound, name: "Approvals that can't go stale", line: "Rules are re-checked at the moment of approval, rehearsals expire after 24 hours, and every row is drift-checked before it's written." },
  { icon: Sparkles, name: "Learns from every catch", line: "When the AI catches a mistake it writes the check it used. One click makes it a rule that runs on every rehearsal, without AI." },
  { icon: Scale, name: "Policy + glossary", line: "Blocking rules you control, plus your company's definitions, so the verifier judges plans the way you would." },
];

export function Platform() {
  return (
    <section id="platform" className="mx-auto max-w-6xl scroll-mt-20 px-4 pb-24 sm:px-6">
      <div className="max-w-2xl">
        <div className="eyebrow">The platform</div>
        <h2 className="mt-3 font-display text-4xl sm:text-5xl">Everything your agent touches. <em>Rehearsed.</em></h2>
        <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">Data, money, email, any API, a real browser, and your cloud. Each gets a double inside the Vultr sandbox; humans approve what would happen.</p>
      </div>
      <DoublesShowcase />
      <div className="mt-4 flex items-start gap-3 rounded-2xl border bg-foreground p-6 text-background">
        <KeyRound className="mt-0.5 size-5 shrink-0" />
        <p className="text-[15px] leading-relaxed"><span className="font-medium">The sandbox never sees a secret.</span> <span className="opacity-75">Plans describe API calls; real credentials are injected on the server only after a human approves, and only for configured connectors. A call to anywhere else locks approval.</span></p>
      </div>

      <div className="mt-24 max-w-2xl">
        <div className="eyebrow">Controls</div>
        <h2 className="mt-3 font-display text-4xl sm:text-5xl">Controls a bank <em>would sign off on.</em></h2>
      </div>
      <div className="mt-10 grid gap-3 sm:grid-cols-2">
        {CONTROLS.map((c) => (
          <div key={c.name} className="card-lift flex gap-4 rounded-2xl border bg-card p-6">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-signal-soft text-signal"><c.icon className="size-[18px]" /></span>
            <div><div className="font-display text-2xl">{c.name}</div><p className="mt-1 text-[15px] leading-relaxed text-muted-foreground">{c.line}</p></div>
          </div>
        ))}
      </div>
    </section>
  );
}

const AGENT_TABS: { key: string; label: string; logo?: LogoName; install: string; code: string }[] = [
  { key: "claude", label: "Claude Code", logo: "claude", install: "$ claude mcp add --transport http stunt-double https://<host>/mcp",
    code: `> Refund everyone who was double-charged last week.

● stunt-double · rehearse(task, plan_code)
  { "refunds": 104, "money_out_usd": 5136.0,
    "blocked_by_policy": [],
    "verdict": "looks_right",
    "approval_url": "https://<host>/app?run=…" }

● Rehearsed on the double. A human approves at the link;
  I can't approve my own plan.` },
  { key: "cursor", label: "Cursor", logo: "cursor", install: "// .cursor/mcp.json",
    code: `{
  "mcpServers": {
    "stunt-double": { "url": "https://<host>/mcp" }
  }
}` },
  { key: "python", label: "Python SDK", logo: "python", install: "$ pip install ./sdk/python",
    code: `from stunt_double import StuntDouble
sd = StuntDouble("https://<host>")

@sd.plan("Clean up our unused Vultr servers")
def run(ctx):
    for s in ctx.vultr.list_instances():
        if s["cpu_avg_7d"] < 2 and "production" not in s["tags"]:
            ctx.vultr.delete_instance(s["id"])

r = run.rehearse()             # on the double, in a gVisor sandbox
print(r.summary, r.approval_url)
sd.wait_for_decision(r.run_id) # a human approves. Never the agent.` },
  { key: "cli", label: "CLI", install: "$ sd rehearse cleanup.py --task \"Clean up idle servers\"",
    code: `rehearsed in sd-9f3c2a1b · gVisor · 1.8 s · destroyed
  deletes 4 Vultr servers  (−$70.00/month)
  production touched: none
  verdict: looks_right
  approve: https://<host>/app?run=run_7c1e…

exit 0 · ready for a human` },
  { key: "rest", label: "REST", logo: "fastapi", install: "POST /api/runs/manual",
    code: `curl -s https://<host>/api/runs/manual \\
  -H 'content-type: application/json' \\
  -d '{"task": "Cancel the duplicate subscription",
       "code": "def run(ctx):\\n    ctx.browser.open(\\"/subscriptions\\")\\n    ..."}'

# then GET /api/runs/<id>  ·  OpenAPI at /api/docs` },
];

export function ForAgents() {
  const [tab, setTab] = useState(AGENT_TABS[0].key);
  const t = AGENT_TABS.find((x) => x.key === tab) ?? AGENT_TABS[0];
  return (
    <section id="mcp" className="scroll-mt-20 bg-[#0B0B0C] py-24 text-white">
      <div className="mx-auto max-w-5xl px-4 sm:px-6">
        <div className="text-center">
          <div className="eyebrow justify-center">Built for agents</div>
          <h2 className="mt-3 font-display text-4xl sm:text-6xl">Works with <em className="text-[#7ea6ff]">any agent</em></h2>
          <p className="mx-auto mt-4 max-w-xl text-[15px] leading-relaxed text-white/60">One call before it acts: MCP, three lines of Python, a CLI or plain REST. There is no approve tool and no approve method. An agent can never approve its own plan.</p>
        </div>
        <div className="mt-10 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]">
          <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-white/10 p-1.5">
            {AGENT_TABS.map((x) => (
              <button key={x.key} role="tab" aria-selected={tab === x.key} onClick={() => setTab(x.key)}
                className={"inline-flex shrink-0 items-center gap-2 rounded-lg px-3.5 py-2 text-sm transition " + (tab === x.key ? "bg-white/10 text-white" : "text-white/55 hover:text-white")}>
                {x.logo ? <BrandLogo name={x.logo} tone="brand" className="size-4" /> : <span className="font-mono text-xs">&gt;_</span>}{x.label}
              </button>
            ))}
          </div>
          <div className="border-b border-white/10 px-5 py-3 font-mono text-[13px] text-white/70">{t.install}</div>
          <Code code={t.code} className="min-h-[280px] rounded-none bg-transparent px-5 py-5 text-white/90" />
        </div>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <a href="/connect" className="inline-flex h-11 items-center gap-2 rounded-full bg-signal px-5 text-sm font-medium text-white transition hover:opacity-90">Connect your agent →</a>
          <a href="/app" className="inline-flex h-11 items-center gap-2 rounded-full border border-white/20 px-5 text-sm text-white/90 transition hover:border-white/50">See it work</a>
        </div>
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
        <div className="flex flex-wrap items-center justify-between gap-2"><div className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Live on this server · since the last demo reset</div><a href="/control" className="text-sm text-signal hover:underline">Watch it live in Mission control →</a></div>
        <div className="mt-4 grid grid-cols-2 gap-6 lg:grid-cols-4">
          {([["rehearsals", s.rehearsals, "num"], ["stopped before damage", s.stopped, "num"], ["money kept", s.money_prevented_cents, "usd"], ["rows protected", s.rows_protected, "num"]] as const).map(([k, v, f]) => (
            <div key={k}><div className="font-mono text-3xl tabular"><CountUp value={v} format={f} /></div><div className="mt-1 text-sm text-muted-foreground">{k}</div></div>
          ))}
        </div>
      </div>
    </section>
  );
}
