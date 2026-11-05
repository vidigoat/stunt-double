import Link from "next/link";
import { Check } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const WHO = [
  { role: "Ops & finance leads", line: "Approve refunds, credits and billing fixes by their impact in dollars and people, not by reading SQL." },
  { role: "Support leads", line: "Let agents act on tickets, while a poisoned ticket can only ever damage the double." },
  { role: "Sales & marketing ops", line: "See every email before a campaign goes out: who gets it, what it says, which VIPs are included." },
  { role: "AI platform teams", line: "Give agents write access with a safety net: isolation, policy, verification, drift-checked apply." },
];

const PLANS = [
  { name: "Free", price: "$0", per: "forever", points: ["100 rehearsals / month", "1 approver", "Sandboxed on Vultr"], cta: "Try the demo" },
  { name: "Team", price: "$49", per: "per approver / month", points: ["2,000 rehearsals included", "$0.02 per extra rehearsal", "Verifier + policy rules", "Audit log"], cta: "Start with Team", featured: true },
  { name: "Enterprise", price: "Custom", per: "annual", points: ["SSO and audit export", "Dedicated Vultr sandboxes", "Custom policy packs", "Managed DB forks"], cta: "Talk to us" },
];

export function Business() {
  return (
    <>
      <section id="who" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
        <div className="max-w-2xl">
          <div className="eyebrow">Who it&apos;s for</div>
          <h2 className="mt-3 font-display text-4xl sm:text-5xl">For the people who <em>sign off.</em></h2>
          <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">Gartner expects 15% of day-to-day work decisions to be made by AI agents by 2028. Someone still has to say yes. Stunt Double makes that yes informed.</p>
        </div>
        <div className="mt-10 grid gap-3 sm:grid-cols-2">
          {WHO.map((w) => (
            <div key={w.role} className="rounded-2xl border bg-card p-6">
              <div className="font-display text-2xl">{w.role}</div>
              <p className="mt-1.5 text-[15px] leading-relaxed text-muted-foreground">{w.line}</p>
            </div>
          ))}
        </div>
      </section>
      <section id="pricing" className="border-t bg-card">
        <div className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
          <div className="max-w-2xl">
            <div className="eyebrow">Pricing</div>
            <h2 className="mt-3 font-display text-4xl sm:text-5xl">Pay per rehearsal, <em>not per disaster.</em></h2>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {PLANS.map((p) => (
              <div key={p.name} className={cn("flex flex-col rounded-2xl border bg-background p-6", p.featured && "border-foreground")}>
                <div className="flex items-center justify-between">
                  <div className="font-display text-2xl">{p.name}</div>
                  {p.featured ? <span className="rounded-full bg-foreground px-2 py-0.5 text-[11px] text-background">Most teams</span> : null}
                </div>
                <div className="mt-4 flex items-baseline gap-2"><span className="font-mono text-4xl tabular">{p.price}</span><span className="text-sm text-muted-foreground">{p.per}</span></div>
                <ul className="mt-5 flex-1 space-y-2 text-[15px]">
                  {p.points.map((pt) => <li key={pt} className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0" />{pt}</li>)}
                </ul>
                <Link href="/app" className={cn(buttonVariants({ variant: p.featured ? "default" : "outline" }), "mt-6 h-11 rounded-full text-[15px]")}>{p.cta}</Link>
              </div>
            ))}
          </div>
          <p className="mt-6 text-sm text-muted-foreground">Hackathon prototype: pricing shows the intended model; all plans currently lead to the live demo.</p>
        </div>
      </section>
    </>
  );
}
