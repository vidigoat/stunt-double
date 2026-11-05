"use client";

import { useState } from "react";
import { BrandLogo, type LogoName } from "@/components/brand-logos";
import { Code } from "@/components/code";
import { DoublesShowcase } from "@/components/doubles-showcase";


export function Platform() {
  return (
    <section id="platform" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
      <div className="max-w-2xl">
        <div className="eyebrow">The platform</div>
        <h2 className="mt-3 font-display text-4xl sm:text-5xl">Everything your agent touches. <em>Rehearsed.</em></h2>
        <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">Data, money, email, any API, a real browser, and your Vultr servers. Each gets a double in the sandbox.</p>
      </div>
      <DoublesShowcase />
      <p className="mt-6 text-center text-[15px] text-muted-foreground">Plus the controls a bank would ask for: two-person approval, rehearsed undo, drift checks, and evidence for every decision.</p>
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
    <section id="mcp" className="grain relative scroll-mt-20 overflow-hidden bg-[#0B0B0C] py-24 text-white">
      <div aria-hidden className="pointer-events-none absolute -left-40 top-10 size-[520px] rounded-full bg-[#1463FF] opacity-25 blur-[120px]" />
      <div aria-hidden className="pointer-events-none absolute -right-40 bottom-0 size-[480px] rounded-full bg-[#2fd4c4] opacity-15 blur-[120px]" />
      <div className="relative z-[2] mx-auto max-w-5xl px-4 sm:px-6">
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
