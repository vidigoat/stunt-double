import { Check, Minus, Scissors, ShieldAlert, ShieldCheck, TriangleAlert, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Decision } from "@/lib/api";

const MARK = {
  pass: { icon: Check, cls: "bg-safe text-white" },
  warn: { icon: TriangleAlert, cls: "bg-signal text-white" },
  fail: { icon: X, cls: "bg-damage text-white" },
  skip: { icon: Minus, cls: "bg-muted text-muted-foreground" },
} as const;

const HEAD = {
  approve: { icon: ShieldCheck, tone: "text-safe", label: "Ready to approve" },
  review: { icon: TriangleAlert, tone: "text-signal", label: "A person decides" },
  blocked: { icon: ShieldAlert, tone: "text-damage", label: "Blocked" },
  cut: { icon: Scissors, tone: "text-safe", label: "Surgical approval" },
} as const;

/** The engine's decision: six independent layers, one plain reason each, combined by fixed rules. */
export function DecisionPanel({ decision, className }: { decision: Decision; className?: string }) {
  const h = HEAD[decision.decision] ?? HEAD.review;
  return (
    <div className={cn("overflow-hidden rounded-2xl border bg-card", className)}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b px-5 py-3.5">
        <h.icon className={cn("size-4 shrink-0", h.tone)} />
        <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Consequence engine · {h.label}</span>
        <span className={cn("min-w-0 basis-full text-[15px] font-medium sm:basis-auto sm:ml-auto", h.tone)}>{decision.headline}</span>
      </div>
      <ol className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-3">
        {decision.layers.map((l, i) => {
          const m = MARK[l.status] ?? MARK.skip;
          return (
            <li key={l.key} className="bg-card px-4 py-3">
              <div className="flex items-center gap-2">
                <span className={cn("flex size-4 shrink-0 items-center justify-center rounded-full", m.cls)}><m.icon className="size-2.5" strokeWidth={3} /></span>
                <span className="text-[13px] font-medium">{l.title}</span>
                <span className="ml-auto font-mono text-[10px] text-muted-foreground">{i + 1}/6</span>
              </div>
              <p className={cn("mt-1 line-clamp-3 text-[13px] leading-snug text-muted-foreground", l.status === "fail" && "text-damage/90")}>{l.reason}</p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
