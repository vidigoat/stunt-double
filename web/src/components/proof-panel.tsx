"use client";

import { useEffect, useState } from "react";
import { BadgeCheck, CircleAlert, FileCode2, GitBranch } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, num, type Provenance, type ProvenanceDetail } from "@/lib/api";

/** One line of SQL, with the values that matter easy to see. */
function Sql({ sql, className }: { sql: string; className?: string }) {
  const parts = sql.replace(/\s+/g, " ").trim().split(/('(?:[^']|'')*'|\b\d+(?:\.\d+)?\b)/g);
  return (
    <code className={cn("block whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed", className)}>
      {parts.map((p, i) => (i % 2 ? <span key={i} className="text-signal">{p}</span>
        : <span key={i}>{p.split(/\b(SELECT|UPDATE|DELETE FROM|INSERT INTO|SET|WHERE|FROM|JOIN|GROUP BY|HAVING|AND|OR|NOT IN|IN|ON|VALUES)\b/g)
          .map((w, k) => (k % 2 ? <b key={k} className="font-semibold">{w}</b> : w))}</span>))}
    </code>
  );
}

const STATUS: Record<Provenance["status"], { icon: typeof BadgeCheck; tone: string; title: (p: Provenance) => string; line: (p: Provenance) => string }> = {
  proven: { icon: BadgeCheck, tone: "text-safe", title: () => "Proven",
    line: (p) => `Replaying the ${num(p.statements ?? 0)} statements the plan ran reproduces all ${num(p.rows_measured ?? 0)} measured changes. Every change has a reason.` },
  unexplained: { icon: CircleAlert, tone: "text-damage", title: (p) => `${num(p.unexplained ?? 0)} change${p.unexplained === 1 ? "" : "s"} the plan can't explain`,
    line: (p) => `The replay reproduces ${num(p.rows_explained ?? 0)} of ${num(p.rows_measured ?? 0)} measured changes. The rest happened some other way, so approval is locked.` },
  derived: { icon: GitBranch, tone: "text-safe", title: () => "Derived",
    line: () => "These effects were cut by the engine from a proven rehearsal. No plan code ran, so there is nothing to replay." },
  unavailable: { icon: CircleAlert, tone: "text-muted-foreground", title: () => "Not proven",
    line: (p) => `The record couldn't be replayed: ${p.reason ?? "unknown reason"}.` },
};

/** Proof of Effect: which statement of the plan caused which change, proven by replay. */
export function ProofPanel({ runId, attempt, summary, highlight = [] }: { runId: string; attempt: number; summary: Provenance; highlight?: number[] }) {
  const [d, setD] = useState<ProvenanceDetail | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => { api.provenance(runId, attempt).then(setD).catch(() => setD(null)); }, [runId, attempt]);
  const s = STATUS[summary.status] ?? STATUS.unavailable;
  const list = d?.statements ?? [];
  return (
    <div className={cn("rounded-2xl border bg-card", summary.status === "unexplained" && "border-damage/40")}>
      <div className="flex flex-wrap items-start gap-3 p-5">
        <s.icon className={cn("mt-0.5 size-5 shrink-0", s.tone)} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Consequence engine · proof of effect</span>
          </div>
          <div className={cn("mt-1 font-display text-2xl", s.tone)}>{s.title(summary)}</div>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{s.line(summary)}</p>
        </div>
      </div>
      {d?.deciders?.length ? (
        <div className="space-y-2 border-t px-5 py-4">
          <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">The decisions</div>
          {d.deciders.slice(0, 3).map((x) => {
            const hot = highlight.includes(x.i);
            return (
              <div key={x.i} className={cn("rounded-xl border p-3", hot ? "border-damage/40 bg-damage/[0.04]" : "bg-background")}>
                <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  <FileCode2 className={cn("size-3.5", hot ? "text-damage" : "text-signal")} />
                  <span className="font-mono text-muted-foreground">statement {x.i} · a read</span>
                  <span className={cn("font-medium", hot ? "text-damage" : "text-foreground")}>chose {num(x.rows)} of the changed rows{hot ? ", including every row that was cut" : ""}</span>
                </div>
                <Sql sql={x.sql} className="max-h-48 overflow-auto rounded-lg bg-muted/60 px-3 py-2 text-foreground/90" />
              </div>
            );
          })}
        </div>
      ) : null}
      {d?.patterns?.length ? (
        <div className="space-y-2 border-t px-5 py-4">
          <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">The writes</div>
          {d.patterns.slice(0, 4).map((x) => (
            <div key={x.shape} className="rounded-xl border bg-background p-3">
              <div className="mb-2 flex items-center gap-3 text-xs">
                <span className="font-mono text-muted-foreground">{x.statements > 1 ? `${num(x.statements)} statements like this` : `statement ${x.first}`}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"><span className="block h-full rounded-full bg-signal" style={{ width: `${(x.rows / Math.max(1, d.patterns![0].rows)) * 100}%` }} /></span>
                <span className="font-mono">{num(x.rows)} row{x.rows === 1 ? "" : "s"}</span>
              </div>
              <Sql sql={x.statements > 1 ? x.shape : x.example} className="max-h-32 overflow-auto rounded-lg bg-muted/60 px-3 py-2 text-foreground/90" />
            </div>
          ))}
          {list.length ? <button className="text-sm text-signal hover:underline" onClick={() => setOpen((v) => !v)}>{open ? "Hide the individual statements" : (summary.statements ?? 0) > list.length ? `Show the ${num(list.length)} statements that changed the most rows (of ${num(summary.statements ?? 0)})` : `Show the ${num(list.length)} individual statements`}</button> : null}
          {open ? (
            <ol className="max-h-80 space-y-1 overflow-auto rounded-xl border bg-background p-2">
              {list.map((x) => <li key={x.i} className="flex gap-3 rounded px-2 py-1 font-mono text-[11px] hover:bg-muted"><span className="w-12 shrink-0 text-muted-foreground">#{x.i}</span><span className="min-w-0 flex-1 truncate">{x.sql}</span><span className="shrink-0 text-muted-foreground">{x.rows}</span></li>)}
            </ol>
          ) : null}
        </div>
      ) : null}
      {d?.unexplained?.length ? (
        <div className="border-t px-5 py-4 text-sm">
          <div className="font-medium text-damage">Changed, but by no statement on record</div>
          <ul className="mt-1.5 flex flex-wrap gap-1.5 font-mono text-[12px]">
            {d.unexplained.slice(0, 12).map((u) => <li key={`${u.table}:${u.rowid}`} className="rounded bg-damage/10 px-1.5 py-0.5 text-damage">{u.table} #{u.rowid} {u.op}</li>)}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
