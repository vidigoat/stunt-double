import Link from "next/link";
import { ArrowRight, Play, Scissors } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { buttonVariants } from "@/components/ui/button";
import { ApprovalCard, type ApprovalView } from "@/components/approval-card";
import { GithubIcon, Mark, Wordmark } from "@/components/brand";
import { cn } from "@/lib/utils";
import { BrandLogo, LogoStrip } from "@/components/brand-logos";
import { Business } from "@/components/landing-business";
import { ForAgents, Platform } from "@/components/landing-platform";
import { TryIt } from "@/components/try-it";
import { Showcase } from "@/components/showcase";
import { Engine } from "@/components/landing-engine";

const GITHUB = "https://github.com/vidigoat/stunt-double";
const pill = (variant: "default" | "outline" = "default") =>
  cn(buttonVariants({ variant }), "h-11 rounded-full px-5 text-[15px] gap-2");

// Real numbers: what the naive refund plan did when rehearsed on the demo business.
const HERO: ApprovalView = {
  task: "Refund everyone who was double-charged last week and send them an apology.",
  moneyCents: 3_740_400, refunds: 744, emails: 744, rowsChanged: 744, biggestChange: "charges: 744 marked refunded",
  flags: [],
  verdict: {
    verdict: "dangerous",
    headline: "Plan refunds 640 customers who were never double-charged",
    jury: { agree: 3, cast: 3, votes: [
      { model: "glm-5.3-flash", lab: "Zhipu GLM", role: "verifier", verdict: "dangerous", headline: "Plan refunded 640 customers who were never double-charged" },
      { model: "deepseek-v4.1-flash-1017", lab: "DeepSeek", role: "juror", verdict: "dangerous", headline: "Refunds 744 charges but only 104 were real double charges" },
      { model: "minimax-m3.1-flash", lab: "MiniMax", role: "juror", verdict: "dangerous", headline: "640 of 744 refunds were for separate orders, not double charges" },
    ] },
    summary: "The plan refunds anyone who bought the same item twice on the same day. Most of them placed two separate orders on purpose. Only 104 customers were charged twice for one order.",
    concerns: [
      { severity: "high", title: "Over-refund of $32,268", detail: "640 legitimate repeat purchases would be refunded." },
      { severity: "medium", title: "8 VIP customers emailed by mistake", detail: "They'd get an apology for a problem they never had." },
    ],
  },
  sandboxId: "sd-d002755d", sandboxMs: 1910, runtime: "runsc",
  plain: "If approved, this refunds $37,404.00 across 744 charges, emails 744 people (8 VIPs) and changes 744 charges (refunded_at, status). Nothing else leaves the sandbox.",
};

const STEPS = [
  { n: "01", title: "Copy", body: "The data your agent needs is cloned into a sealed Vultr sandbox. No internet, no secrets, hard memory and time caps." },
  { n: "02", title: "Rehearse", body: "The agent's plan runs on the double. Payments and emails are recorded, never sent. Every changed row is measured." },
  { n: "03", title: "Approve", body: "You see what would happen, in plain English, checked against what you asked for. Only then does it run for real." },
];

