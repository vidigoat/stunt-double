"use client";

import { useEffect, useMemo, useState } from "react";
import { Banknote, Database, Globe, Mail, Network, CircleDot } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, num, type GraphSummary, type GraphUnit } from "@/lib/api";

const KIND = {
  row: { icon: Database, label: "row change", cls: "border-foreground/15 bg-card" },
  refund: { icon: Banknote, label: "refund", cls: "border-foreground/15 bg-card" },
  email: { icon: Mail, label: "email", cls: "border-foreground/15 bg-card" },
  http: { icon: Globe, label: "API call", cls: "border-foreground/15 bg-card" },
  context: { icon: CircleDot, label: "unchanged, ties it together", cls: "border-dashed bg-muted/40 text-muted-foreground" },
} as const;

function Pill({ n, tone }: { n?: GraphUnit["nodes"][number]; tone?: "cut" | "keep" }) {
  if (!n) return <span className="text-muted-foreground">…</span>;
  const k = KIND[n.kind as keyof typeof KIND] ?? KIND.context;
  return (
    <span className={cn("inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-lg border px-2 py-1 text-[12.5px]", k.cls,
      n.kind !== "context" && tone === "cut" && "border-damage/40 bg-damage/[0.06] text-damage", n.kind !== "context" && tone === "keep" && "border-safe/40 bg-safe/[0.06]")}>
      <k.icon className="size-3.5 shrink-0" /><span className="truncate">{n.label}</span>
    </span>
  );
}

/** The Effect Graph: every consequence of the plan linked into units of work, one square each; pick one to see why its parts belong together. */
export function EffectGraph({ runId, attempt, summary, dropped }: { runId: string; attempt: number; summary: GraphSummary; dropped?: number[] }) {
  const cut = useMemo(() => new Set(dropped ?? []), [dropped]);
  const [sel, setSel] = useState<number>(() => (dropped?.length ? dropped[0] : 0));
  const [unit, setUnit] = useState<GraphUnit | null>(null);
  useEffect(() => { setUnit(null); api.graphUnit(runId, attempt, sel).then(setUnit).catch(() => setUnit(null)); }, [runId, attempt, sel]);
  const byId = useMemo(() => new Map((unit?.nodes ?? []).map((n) => [n.id, n])), [unit]);
  const n = Math.min(summary.units, 1200);
  const tone = dropped ? (cut.has(sel) ? "cut" : "keep") : undefined;
  const kinds = Object.entries(summary.by_kind).map(([k, v]) => `${num(v)} ${KIND[k as keyof typeof KIND]?.label ?? k}${v === 1 ? "" : "s"}`).join(" · ");
  return (
    <div className="rounded-2xl border bg-card">
      <div className="flex flex-wrap items-start gap-3 p-5">
        <Network className="mt-0.5 size-5 shrink-0 text-signal" />
        <div className="min-w-0 flex-1">
          <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Consequence engine · effect graph</div>
          <div className="mt-1 font-display text-2xl">{num(summary.units)} unit{summary.units === 1 ? "" : "s"} of work</div>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            {kinds}, linked by {num(summary.edges)} foreign keys, charge ids and recipients. Each unit lives or dies whole: a refund never leaves without its email.
            {summary.units > n ? ` Showing ${num(n)} squares; each stands for a few units.` : ""}
          </p>
        </div>
      </div>
      <div className="border-t px-5 py-4">
        <div className="flex flex-wrap gap-[2px]" role="listbox" aria-label="Units of work: use the arrow keys" onKeyDown={(e) => {
          const kids = e.currentTarget.children;
          let cols = 1;
          while (cols < kids.length && (kids[cols] as HTMLElement).offsetTop === (kids[0] as HTMLElement).offsetTop) cols++;
          const step = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: cols, ArrowUp: -cols }[e.key];
          if (step === undefined) return;
          e.preventDefault();
          const next = Math.min(summary.units - 1, Math.max(0, sel + step));
          setSel(next);
          (e.currentTarget.querySelector(`[data-unit="${next}"]`) as HTMLElement | null)?.focus();
        }}>
          {Array.from({ length: n }, (_, i) => {
            const u = Math.floor((i * summary.units) / n);
            return (
              <button key={i} role="option" aria-selected={u === sel} data-unit={u} tabIndex={u === sel ? 0 : -1} title={`Unit ${u + 1}${dropped ? (cut.has(u) ? " · cut" : " · kept") : ""}`} onClick={() => setSel(u)}
                className={cn("size-[7px] rounded-[1.5px] transition hover:scale-150", dropped ? (cut.has(u) ? "bg-damage/80" : "bg-safe") : "bg-signal/70",
                  u === sel && "scale-150 ring-2 ring-foreground ring-offset-1 ring-offset-card")} />
            );
          })}
        </div>
        <div className="mt-1.5 font-mono text-[11px] text-muted-foreground">{dropped ? <><span className="text-safe">■</span> kept · <span className="text-damage">■</span> cut by the engine · </> : null}click a square</div>
      </div>
      <div className="border-t px-5 py-4">
        <div className="mb-2 flex flex-wrap items-baseline gap-x-3 text-sm">
          <span className="font-medium">Unit {num(sel + 1)}</span>
          {tone ? <span className={cn("font-mono text-[11px] uppercase tracking-wider", tone === "cut" ? "text-damage" : "text-safe")}>{tone === "cut" ? "cut: breaks a check" : "kept"}</span> : null}
        </div>
        {unit ? (
          <ul className="space-y-1.5">
            {unit.edges.map(([a, b, why], i) => (
              <li key={i} className="grid items-center gap-1.5 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:gap-3">
                <Pill n={byId.get(a)} tone={tone} />
                <span className="font-mono text-[11px] text-muted-foreground">{why}</span>
                <Pill n={byId.get(b)} tone={tone} />
              </li>
            ))}
            {!unit.edges.length ? unit.nodes.map((x) => <li key={x.id}><Pill n={x} tone={tone} /></li>) : null}
          </ul>
        ) : <div className="h-16 animate-pulse rounded-lg bg-muted/50" />}
      </div>
    </div>
  );
}
