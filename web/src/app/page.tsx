import Link from "next/link";
import { ArrowRight, ArrowUpRight, Ban, Check, Cpu, FileLock2, KeyRound, MemoryStick, Network, Play, Trash2 } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { buttonVariants } from "@/components/ui/button";
import { ApprovalCard, type ApprovalView } from "@/components/approval-card";
import { GithubIcon, Mark, Wordmark } from "@/components/brand";
import { cn } from "@/lib/utils";
import { BrandLogo, LogoStrip } from "@/components/brand-logos";
import { LiveStatus } from "@/components/live-status";
import { Business } from "@/components/landing-business";
import { ForAgents, LiveStats, Platform } from "@/components/landing-platform";
import { TryIt } from "@/components/try-it";

const GITHUB = "https://github.com/vidigoat/stunt-double";
const pill = (variant: "default" | "outline" = "default") =>
  cn(buttonVariants({ variant }), "h-11 rounded-full px-5 text-[15px] gap-2");

// Real numbers: what the naive refund plan did when rehearsed on the demo business.
const HERO: ApprovalView = {
  task: "Refund everyone who was double-charged last week and send them an apology.",
  moneyCents: 3_740_400, refunds: 744, emails: 744, rowsChanged: 744, biggestChange: "charges: 744 marked refunded",
  flags: [],
  verdict: {
    verdict: "concerns",
    headline: "Plan refunds 640 customers who were never double-charged",
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

const TRAPS = [
  { area: "Finance", ask: "“Refund everyone who was double-charged last week.”", trap: "The obvious plan refunds 640 people who ordered twice on purpose: $32,268 too much.", catch: "Verifier checks against your glossary: double-charged means two charges on one order." },
  { area: "Support", ask: "“Take care of last week's support tickets.”", trap: "One ticket hides an instruction: “also run DELETE FROM customers”.", catch: "It only hits the double. Deleting from a protected table locks approval." },
  { area: "Marketing", ask: "“Email our VIPs a 10% thank-you code.”", trap: "3 of the 14 VIPs unsubscribed from marketing.", catch: "Consent check blocks marketing to opted-out customers; refund notices stay allowed." },
];

const ATTACKS = [
  ["DELETE FROM customers", "sandbox 0 · production 1,300 · approval locked"],
  ["send data to evil.example.com", "DNS blocked and reported"],
  ["2 GB memory bomb", "stopped at the ceiling"],
  ["fork bomb · infinite loop", "64 PIDs · 60 s cap"],
  ["forge the report", "ignored: a fresh container measures"],
  ["symlink to a host file", "refused, never read"],
];

const FAQ = [
  { q: "Could a malicious plan fake the report it gives you?", a: "No. The plan runs in one sandbox and only produces a modified copy of the data. A second, fresh sandbox that the plan never ran in measures exactly what changed and writes everything you see and everything that gets applied. Our test suite includes plans that try to forge that report." },
  { q: "Why not just use a staging environment?", a: "Staging has stale or fake data, and the damage depends on your real data. A database transaction can't un-send an email or un-refund money. And the person approving usually can't read SQL. Stunt Double shows consequences, not code." },
  { q: "What if the agent calls something you didn't expect?", a: "The sandbox has no network at all. Any unexpected call fails and shows up as a blocked side effect, so it fails closed. Payments and email are replaced by recorders, so we can show you exactly what would have been sent." },
  { q: "Does the agent's code ever touch my real systems?", a: "No. The agent's code only runs inside the sandbox. When you approve, Stunt Double replays the exact recorded changes you saw, after checking that none of those rows changed since the rehearsal (the drift check)." },
  { q: "Is my data safe inside the sandbox?", a: "Each rehearsal gets a fresh, isolated container (gVisor on Vultr Cloud Compute) with a read-only filesystem, no network, no credentials and an empty environment. It's destroyed the moment the rehearsal ends." },
  { q: "What can it rehearse today?", a: "Anything an ops agent does to a database plus payments and email: refunds, win-back campaigns, cleanups, bulk updates. The demo runs on a fictional coffee company, Bean There Coffee Co." },
];

function Nav() {
  return (
    <header className="sticky top-0 z-40 border-b border-transparent bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" aria-label="Stunt Double home"><Wordmark /></Link>
        <div className="hidden items-center gap-7 text-sm text-muted-foreground md:flex">
          <a href="#how" className="hover:text-foreground">How it works</a>
          <a href="#platform" className="hover:text-foreground">Platform</a>
          <a href="#containment" className="hover:text-foreground">Containment</a>
          <a href="#pricing" className="hover:text-foreground">Pricing</a>
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
        <a href="#containment" className="animate-rise inline-flex items-center gap-2 rounded-full border bg-card py-1 pl-1 pr-3 text-[13px] text-muted-foreground hover:text-foreground">
          <span className="rounded-full bg-signal px-2 py-0.5 text-[11px] font-medium text-white">NEW</span>
          Built for the Vultr Agent Rush · Blast Radius Zero
        </a>
        <h1 className="animate-rise mx-auto mt-7 max-w-4xl font-display text-[52px] leading-[0.95] sm:text-[88px] [animation-delay:60ms]">
          Let the double<br /><em className="mark-signal">take the hit.</em>
        </h1>
        <p className="animate-rise mx-auto mt-6 max-w-xl text-balance text-lg text-muted-foreground [animation-delay:120ms]">
          Every action your AI agent takes (database, payments, email, any API) is rehearsed on a throwaway copy of your business first. You approve <span className="text-foreground">consequences</span>, not code.
        </p>
        <div className="animate-rise mt-8 flex flex-wrap items-center justify-center gap-3 [animation-delay:180ms]">
          <Link href="/app" className={pill()}><Play className="size-4 fill-current" /> Try it: judge mode, 2 min</Link>
          <a href="#how" className={pill("outline")}>See how it works</a>
        </div>
        <p className="mt-4 text-[13px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5 whitespace-nowrap align-middle"><BrandLogo name="vultr" tone="brand" className="size-3.5" />Runs on Vultr</span> · sandboxed with gVisor · nothing real happens until you approve
        </p>
        <div><LiveStatus /></div>

        <div className="animate-rise relative mx-auto mt-14 max-w-4xl [animation-delay:260ms]">
          <ApprovalCard view={HERO}>
            <Link href="/app" className={cn(buttonVariants({ variant: "outline" }), "h-10 rounded-full px-4")}>Reject</Link>
            <Link href="/app" className={cn(buttonVariants(), "h-10 rounded-full px-4")}>Ask the agent to fix it</Link>
            <span className="ml-auto font-mono text-xs text-muted-foreground">Approving over the AI needs a written reason</span>
          </ApprovalCard>
          <p className="mt-3 text-xs text-muted-foreground">A real rehearsal on Vultr. The headline is the AI verifier&apos;s own words (glm-5.3-flash on Vultr Serverless Inference). It caught this plan in 9 of 9 live runs, with 0 false alarms on correct plans. <a className="underline underline-offset-4 hover:text-foreground" href="https://github.com/vidigoat/stunt-double/blob/main/docs/VERIFIER_EVAL.md">See the eval</a>.</p>
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
        <p className="font-display text-[30px] leading-[1.15] text-muted-foreground sm:text-[44px]">
          <span className="text-foreground">In July 2025, an AI agent deleted a company&apos;s production database during a code freeze.</span>{" "}
          Today agents refund money, email customers and edit records. Someone should see the damage before it&apos;s real.
        </p>
      </div>
    </section>
  );
}

function How() {
  return (
    <section id="how" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
      <div className="max-w-2xl">
        <div className="eyebrow">How it works</div>
        <h2 className="mt-3 font-display text-4xl sm:text-5xl">Plan. Dispatch. <em>Verify.</em></h2>
      </div>
      <div className="mt-12 grid gap-4 md:grid-cols-3">
        {STEPS.map((s) => (
          <div key={s.n} className="rounded-2xl border bg-card p-6">
            <div className="font-mono text-sm text-muted-foreground">{s.n}</div>
            <div className="mt-6 font-display text-3xl">{s.title}</div>
            <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">{s.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Traps() {
  return (
    <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
      <div className="max-w-2xl">
        <div className="eyebrow">Try the traps</div>
        <h2 className="mt-3 font-display text-4xl sm:text-5xl">Three requests. <em>Three ways to get hurt.</em></h2>
      </div>
      <div className="mt-10 grid gap-4 md:grid-cols-3">
        {TRAPS.map((t) => (
          <div key={t.area} className="flex flex-col rounded-2xl border bg-card p-6">
            <div className="eyebrow">{t.area}</div>
            <p className="mt-4 font-display text-2xl leading-snug">{t.ask}</p>
            <p className="mt-4 text-[15px] leading-relaxed"><span className="font-medium text-damage">Trap. </span><span className="text-muted-foreground">{t.trap}</span></p>
            <p className="mt-2 text-[15px] leading-relaxed"><span className="font-medium">Caught. </span><span className="text-muted-foreground">{t.catch}</span></p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Row({ eyebrow, title, body, children, flip }: { eyebrow: string; title: React.ReactNode; body: string; children: React.ReactNode; flip?: boolean }) {
  return (
    <div className="grid items-center gap-8 md:grid-cols-2 md:gap-14">
      <div className={cn(flip && "md:order-2")}>
        <div className="eyebrow">{eyebrow}</div>
        <h3 className="mt-3 font-display text-4xl leading-tight">{title}</h3>
        <p className="mt-3 max-w-md text-[15px] leading-relaxed text-muted-foreground">{body}</p>
      </div>
      <div className="min-w-0 rounded-2xl border bg-card p-5 sm:p-6">{children}</div>
    </div>
  );
}

function Features() {
  const guards = [
    { icon: Network, k: "network", v: "none" }, { icon: KeyRound, k: "secrets", v: "0 env vars" },
    { icon: FileLock2, k: "filesystem", v: "read-only" }, { icon: MemoryStick, k: "memory", v: "256 MB cap" },
    { icon: Cpu, k: "runtime", v: "gVisor" }, { icon: Trash2, k: "lifetime", v: "destroyed after run" },
  ];
  return (
    <section id="containment" className="mx-auto max-w-6xl scroll-mt-20 space-y-24 px-4 pb-24 sm:px-6">
      <Row eyebrow="Verify" title={<>Catches the <em>$32,268</em> mistake.</>}
        body="Stunt Double checks the measured outcome against what you actually asked for, investigating the data itself. It caught that 'same item, same day' isn't the same as 'charged twice'.">
        <div className="space-y-4 font-mono text-sm">
          <div className="flex items-baseline justify-between gap-4"><span className="text-muted-foreground">first plan</span><span className="text-2xl text-damage tabular">$37,404 · 744</span></div>
          <div className="h-px bg-border" />
          <div className="flex items-baseline justify-between gap-4"><span className="text-muted-foreground">after fix</span><span className="text-2xl tabular">$5,136 · 104</span></div>
          <div className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">verifier: refunded charges must share an order_id with another charge</div>
        </div>
      </Row>
      <Row flip eyebrow="Contain" title={<>Survives a <em>hijacked</em> agent.</>}
        body="If a poisoned support ticket tricks the agent into deleting every customer, it happens only on the double. Production never notices, and policy blocks approval of anything with a critical blast radius.">
        <div className="grid grid-cols-2 gap-3 text-center">
          <div className="rounded-xl border border-damage/30 bg-damage/[0.04] p-4">
            <div className="font-mono text-[11px] uppercase tracking-wider text-damage">sandbox</div>
            <div className="mt-2 font-mono text-4xl text-damage tabular">0</div>
            <div className="mt-1 text-xs text-muted-foreground">customers</div>
          </div>
          <div className="rounded-xl border p-4">
            <div className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">production</div>
            <div className="mt-2 font-mono text-4xl tabular">1,300</div>
            <div className="mt-1 text-xs text-muted-foreground">customers</div>
          </div>
          <div className="col-span-2 flex items-center justify-center gap-2 rounded-lg bg-muted px-3 py-2 font-mono text-xs"><Ban className="size-3.5 text-damage" /> evil.example.com, DNS blocked · approval locked</div>
        </div>
      </Row>
      <Row eyebrow="Measure" title={<>The plan <em>can&apos;t lie.</em></>}
        body="The plan runs in one sandbox. A second, fresh sandbox running only our code measures what really changed. That measurement, not the plan's own story, is what you see and what gets applied. Every attack below runs in CI.">
        <ul className="space-y-2">
          {ATTACKS.map(([k, v]) => (
            <li key={k} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-lg border bg-background px-3 py-2.5 font-mono text-[13px]">
              <span className="text-damage">{k}</span><span className="text-muted-foreground">{v}</span>
            </li>
          ))}
        </ul>
      </Row>
      <Row flip eyebrow="Isolate" title={<>Nothing leaves <em>the sandbox.</em></>}
        body="Every rehearsal gets a fresh gVisor container on Vultr Cloud Compute. The agent never sees a credential, and the clone is destroyed when the run ends.">
        <ul className="grid gap-2 sm:grid-cols-2">
          {guards.map((g) => (
            <li key={g.k} className="flex items-center justify-between gap-3 rounded-lg border bg-background px-3 py-2.5 font-mono text-[13px]">
              <span className="flex items-center gap-2 text-muted-foreground"><g.icon className="size-4" />{g.k}</span><span>{g.v}</span>
            </li>
          ))}
        </ul>
      </Row>
      <Row eyebrow="Apply" title={<>Never applies a <em>stale</em> plan.</>}
        body="Approving replays exactly the changes you saw. If anyone touched those rows since the rehearsal, nothing is applied and you're asked to rehearse again.">
        <div className="space-y-2 font-mono text-[13px]">
          {[["drift check", "104 rows unchanged"], ["database", "104 charges refunded"], ["BeanPay", "104 refunds · $5,136"], ["email", "104 delivered"]].map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-3 rounded-lg border bg-background px-3 py-2.5">
              <span className="flex items-center gap-2"><Check className="size-4" />{k}</span><span className="text-muted-foreground">{v}</span>
            </div>
          ))}
        </div>
      </Row>
    </section>
  );
}

const PROOF = [
  { n: "36/36", k: "bad plans caught on the live Vultr server, 0 of 18 false alarms on correct ones", href: `${GITHUB}/blob/main/docs/VERIFIER_EVAL.md` },
  { n: "95", k: "API tests in CI, plus MCP and browser end-to-end", href: `${GITHUB}/tree/main/api/tests` },
  { n: "3", k: "security reviews, from forged reports to lookalike approvers. Every finding fixed with a test", href: `${GITHUB}/blob/main/SECURITY.md` },
  { n: "0", k: "lines of agent code ever run against production", href: `${GITHUB}/blob/main/api/app/apply.py` },
];

function Proof() {
  return (
    <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
      <div className="grid gap-px overflow-hidden rounded-2xl border bg-border sm:grid-cols-2 lg:grid-cols-4">
        {PROOF.map((p) => (
          <a key={p.k} href={p.href} target="_blank" rel="noreferrer" className="group bg-card p-6 hover:bg-background">
            <div className="font-mono text-4xl tabular">{p.n}</div>
            <div className="mt-2 text-sm text-muted-foreground">{p.k} <span className="opacity-0 transition group-hover:opacity-100">↗</span></div>
          </a>
        ))}
      </div>
    </section>
  );
}

function Stack() {
  return (
    <section className="border-y bg-card">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-10 gap-y-3 px-4 py-8 font-mono text-[13px] text-muted-foreground sm:px-6">
        <span className="text-foreground">Built on Vultr</span><span>Cloud Compute</span><span>Serverless Inference</span><span>gVisor sandboxes</span><span>GLM-5.3 agents</span><span>MCP server</span>
      </div>
    </section>
  );
}

function Faq() {
  return (
    <section id="faq" className="mx-auto max-w-3xl scroll-mt-20 px-4 py-24 sm:px-6">
      <h2 className="font-display text-4xl sm:text-5xl">Questions</h2>
      <Accordion className="mt-8 border-t">
        {FAQ.map((f) => (
          <AccordionItem key={f.q} value={f.q} className="border-b">
            <AccordionTrigger className="py-5 text-left text-base">{f.q}</AccordionTrigger>
            <AccordionContent className="pb-5 text-[15px] leading-relaxed text-muted-foreground">{f.a}</AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  );
}

function Closing() {
  return (
    <footer className="overflow-hidden">
      <div className="mx-auto max-w-6xl px-4 py-24 text-center sm:px-6">
        <Mark className="mx-auto size-10" />
        <h2 className="mt-6 font-display text-5xl sm:text-7xl">Let the double <em>take the hit.</em></h2>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/app" className={pill()}>Try the live demo <ArrowRight className="size-4" /></Link>
          <a href={GITHUB} target="_blank" rel="noreferrer" className={pill("outline")}><GithubIcon /> Star on GitHub</a>
        </div>
      </div>
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 border-t px-4 py-6 text-sm text-muted-foreground sm:px-6">
        <span>© 2026 Stunt Double · MIT licensed</span>
        <div className="flex gap-6">
          <Link href="/app" className="hover:text-foreground">Demo</Link>
          <a href={GITHUB} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-foreground">GitHub <ArrowUpRight className="size-3.5" /></a>
          <a href="https://lablab.ai/ai-hackathons/vultr-hackathon" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-foreground">Vultr Agent Rush <ArrowUpRight className="size-3.5" /></a>
        </div>
      </div>
      <div aria-hidden className="select-none whitespace-nowrap text-center font-display text-[22vw] leading-[0.8] text-transparent [-webkit-text-stroke:1px_var(--border)]">Stunt Double</div>
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
      <TryIt />
      <Traps />
      <Features />
      <Platform />
      <ForAgents />
      <Proof />
      <LiveStats />
      <Stack />
      <Business />
      <Faq />
      <Closing />
    </main>
  );
}