const FAQ = [
  { q: "Could a malicious plan fake the report it gives you?", a: "No. The plan runs in one sandbox and only produces a modified copy of the data. A second, fresh sandbox that the plan never ran in measures exactly what changed and writes everything you see and everything that gets applied. Our test suite includes plans that try to forge that report." },
  { q: "What if the plan is only partly wrong?", a: "That's what the Consequence Engine is for. Before the plan exists, it writes down what your request means (\"104 extra charges need a refund, nothing else may be refunded\"), and a second model from another lab must read it the same way. After the rehearsal, it proves which statement of the plan caused each change, cuts every unit of work that breaks a promise (a refund always leaves with its email), re-measures what's left in a fresh sandbox and checks it again. You approve just the part that's right: on the demo, 104 of 744 refunds." },
  { q: "Does it only work on this coffee-shop demo?", a: "No. Nothing in the engine knows any schema. Live on the Vultr server, on an online school's database it had never seen, the contract found the 22 students who took their withdrawal back, and the cut kept exactly the right 41 of 63. On a SaaS company's Postgres it approved two correct plans and blocked the destructive one. And on 16 held-out cases, written down before the run and never tuned on, it stopped all 8 wrong plans. The write-ups, misses included, are on GitHub." },
  { q: "Why not just use a staging environment?", a: "Staging has stale or fake data, and the damage depends on your real data. A database transaction can't un-send an email or un-refund money. And the person approving usually can't read SQL. Stunt Double shows consequences, not code." },
  { q: "Is my data safe inside the sandbox?", a: "Each rehearsal gets a fresh, isolated container (gVisor on Vultr Cloud Compute) with a read-only filesystem, no network, no credentials and an empty environment. It's destroyed the moment the rehearsal ends. The agent's code never runs against your real systems: approval replays only the recorded changes." },
  { q: "What can it rehearse today?", a: "Database changes, refunds, emails, calls to any HTTP API, clicks in a real browser on a double of your admin site, and changes to your Vultr servers (delete, stop, resize) on a double of your fleet, including a read-only import of your real Vultr account. You can also rehearse on a read-only double of your own PostgreSQL database; approved changes download as drift-guarded SQL. Each one is measured, shown to you in plain English, and applied only after you approve." },
  { q: "How is the AI involved, and can I trust it?", a: "Three ways, all on Vultr Serverless Inference. Before any plan exists, one model (Qwen) writes down what your request means as checkable promises, and a second (DeepSeek) reads it again to cross-check. An agent writes plans. And an AI jury checks the measured outcome against what you asked for: three models from different labs (GLM, DeepSeek, MiniMax), each investigating the data on its own, and for browser runs the screenshots. The jury can make a verdict stricter, never more lenient. On the live server it caught 48 of 48 bad plans with 0 false alarms on 26 correct ones. Deterministic rules run first and can't be overruled by the AI; overruling the AI needs a written reason." },
  { q: "Can an agent approve its own plan?", a: "No. There is no approve tool in the MCP server and no approve method in the SDK. Big changes need two different people, approvals are bound to a fingerprint of the exact effects, and a rehearsal expires after 24 hours." },
  { q: "Does it get better over time?", a: "Yes. When the AI verifier catches a mistake, it also writes the SQL check it used. Stunt Double proves that check passes on today's data, and one click turns it into a rule that runs on every future rehearsal in milliseconds, without any AI. The same mistake is then blocked instantly, every time." },
  { q: "Can safe changes skip the human?", a: "Only if you turn it on. Graduated autonomy lets a change apply by itself when no rule fired, the AI verifier says it looks right, it needs a single approver, and it stays inside your money and row budget. Emails can be excluded. Everything else still waits for a person, and auto-applied runs are labelled in the audit trail." },
];

