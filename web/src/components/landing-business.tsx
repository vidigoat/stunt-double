import Link from "next/link";
import { Check } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PLANS = [
  { name: "Free", price: "$0", per: "forever", points: ["Self-host on your Vultr account (MIT, one command)", "200 rehearsals / month here", "20 AI jury checks / month"], cta: "Try the demo" },
  { name: "Team", price: "$49", per: "per approver / month", points: ["2,000 rehearsals + 300 AI jury checks", "Then $0.005 / rehearsal, $0.10 / jury check", "Re-checks and learned rules are free", "Audit trail + evidence export"], cta: "Start with Team", featured: true },
  { name: "Enterprise", price: "Custom", per: "annual", points: ["SSO and audit export", "A dedicated Vultr VM per rehearsal", "Custom policy packs", "Your Postgres and Vultr fleet"], cta: "Talk to us" },
];

export function Business() {
  return (
    <>
      <section id="pricing" className="border-t bg-card">
        <div className="mx-auto max-w-6xl scroll-mt-20 px-4 py-24 sm:px-6">
          <div className="max-w-2xl">
            <div className="eyebrow">Pricing</div>
            <h2 className="mt-3 font-display text-4xl sm:text-5xl">Pay per rehearsal, <em>not per disaster.</em></h2>
            <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">For the ops, finance, support and platform teams who sign off on what agents do. <span className="text-foreground">One caught mistake from the demo ($32,268) pays for a Team seat for almost 55 years.</span> And every approval is the human-oversight and change-management record the EU AI Act (Art. 14) and SOC 2 (CC8.1) ask for.</p>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {PLANS.map((p) => (
              <div key={p.name} className={cn("flex flex-col rounded-2xl border bg-background p-6", p.featured && "card-hard")}>
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
          <div className="mt-6 grid gap-px overflow-hidden rounded-2xl border bg-border sm:grid-cols-3">
            {[["≈ $0.00003", "our cost per rehearsal", "1.8 s on a $20/month Vultr VM"], ["$0.02–0.044", "our cost per AI jury check", "measured tokens × Vultr prices"], ["73%", "gross margin, Team at full use", "re-checks and learned rules cost $0"]].map(([n, k, d]) => (
              <div key={k} className="bg-background p-5"><div className="font-mono text-2xl tabular">{n}</div><div className="mt-1 text-sm">{k}</div><div className="text-xs text-muted-foreground">{d}</div></div>
            ))}
          </div>
          <p className="mt-4 text-sm text-muted-foreground">Measured on the live Vultr deployment. <a className="underline underline-offset-4 hover:text-foreground" href="https://github.com/vidigoat/stunt-double/blob/main/docs/BUSINESS.md" target="_blank" rel="noreferrer">The business case →</a> · Hackathon prototype: all plans currently lead to the live demo.</p>
        </div>
      </section>
    </>
  );
}
