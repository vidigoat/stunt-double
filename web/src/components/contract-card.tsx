"use client";

import { useState } from "react";
import { FileSignature } from "lucide-react";
import { cn } from "@/lib/utils";
import { num, type Contract, type ContractResult, type Pledge } from "@/lib/api";

const PILL: Record<string, { label: string; cls: string }> = {
  kept: { label: "kept", cls: "bg-safe/10 text-safe" },
  met: { label: "done", cls: "bg-safe/10 text-safe" },
  broken: { label: "broken", cls: "bg-damage/10 text-damage" },
  unmet: { label: "not done", cls: "bg-signal-soft text-signal" },
  unknown: { label: "couldn't check", cls: "bg-muted text-muted-foreground" },
  pending: { label: "waiting for a plan", cls: "bg-muted text-muted-foreground" },
};

function Line({ p, onStrike }: { p: Pledge & { status?: string; after?: number | null }; onStrike?: (reason: string) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [striking, setStriking] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const pill = PILL[p.status ?? "pending"] ?? PILL.pending;
  const counts = p.kind === "obligation"
    ? p.after == null ? `${num(p.today)} to do today` : p.after === 0 ? `${num(p.today)} to do · all done` : `${num(p.today)} to do · ${num(p.after)} left`
    : p.after == null ? "nothing breaks it today" : p.after === 0 ? "nothing breaks it" : `${num(p.after)} row${p.after === 1 ? "" : "s"} break it`;
  return (
    <li className={cn("rounded-xl border p-3", p.status === "broken" ? "border-damage/40 bg-damage/[0.04]" : "bg-background")}>
      <div className="flex flex-wrap items-start gap-x-3 gap-y-1.5">
        <span className={cn("mt-0.5 shrink-0 rounded-full px-2 py-0.5 font-mono text-[11px]", pill.cls)}>{pill.label}</span>
        <span className="min-w-0 flex-1 text-[15px] leading-snug">{p.text}</span>
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 pl-0.5 text-xs text-muted-foreground">
        <span className="font-mono uppercase tracking-wider">{p.kind === "guard" ? "guard" : "the work"}</span>
        <span className={cn("font-mono", p.status === "broken" && "text-damage")}>{counts}</span>
        {onStrike ? <button className="ml-auto hover:text-foreground hover:underline" onClick={() => setStriking((v) => !v)}>Disagree?</button> : null}
        <button className={cn("text-signal hover:underline", !onStrike && "ml-auto")} onClick={() => setOpen((v) => !v)}>{open ? "Hide the check" : "The check"}</button>
      </div>
      {striking && onStrike ? (
        <form className="mt-2 flex flex-wrap gap-2" onSubmit={async (e) => {
          e.preventDefault(); setBusy(true);
          try { await onStrike(reason); setStriking(false); } finally { setBusy(false); }
        }}>
          <input value={reason} onChange={(e) => setReason(e.target.value)} minLength={10} maxLength={500} required aria-label="Why this promise is wrong"
            placeholder="Why is this promise wrong for your business? (goes in the signed record)"
            className="h-9 min-w-0 flex-1 rounded-full border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50" />
          <button disabled={busy || reason.trim().length < 10} className="h-9 rounded-full border px-3 text-sm hover:bg-muted disabled:opacity-50">Strike it</button>
        </form>
      ) : null}
      {open ? <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-muted/60 px-3 py-2 font-mono text-[11px] leading-relaxed">{p.sql}</pre> : null}
    </li>
  );
}

/** Intent Contract: what the request means, written down before any plan existed, then checked against the plan. */
export function ContractCard({ contract, result, className, onStrike }: {
  contract: Contract; result?: ContractResult; className?: string; onStrike?: (index: number, reason: string) => Promise<void>;
}) {
  if (contract.status === "writing") {
    return (
      <div className={cn("flex items-center gap-3 rounded-2xl border bg-card px-5 py-4 text-sm", className)}>
        <span className="relative flex size-2.5"><span className="absolute inline-flex size-full animate-ping rounded-full bg-signal opacity-60" /><span className="relative inline-flex size-2.5 rounded-full bg-signal" /></span>
        <span><span className="font-medium">Writing the contract.</span> <span className="text-muted-foreground">What your request means, from the request, the glossary and the schema alone, before any plan exists.</span></span>
      </div>
    );
  }
  if (contract.status !== "ready" || !contract.promises?.length) return null;
  const rows = result?.promises?.length ? result.promises : contract.promises;
  const broken = result?.broken ?? 0, unmet = result?.unmet ?? 0;
  const checked = result?.status === "checked";
  const title = !checked ? `${contract.promises.length} promises, written before the plan`
    : broken ? `The plan breaks ${broken === 1 ? "a promise" : `${broken} promises`} made before it existed`
    : unmet ? "The plan leaves part of the work undone" : "Every promise kept";
  return (
    <div className={cn("animate-rise rounded-2xl border bg-card", broken ? "border-damage/40" : "", className)}>
      <div className="flex flex-wrap items-start gap-3 p-5">
        <FileSignature className={cn("mt-0.5 size-5 shrink-0", broken ? "text-damage" : unmet ? "text-signal" : checked ? "text-safe" : "text-signal")} />
        <div className="min-w-0 flex-1">
          <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Consequence engine · intent contract</div>
          <div className={cn("mt-1 font-display text-2xl", broken ? "text-damage" : checked && !unmet ? "text-safe" : "")}>{title}</div>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            Written by {contract.model ?? "a model on Vultr"} from the request, the business glossary and the schema. The plan never saw it, so it
            can&apos;t bend it{checked ? ", and code with no AI checked every promise against what the rehearsal measured" : ""}.
            {contract.cached ? " Same request and data as before, so the contract was reused." : ""}
          </p>
          {contract.cross_check?.status === "agree" ? (
            <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-safe/10 px-2.5 py-1 text-xs text-safe">
              Cross-checked by {contract.cross_check.model}: it read the request the same way{contract.cross_check.ours ? `, ${num(contract.cross_check.ours)} to do` : ""}
            </p>
          ) : contract.cross_check?.status === "disagree" ? (
            <p className="mt-2 rounded-xl border border-signal/40 bg-signal-soft px-3 py-2 text-sm">
              <span className="font-medium">Your request is ambiguous.</span> {contract.cross_check.model} read it differently: {num(contract.cross_check.theirs ?? 0)} to do,
              not {num(contract.cross_check.ours ?? 0)}. A glossary entry for the term they disagree on settles it for every future run.
            </p>
          ) : null}
        </div>
      </div>
      <ul className="space-y-2 border-t px-5 py-4">
        {rows.map((p, i) => <Line key={`${i}:${p.text}`} p={p} onStrike={onStrike && rows.length > 1 ? (r) => onStrike(i, r) : undefined} />)}
      </ul>
      {contract.struck?.length ? (
        <div className="space-y-1 border-t px-5 py-3 text-xs text-muted-foreground">
          {contract.struck.map((x, i) => (
            <p key={i}><span className="line-through">{x.text}</span> <span className="text-foreground">Struck by {x.by}:</span> “{x.reason}”</p>
          ))}
        </div>
      ) : null}
      {contract.withdrawn?.length ? (
        <p className="border-t px-5 py-3 text-xs text-muted-foreground">
          {contract.withdrawn.length === 1 ? "One promise was" : `${contract.withdrawn.length} promises were`} withdrawn before checking: a plan the jury judged
          correct for this same request failed {contract.withdrawn.length === 1 ? "it" : "them"}, so the mistake was the contract&apos;s, not the plan&apos;s.
        </p>
      ) : null}
    </div>
  );
}