function Nav() {
  return (
    <header className="sticky top-0 z-40 border-b border-transparent bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" aria-label="Stunt Double home"><Wordmark /></Link>
        <div className="hidden items-center gap-7 text-sm text-muted-foreground md:flex">
          <a href="#how" className="hover:text-foreground">How it works</a>
          <a href="#engine" className="hover:text-foreground">The engine</a>
          <a href="#faq" className="hover:text-foreground">FAQ</a>
          <a href={GITHUB} target="_blank" rel="noreferrer" className="hover:text-foreground">GitHub</a>
        </div>
        <Link href="/app" className={cn(buttonVariants(), "h-9 rounded-full px-4 gap-1.5")}>Try it <ArrowRight className="size-4" /></Link>
      </nav>
    </header>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="grid-paper pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_20%,transparent_70%)]" />
      <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-16 text-center sm:px-6 sm:pt-24">
        <a href="#different" className="animate-rise inline-flex items-center gap-2 rounded-full border bg-card py-1 pl-1 pr-3 text-[13px] text-muted-foreground hover:text-foreground">
          <span className="rounded-full bg-signal px-2 py-0.5 text-[11px] font-medium text-white">NEW</span>
          Built for the Vultr Agent Rush · Blast Radius Zero
        </a>
        <h1 className="animate-rise mx-auto mt-7 max-w-4xl font-display text-[52px] leading-[0.95] sm:text-[88px] [animation-delay:60ms]">
          Let the double<br /><em className="mark-block">take the hit.</em>
        </h1>
        <p className="animate-rise mx-auto mt-6 max-w-xl text-balance text-lg text-muted-foreground [animation-delay:120ms]">
          Your AI agent tries every action on a throwaway copy of your business first. You see what would happen, in plain English, and approve the <span className="text-foreground">consequences</span>, not the code.
        </p>
        <div className="animate-rise mt-8 flex flex-wrap items-center justify-center gap-3 [animation-delay:180ms]">
          <Link href="/app" className={pill()}><Play className="size-4 fill-current" /> Try it: judge mode, 2 min</Link>
          <a href="#how" className={pill("outline")}>See how it works</a>
        </div>
        <p className="mt-4 text-[13px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5 whitespace-nowrap align-middle"><BrandLogo name="vultr" tone="brand" className="size-3.5" />Runs on Vultr</span> · sandboxed with gVisor · nothing real happens until you approve
        </p>

        <div className="animate-rise relative mx-auto mt-14 [animation-delay:260ms]">
          <div className="grain backdrop-blue rounded-[28px] px-3 py-8 sm:px-12 sm:py-14">
            <div className="relative z-[2] mx-auto max-w-4xl rounded-2xl text-left shadow-[0_40px_80px_-40px_rgba(20,30,80,.55),0_10px_30px_-15px_rgba(20,30,80,.3)]">
              <ApprovalCard view={HERO}>
                <Link href="/app" className={cn(buttonVariants({ variant: "outline" }), "h-10 rounded-full px-4")}>Reject</Link>
                <Link href="/app" className={cn(buttonVariants(), "h-10 rounded-full px-4")}>Ask the agent to fix it</Link>
                <span className="ml-auto font-mono text-xs text-muted-foreground">Approving over the AI needs a written reason</span>
              </ApprovalCard>
              <a href="#engine" className="group mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-2xl border border-safe/30 bg-card px-4 py-3 text-left text-sm shadow-[0_20px_40px_-30px_rgba(20,60,30,.6)] hover:border-safe/60">
                <span className="w-full min-w-0 sm:w-auto sm:flex-1"><Scissors className="mr-1.5 inline size-4 align-[-3px] text-safe" /><span className="font-medium"><span className="text-safe">104</span> of these 744 changes are right.</span> <span className="text-muted-foreground">The engine proves which line chose the other 640, cuts them, and lets you approve just the 104.</span></span>
                <span className="font-mono text-[12px]"><span className="text-safe">keep $5,136</span> · <span className="text-damage">cut $32,268</span></span>
                <span className="inline-flex items-center gap-1 font-medium text-safe">Keep just the 104 <ArrowRight className="size-3.5 transition group-hover:translate-x-0.5" /></span>
              </a>
            </div>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">A real rehearsal on Vultr, checked by an AI jury of three labs. <a className="underline underline-offset-4 hover:text-foreground" href="https://github.com/vidigoat/stunt-double/blob/main/docs/VERIFIER_EVAL.md">See the eval</a>. Then the engine keeps the right 104 and cuts the rest: <a className="text-signal underline-offset-4 hover:underline" href="#engine">see how</a>.</p>
        </div>
        <div className="mx-auto mt-16 max-w-4xl">
          <div className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Works with the agents and tools you already use</div>
          <LogoStrip className="mt-5" />
        </div>
      </div>
    </section>
  );
}

function Statement() {
  return (
    <section className="border-y bg-card">
      <div className="mx-auto max-w-5xl px-4 py-20 sm:px-6 sm:py-28">
        <p className="font-display text-[28px] leading-[1.18] text-muted-foreground sm:text-[38px]">
          <span className="text-foreground">In July 2025, an AI agent deleted a company&apos;s production database during a code freeze.</span>{" "}
          Today agents refund money, email customers and edit records. Someone should see the damage before it&apos;s real.
        </p>
      </div>
    </section>
  );
}

