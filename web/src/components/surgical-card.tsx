"use client";

import { useMemo } from "react";
import { Scissors } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { num, usd, type SurgicalOffer } from "@/lib/api";

/** The plan, drawn as its units of work: one thin bar each, the ones the engine would cut in red. */
export function UnitStrip({ total, dropped, className }: { total: number; dropped: number[]; className?: string }) {
  const cut = useMemo(() => new Set(dropped), [dropped]);
  const n = Math.min(total, 1200);
  const scale = total / n;
  return (
    <div className={cn("flex h-10 w-full items-stretch gap-px overflow-hidden rounded-md", className)} role="img"
      aria-label={`${total} units of work, ${dropped.length} cut`}>
      {Array.from({ length: n }, (_, i) => {
        const lo = Math.floor(i * scale), hi = Math.max(lo + 1, Math.floor((i + 1) * scale));
        let bad = false;
        for (let k = lo; k < hi && !bad; k++) bad = cut.has(k);
        return <span key={i} className={cn("min-w-px flex-1", bad ? "bg-damage/80" : "bg-safe")} />;
      })}
    </div>
  );
}

/** "104 of these 744 changes are right. Approve just those?" */
export function SurgicalCard({ offer, check, busy, onCut }: { offer: SurgicalOffer; check?: { title: string; source: string }; busy: boolean; onCut: () => void }) {
  return (
    <div className="animate-rise card-hard overflow-hidden rounded-2xl border bg-card">
      <div className="grain backdrop-green p-5 sm:p-6 [&>*]:relative [&>*]:z-[2]">
        <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.14em] text-foreground/70">
          <Scissors className="size-3.5" /> Consequence engine · surgical approval
        </div>
        <h3 className="mt-2 font-display text-[28px] leading-tight sm:text-[32px]">
          <span className="text-safe">{num(offer.units_kept)}</span> of these {num(offer.units_total)} changes are right.
        </h3>
        <p className="mt-1.5 max-w-2xl text-[15px] leading-relaxed text-foreground/75">
          The engine traced every row {check?.source === "learned rule" ? "the learned rule" : "the AI jury"} flagged back through the plan&apos;s effect graph,
          and cut each wrong refund out together with its email. What&apos;s left passes the check.
          {offer.caused_by?.length === 1 ? <> Every cut row was {offer.caused_by[0].how === "chose" ? "chosen" : "written"} by <b className="font-semibold">statement {offer.caused_by[0].i}</b> of the plan (shown below, proven by replay).</>
            : offer.caused_by?.length ? <> The cut rows came from statements <b className="font-semibold">{offer.caused_by.map((c) => c.i).join(", ")}</b> of the plan (shown below, proven by replay).</> : null}
        </p>
        <UnitStrip total={offer.units_total} dropped={offer.dropped_units} className="mt-4 shadow-[0_10px_30px_-18px_rgba(20,60,30,.6)]" />
        <div className="mt-1.5 flex justify-between font-mono text-[11px] text-foreground/60">
          <span>each bar is one unit of work: a charge, its refund and its email</span>
          <span><span className="text-safe">■</span> keep {num(offer.units_kept)} · <span className="text-damage">■</span> cut {num(offer.units_dropped)}</span>
        </div>
      </div>
      <div className="grid gap-px border-t bg-border sm:grid-cols-2">
        <div className="bg-card p-4">
          <div className="text-[11px] font-medium uppercase tracking-wider text-safe">Keep</div>
          <div className="mt-1 font-mono text-xl tabular">{usd(offer.kept.money_cents)}</div>
          <div className="text-sm text-muted-foreground">{num(offer.kept.refunds)} refunds · {num(offer.kept.emails)} emails · {num(offer.kept.rows)} rows</div>
        </div>
        <div className="bg-card p-4">
          <div className="text-[11px] font-medium uppercase tracking-wider text-damage">Cut</div>
          <div className="mt-1 font-mono text-xl tabular text-damage">{usd(offer.dropped.money_cents)}</div>
          <div className="text-sm text-muted-foreground">{num(offer.dropped.refunds)} refunds · {num(offer.dropped.emails)} emails · {num(offer.dropped.rows)} rows</div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t bg-card p-4">
        <Button className="h-10 rounded-full bg-safe px-5 text-white hover:bg-safe/90" disabled={busy} onClick={onCut}>
          <Scissors className="size-4" /> Keep just the {num(offer.units_kept)} that are right
        </Button>
        <span className="text-sm text-muted-foreground">The {num(offer.units_kept)} are re-rehearsed in a fresh sandbox and checked again. You still approve.</span>
      </div>
    </div>
  );
}
