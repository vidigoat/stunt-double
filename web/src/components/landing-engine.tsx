import Link from "next/link";
import { ArrowRight, Check, FileSignature, GitBranch, Network, Scissors, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { UnitStrip } from "@/components/surgical-card";

const GITHUB = "https://github.com/vidigoat/stunt-double";

// Real data from one rehearsal of the naive refund plan on the demo business: 744 units of work, these 104 kept.
const KEPT = [0, 11, 26, 32, 34, 40, 43, 58, 64, 66, 94, 104, 106, 108, 115, 118, 127, 134, 135, 159, 161, 169, 175, 183, 186, 188, 192, 203, 205,
  208, 213, 227, 231, 233, 271, 272, 273, 276, 280, 282, 288, 296, 298, 300, 302, 314, 315, 334, 336, 339, 345, 353, 356, 361, 362, 364, 383, 388,
  403, 409, 421, 422, 425, 432, 438, 441, 449, 459, 461, 462, 468, 485, 501, 514, 532, 535, 539, 552, 553, 558, 573, 574, 576, 594, 610, 616, 618,
  620, 623, 632, 650, 651, 654, 659, 678, 693, 695, 697, 702, 718, 719, 733, 738, 739];
const KEEP = new Set(KEPT);
const CUT = Array.from({ length: 744 }, (_, i) => i).filter((i) => !KEEP.has(i));

const LAYERS: [string, boolean][] = [["Measured", true], ["Proof of effect", true], ["Intent contract", false], ["Policy and rules", true], ["AI jury", false], ["Sign-off", true]];

function Stage({ n, icon: Icon, kicker, title, body, children, className }: {
  n: string; icon: typeof Check; kicker: string; title: React.ReactNode; body: string; children: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex flex-col overflow-hidden rounded-[22px] border bg-card/60", className)}>
      <div className="flex-1 border-b bg-background/40 p-5 sm:p-6">{children}</div>
      <div className="p-6">
        <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
          <span className="text-foreground/80">{n}</span><Icon className="size-3.5 text-signal" />{kicker}
        </div>
        <h3 className="mt-2 font-display text-[28px] leading-[1.1] sm:text-[32px]">{title}</h3>
        <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">{body}</p>
      </div>
    </div>
  );
}

function Pledge({ kind, state, text, count }: { kind: string; state: "todo" | "guard" | "broken"; text: string; count: string }) {
  return (
    <div className={cn("rounded-xl border p-3", state === "broken" ? "border-damage/40 bg-damage/[0.06]" : "bg-card")}>
      <div className="flex items-start gap-2.5">
        <span className={cn("mt-0.5 shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px]",
          state === "broken" ? "bg-damage/15 text-damage" : state === "todo" ? "bg-signal-soft text-signal" : "bg-safe/15 text-safe")}>
          {state === "broken" ? "broken" : state === "todo" ? "to do" : "guard"}
        </span>
        <span className="text-[14px] leading-snug">{text}</span>
      </div>
      <div className="mt-1.5 flex gap-3 pl-0.5 font-mono text-[11px] text-muted-foreground"><span className="uppercase tracking-wider">{kind}</span><span className={state === "broken" ? "text-damage" : ""}>{count}</span></div>
    </div>
  );
}

export function Engine() {
  return (
    <section id="engine" className="dark relative scroll-mt-16 overflow-hidden bg-background text-foreground">
      <div className="grid-paper pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_10%,transparent_65%)]" />
      <div className="relative mx-auto max-w-6xl px-4 py-24 sm:px-6 sm:py-28">
        <div className="max-w-3xl">
          <div className="eyebrow">The Consequence Engine</div>
          <h2 className="mt-3 font-display text-[44px] leading-[1.02] sm:text-[64px]">Not block or allow.<br /><em className="text-signal">Understand, correct, prove.</em></h2>
          <p className="mt-5 max-w-2xl text-lg leading-relaxed text-muted-foreground">
            Every guardrail asks one question: should this agent be stopped? The engine works out what the plan really did, why it did it, what you
            actually meant, and which part of it is right. Then it lets you approve exactly that part.
          </p>
        </div>

        <div className="mt-6 inline-flex flex-wrap items-center gap-x-3 gap-y-1 rounded-full border bg-card/60 px-4 py-2 font-mono text-[12px] text-muted-foreground">
          <span className="text-foreground">The request</span> “Refund everyone who was double-charged last week and send them an apology.”
        </div>

        <div className="mt-10 grid gap-4 lg:grid-cols-2">
          <Stage n="01" icon={FileSignature} kicker="Intent contract" title={<>Written <em>before</em> the plan exists.</>}
            body="From your request, your business glossary and your schema alone, a model on Vultr writes down what you meant: the work to be done, and what must not be touched. The plan never sees it, so it can't bend it. Code with no AI checks it afterwards. Try it on your own request: “What does this mean?” in the console.">
            <div className="space-y-2">
              <Pledge kind="the work" state="todo" count="104 to do today" text="Every extra charge from an order that was double-charged last week has been refunded." />
              <Pledge kind="guard" state="broken" count="the plan: 640 rows break it" text="Nothing else was refunded: never the first charge of an order, nor any other charge." />
              <p className="pl-1 font-mono text-[11px] text-muted-foreground">two of its four promises · cross-checked by a second model: 104 to do</p>
            </div>
          </Stage>

          <Stage n="02" icon={Network} kicker="Effect graph" title={<>744 refunds are <em>744 units of work.</em></>}
            body="Every measured consequence (a row, a refund, an email, an API call) is linked by foreign keys, charge ids and recipients into units that live or die together. A refund never leaves without its email.">
            <div className="flex h-full flex-col justify-center">
              <div className="grid grid-cols-3 gap-2 font-mono text-[12px]">
                {[["744", "charges changed"], ["744", "refunds"], ["744", "emails"]].map(([v, k]) => (
                  <div key={k} className="rounded-lg border bg-card px-3 py-2"><div className="text-lg text-foreground">{v}</div><div className="text-muted-foreground">{k}</div></div>
                ))}
              </div>
              <UnitStrip total={744} dropped={CUT} className="mt-4" />
              <div className="mt-1.5 flex justify-between font-mono text-[11px] text-muted-foreground">
                <span>one square per unit: charge + refund + email</span>
                <span><span className="text-safe">■</span> right 104 · <span className="text-damage">■</span> wrong 640</span>
              </div>
            </div>
          </Stage>

          <Stage n="03" icon={GitBranch} kicker="Proof of effect" title={<>Every change <em>has a reason.</em></>}
            body="The plan's own record of what it ran is only a claim. Trusted code replays it on the untouched copy, with a frozen clock, and must reproduce every measured change. A write through a hidden connection is a change no statement explains, and approval locks.">
            <div className="rounded-xl border border-damage/40 bg-card p-3">
              <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px]">
                <span className="text-muted-foreground">statement 1 · a read</span><span className="text-damage">chose all 640 wrong refunds</span>
              </div>
              <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-muted/60 px-3 py-2 font-mono text-[11.5px] leading-relaxed text-foreground/90">
{`SELECT c.id, c.customer_id, c.amount_cents FROM charges c
JOIN (SELECT customer_id, amount_cents, date(created_at) d
      FROM charges WHERE created_at >= '2026-10-26'
      GROUP BY customer_id, amount_cents, d
      HAVING COUNT(*) > 1) dup ON ...`}</pre>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] text-muted-foreground">
                <span><span className="text-safe">✓</span> 1,490 statements replayed</span><span><span className="text-safe">✓</span> 744 of 744 changes reproduced</span>
              </div>
            </div>
            <p className="mt-2 text-[12px] text-muted-foreground">Same customer, same amount, same day. Two separate orders, not a double charge.</p>
          </Stage>

          <Stage n="04" icon={Scissors} kicker="Surgical approval" title={<>Approve <em>the part that&apos;s right.</em></>}
            body="The engine cuts every unit that breaks the contract, rebuilds what is left without running the plan again, re-measures it in a fresh sandbox and re-checks it. Then you approve 104 refunds, and money moves for exactly the right people.">
            <div className="grid h-full grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border">
              <div className="bg-card p-4">
                <div className="font-mono text-[11px] uppercase tracking-wider text-safe">keep</div>
                <div className="mt-1 font-mono text-3xl">$5,136</div>
                <div className="text-sm text-muted-foreground">104 refunds · 104 emails</div>
              </div>
              <div className="bg-card p-4">
                <div className="font-mono text-[11px] uppercase tracking-wider text-damage">cut</div>
                <div className="mt-1 font-mono text-3xl text-damage">$32,268</div>
                <div className="text-sm text-muted-foreground">640 refunds · 640 emails</div>
              </div>
              <div className="col-span-2 flex items-center gap-2 bg-card px-4 py-3 text-sm">
                <span className="inline-flex h-8 items-center gap-1.5 rounded-full bg-safe px-3 font-medium text-black"><Scissors className="size-3.5" /> Keep just the 104 that are right</span>
                <span className="ml-auto hidden font-mono text-[11px] text-muted-foreground sm:inline">contract: 4 of 4 kept</span>
              </div>
            </div>
          </Stage>
        </div>

        <div className="mt-4 overflow-hidden rounded-[22px] border bg-card/60">
          <div className="grid gap-px bg-border md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <div className="bg-card/80 p-6">
              <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">05 · one decision, sealed</div>
              <h3 className="mt-2 font-display text-[28px] leading-[1.1]">Six layers. <em>One signed record.</em></h3>
              <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">
                Each layer gives one plain reason, and fixed rules combine them. Every step is then sealed into a hash chain signed with Ed25519:
                change one refund, one promise or one approver&apos;s name and the record no longer verifies.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-3">
              {LAYERS.map(([name, ok]) => (
                <div key={name} className="flex items-center gap-2.5 bg-card/80 px-4 py-4 text-sm">
                  <span className={cn("flex size-5 shrink-0 items-center justify-center rounded-full", ok ? "bg-safe text-black" : "bg-damage text-white")}>
                    {ok ? <Check className="size-3" strokeWidth={3} /> : <X className="size-3" strokeWidth={3} />}
                  </span>
                  {name}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
          <Link href="/app" className="inline-flex h-11 items-center gap-2 rounded-full bg-foreground px-5 text-[15px] font-medium text-background hover:opacity-90">See it on the live server <ArrowRight className="size-4" /></Link>
          <a href={`${GITHUB}/blob/main/docs/ENGINE.md`} target="_blank" rel="noreferrer" className="text-[15px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">How the engine works ↗</a>
          <a href={`${GITHUB}/blob/main/docs/BEYOND_THE_DEMO.md`} target="_blank" rel="noreferrer" className="text-[15px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">Not just this demo: a school and a SaaS company it never saw ↗</a>
        </div>
      </div>
    </section>
  );
}