const STEP_VISUALS: Record<string, { tone: "blue" | "warm" | "green"; rows: [string, string][] ; foot: string }> = {
  "01": { tone: "blue", rows: [["business.db", "5,290 charges"], ["→ clone", "sealed copy"], ["network", "none"], ["secrets", "0"]], foot: "a fresh copy for every rehearsal" },
  "02": { tone: "warm", rows: [["sandbox", "gVisor · no network"], ["refunds", "recorded, not sent"], ["emails", "recorded, not sent"], ["rows changed", "measured: 104"]], foot: "destroyed after 1.8 s" },
  "03": { tone: "green", rows: [["money out", "$5,136"], ["people", "104"], ["AI jury", "3 of 3 agree"], ["you", "approve ✓"]], foot: "applied after a drift check" },
};

function How() {
  return (
    <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
      <div className="max-w-2xl">
        <div className="eyebrow">How it works</div>
        <h2 className="mt-3 font-display text-4xl sm:text-5xl">Three steps. <em>No surprises.</em></h2>
      </div>
      <div className="mt-12 grid gap-4 md:grid-cols-3">
        {STEPS.map((s) => {
          const v = STEP_VISUALS[s.n];
          return (
            <div key={s.n} className="card-hard flex flex-col overflow-hidden rounded-[22px] border bg-card">
              <div className={cn("grain px-6 pb-6 pt-7", `backdrop-${v.tone}`)}>
                <div className="relative z-[2] rounded-xl border border-black/10 bg-card/95 p-3 font-mono text-[12px] shadow-[0_18px_40px_-24px_rgba(20,30,60,.5)]">
                  {v.rows.map(([k, val]) => (
                    <div key={k} className="flex justify-between gap-3 border-b border-dashed py-1.5 last:border-0"><span className="text-muted-foreground">{k}</span><span>{val}</span></div>
                  ))}
                  <div className="mt-1.5 text-[11px] text-muted-foreground">{v.foot}</div>
                </div>
              </div>
              <div className="p-6">
                <div className="flex items-baseline gap-3"><span className="font-mono text-sm text-muted-foreground">{s.n}</span><span className="font-display text-3xl">{s.title}</span></div>
                <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">{s.body}</p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Panel({ shot, title, body, cta, className }: { shot: React.ReactNode; title: React.ReactNode; body: string; cta?: string; className?: string }) {
  return (
    <div className={cn("card-hard flex flex-col overflow-hidden rounded-[22px] border bg-card", className)}>
      {shot}
      <div className="p-6 sm:p-7">
        <h3 className="font-display text-[30px] leading-[1.1] sm:text-[34px]">{title}</h3>
        <p className="mt-2 max-w-xl text-[15px] leading-relaxed text-muted-foreground">{body}</p>
        {cta ? <Link href="/app" className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-signal hover:underline">{cta} <ArrowRight className="size-3.5" /></Link> : null}
      </div>
    </div>
  );
}

function Different() {
  return (
    <section id="different" className="scroll-mt-20 border-y bg-card/60">
      <div className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
        <div className="max-w-2xl">
          <div className="eyebrow">Why it&apos;s different</div>
          <h2 className="mt-3 font-display text-4xl sm:text-5xl">Not just a sandbox. <em>Three things no sandbox does.</em></h2>
          <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">Real screens from the live server.</p>
        </div>
        <div className="mt-12 grid gap-4 lg:grid-cols-5">
          <Panel className="lg:col-span-5"
            shot={<Showcase tone="warm" title="Try to fool it" src="/shots/lie.webp" width={2115} height={483} alt="The plan said it made no changes; a separate sandbox measured 300 changed rows" className="rounded-none" />}
            title={<>The plan <em>can&apos;t lie.</em></>}
            cta="Try it: judge step 3"
            body="A “read-only audit” secretly refunds 300 charges and forges its own report. It doesn't matter: a separate sandbox measures what really changed, and that is what you approve." />
          <Panel className="lg:col-span-3"
            shot={<Showcase tone="blue" title="AI jury · Vultr Serverless Inference" src="/shots/jury.webp" width={1364} height={590} alt="Three models from different labs each found that 640 of 744 refunds were wrong" className="rounded-none" />}
            title={<>A jury, <em>not a guess.</em></>}
            cta="Try it: judge step 1"
            body="Three models from three labs check the data on their own. They can make a verdict stricter, never softer." />
          <Panel className="lg:col-span-2"
            shot={<Showcase tone="green" title="Learned" src="/shots/learned.webp" width={1008} height={478} alt="The same plan blocked by a learned rule, no AI needed" className="rounded-none" />}
            title={<>Every catch <em>becomes a rule.</em></>}
            cta="Learn a rule: judge step 1"
            body="Every catch comes with the check that found it. One click makes it a rule, and the same mistake is blocked in seconds, with no AI." />
        </div>
      </div>
    </section>
  );
}

const PROOF = [
  { n: "1.8 s", k: "median two-phase rehearsal in a gVisor sandbox on Vultr", href: `${GITHUB}/blob/main/docs/BENCH.md` },
  { n: "201", k: "API tests in CI, plus MCP and browser end-to-end", href: `${GITHUB}/tree/main/api/tests` },
  { n: "3", k: "security reviews, from forged reports to lookalike approvers. Every finding fixed with a test", href: `${GITHUB}/blob/main/SECURITY.md` },
  { n: "0", k: "lines of agent code ever run against production", href: `${GITHUB}/blob/main/api/app/apply.py` },
];

function Proof() {
  return (
    <section className="mx-auto max-w-6xl px-4 pb-24 pt-20 sm:px-6">
      <div className="grid gap-px overflow-hidden rounded-2xl border bg-border sm:grid-cols-2 lg:grid-cols-4">
        {PROOF.map((p) => (
          <a key={p.k} href={p.href} target="_blank" rel="noreferrer" className="group bg-card p-6 hover:bg-background">
            <div className="font-mono text-4xl tabular">{p.n}</div>
            <div className="mt-2 text-sm text-muted-foreground">{p.k} <span className="opacity-0 transition group-hover:opacity-100">↗</span></div>
          </a>
        ))}
      </div>
      <p className="mt-5 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-center text-[13px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5 text-foreground"><BrandLogo name="vultr" tone="brand" className="size-3.5" />Built on Vultr</span>
        <span>Cloud Compute · Serverless Inference · gVisor sandboxes · MCP</span>
        <Link href="/control" className="text-signal hover:underline">Watch it live in Mission control →</Link>
      </p>
    </section>
  );
}

function Faq() {
  return (
    <section id="faq" className="mx-auto grid max-w-6xl scroll-mt-20 gap-10 px-4 py-24 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="lg:sticky lg:top-24 lg:self-start">
        <div className="eyebrow">FAQ</div>
        <h2 className="mt-3 font-display text-4xl leading-[1.05] sm:text-5xl">Frequently asked <em>questions</em></h2>
        <p className="mt-4 max-w-sm text-[15px] leading-relaxed text-muted-foreground">Anything else? The <a className="underline underline-offset-4 hover:text-foreground" href={`${GITHUB}#readme`} target="_blank" rel="noreferrer">README</a> and <a className="underline underline-offset-4 hover:text-foreground" href={`${GITHUB}/blob/main/SECURITY.md`} target="_blank" rel="noreferrer">SECURITY.md</a> go deeper.</p>
      </div>
      <Accordion className="border-t">
        {FAQ.map((f) => (
          <AccordionItem key={f.q} value={f.q} className="border-b">
            <AccordionTrigger className="py-6 text-left text-[17px] font-normal hover:no-underline">{f.q}</AccordionTrigger>
            <AccordionContent className="pb-6 pr-8 text-[15px] leading-relaxed text-muted-foreground">{f.a}</AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  );
}

const FOOTER: { title: string; links: [string, string][] }[] = [
  { title: "Product", links: [["Judge mode (live demo)", "/app"], ["Mission control", "/control"], ["Audit trail", "/history"], ["Policy", "/policy"], ["Outbox", "/ledger"], ["Connect an agent", "/connect"]] },
  { title: "How it works", links: [["Three steps", "#how"], ["Why it's different", "#different"], ["What it rehearses", "#platform"], ["Built for agents (MCP)", "#mcp"], ["Pricing", "#pricing"]] },
  { title: "Proof", links: [["Live eval: 48/48 caught", `${GITHUB}/blob/main/docs/VERIFIER_EVAL.md`], ["Agent eval", `${GITHUB}/blob/main/docs/EVAL.md`], ["Security reviews", `${GITHUB}/blob/main/SECURITY.md`], ["gVisor benchmark", `${GITHUB}/blob/main/docs/BENCH.md`]] },
  { title: "Project", links: [["GitHub", GITHUB], ["Python SDK", `${GITHUB}/tree/main/sdk/python`], ["Vultr: Agent Rush", "https://lablab.ai/ai-hackathons/vultr-hackathon"], ["MIT license", `${GITHUB}/blob/main/LICENSE`]] },
];

function Closing() {
  return (
    <footer className="overflow-hidden">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div className="grain backdrop-blue relative overflow-hidden rounded-[28px] px-6 py-20 text-center sm:py-28">
          <div className="relative z-[2]">
          <h2 className="mx-auto max-w-3xl font-display text-5xl leading-[1.02] sm:text-7xl">Let the double <em className="text-signal">take the hit.</em></h2>
          <p className="mx-auto mt-5 max-w-md text-[15px] leading-relaxed text-muted-foreground">Rehearse every agent action on Vultr first. Approve the consequences. Nothing real happens until you do.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/app" className={pill()}>Try the live demo <ArrowRight className="size-4" /></Link>
            <a href={GITHUB} target="_blank" rel="noreferrer" className={cn(pill("outline"), "bg-card/80")}><GithubIcon /> Star on GitHub</a>
          </div>
          </div>
        </div>
      </div>
      <div className="mx-auto grid max-w-6xl grid-cols-2 gap-x-6 gap-y-10 px-4 pb-16 sm:px-6 lg:grid-cols-4">
        {FOOTER.map((col) => (
          <div key={col.title}>
            <div className="text-sm text-muted-foreground">{col.title}</div>
            <ul className="mt-4 space-y-2.5">
              {col.links.map(([label, href]) => {
                const ext = href.startsWith("http");
                return (
                  <li key={label}>
                    <a href={href} {...(ext ? { target: "_blank", rel: "noreferrer" } : {})} className="text-[15px] text-foreground/90 underline-offset-4 hover:underline">{label}</a>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
      {/* The sign-off: the mark and the name, as big as the page allows. */}
      <div aria-hidden className="mx-auto flex max-w-[1400px] select-none items-center justify-center gap-[3vw] px-4 sm:px-6">
        <Mark className="size-[17vw] shrink-0" />
        <span className="whitespace-nowrap font-display text-[13.5vw] leading-none tracking-[-0.03em]">Stunt <em>Double</em></span>
      </div>
      <div className="mx-auto mt-10 flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 pb-10 text-sm text-muted-foreground sm:px-6">
        <span>© 2026 Stunt Double · Team Dragon · MIT licensed</span>
        <div className="flex items-center gap-5">
          <a href={GITHUB} target="_blank" rel="noreferrer" aria-label="GitHub" className="hover:text-foreground"><BrandLogo name="github" className="size-5" /></a>
          <a href="https://www.vultr.com" target="_blank" rel="noreferrer" aria-label="Runs on Vultr" className="hover:text-foreground"><BrandLogo name="vultr" className="size-5" /></a>
          <Link href="/connect" aria-label="MCP" className="hover:text-foreground"><BrandLogo name="mcp" className="size-5" /></Link>
          <a href={`${GITHUB}/tree/main/sdk/python`} target="_blank" rel="noreferrer" aria-label="Python SDK" className="hover:text-foreground"><BrandLogo name="python" className="size-5" /></a>
        </div>
      </div>
    </footer>
  );
}

export default function Home() {
  return (
    <main>
      <Nav />
      <Hero />
      <Statement />
      <How />
      <Engine />
      <TryIt />
      <Different />
      <Platform />
      <ForAgents />
      <Proof />
      <Business />
      <Faq />
      <Closing />
    </main>
  );
}
