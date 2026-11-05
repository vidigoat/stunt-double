"use client";

import { cn } from "@/lib/utils";
import { num, type Run } from "@/lib/api";

const go = (id: string) => {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
  el.classList.add("ring-4", "ring-signal/30", "rounded-2xl");
  setTimeout(() => el.classList.remove("ring-4", "ring-signal/30"), 1600);
};

/** The engine's story for this run in five steps, each one a jump to the card that proves it. */
export function EngineGuide({ run }: { run: Run }) {
  const first = run.attempts[0];
  const last = run.attempts.at(-1);
  const offer = run.surgical?.offer;
  const work = Math.max(0, ...((run.contract?.promises ?? []).filter((p) => p.kind === "obligation").map((p) => p.today)));
  const did = first ? (first.consequences.payments?.count || Object.values(first.consequences.tables ?? {}).reduce((n, t) => n + t.updated + t.deleted + t.inserted, 0)) : 0;
  const cutDone = !!last?.surgical_of;
  const by = offer?.caused_by?.[0];
  const steps = [
    { id: "eng-contract", label: work ? `Contract: ${num(work)} to do` : "The contract", done: run.contract?.status === "ready" },
    { id: "eng-plan", label: `Plan did ${num(did)}`, done: !!first },
    { id: "eng-proof", label: by ? `Statement ${by.i} chose them` : "Every change proven", done: !!first?.consequences.provenance },
    { id: "eng-cut", label: offer ? `Keep ${num(offer.units_kept)} of ${num(offer.units_total)}` : "The cut", done: cutDone },
    { id: "eng-decision", label: cutDone && run.decision?.decision === "approve" ? "All layers pass" : "The decision", done: cutDone && !!run.decision },
  ];
  return (
    <nav aria-label="The engine, step by step" className="flex gap-1 overflow-x-auto rounded-2xl border bg-card p-1.5 sm:grid sm:grid-cols-5">
      {steps.map((s, i) => (
        <button key={s.id} onClick={() => go(cutDone && s.id === "eng-cut" ? "eng-decision" : s.id)}
          className={cn("flex min-w-max items-center gap-2 rounded-xl px-2.5 py-2 text-left text-[12.5px] leading-tight transition hover:bg-muted sm:min-w-0",
            s.done ? "text-foreground" : "text-muted-foreground")}>
          <span className={cn("flex size-5 shrink-0 items-center justify-center rounded-full font-mono text-[11px]",
            s.done ? "bg-signal text-white" : "border border-foreground/20")}>{i + 1}</span>
          {s.label}
        </button>
      ))}
    </nav>
  );
}
