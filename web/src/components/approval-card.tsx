"use client";

import { AlertTriangle, CheckCircle2, Info, OctagonX, ShieldCheck } from "lucide-react";
import type { Attempt, Flag, Verdict } from "@/lib/api";
import { num } from "@/lib/api";
import { cn } from "@/lib/utils";
import { CountUp } from "@/components/count-up";

export type ApprovalView = {
  task: string;
  checking?: boolean;   // the AI verifier is still investigating: no verdict yet, and none implied
  moneyCents: number;
  cloudSavingsCents?: number;   // Vultr bill change per month (positive = cheaper)
  serversDeleted?: number;
  refunds: number;
  emails: number;
  rowsChanged: number;
  biggestChange?: string;
  verdict?: Verdict | null;
  flags: Flag[];
  sandboxId?: string;
  sandboxMs?: number;
  runtime?: string;
  plain?: string;
};

/** A deterministic, plain-English sentence from the measured consequences (no AI involved). */
export function plainEnglish(c: Attempt["consequences"]): string {
  if (!c.ok) return "The plan crashed in the sandbox, so nothing would be applied. Ask the agent to fix it or reject it.";
  const parts: string[] = [];
  if (c.payments.count) parts.push(`refunds ${(c.payments.total_cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD" })} across ${num(c.payments.count)} charges`);
  const vip = c.audit?.emails?.vip_count ?? 0;
  if (c.emails.count) parts.push(`emails ${num(c.emails.count)} ${c.emails.count === 1 ? "person" : "people"}${vip ? ` (${num(vip)} VIP${vip === 1 ? "" : "s"})` : ""}`);
  const cl = c.cloud;
  if (cl && cl.servers_before && cl.deleted.length + cl.stopped.length + cl.resized.length) {
    const names = cl.deleted.map((x) => x.label);
    if (cl.deleted.length) parts.push(`deletes ${num(cl.deleted.length)} Vultr server${cl.deleted.length === 1 ? "" : "s"} (${names.slice(0, 3).join(", ")}${names.length > 3 ? ", …" : ""})`);
    if (cl.stopped.length) parts.push(`stops ${num(cl.stopped.length)} server${cl.stopped.length === 1 ? "" : "s"}`);
    if (cl.resized.length) parts.push(`resizes ${num(cl.resized.length)} server${cl.resized.length === 1 ? "" : "s"}`);
    if (cl.monthly_savings_cents) parts.push(`${cl.monthly_savings_cents > 0 ? "cuts" : "raises"} the Vultr bill by ${(Math.abs(cl.monthly_savings_cents) / 100).toLocaleString("en-US", { style: "currency", currency: "USD" })}/month`);
  }
  for (const [t, d] of Object.entries(c.tables)) {
    if (t === "servers" && cl?.servers_before) continue;
    if (d.dropped) parts.push(`drops the entire ${t} table (${num(d.rows_before)} rows)`);
    else {
      const rows = (n: number) => (n === 1 ? `1 row in ${t}` : `${num(n)} ${t}`);
      if (d.deleted) parts.push(d.deleted === 1 ? `deletes 1 row in ${t}` : `deletes ${num(d.deleted)} of ${num(d.rows_before)} ${t}`);
      if (d.updated) parts.push(`changes ${rows(d.updated)} (${d.changed_columns.join(", ")})`);
      if (d.inserted) parts.push(`adds ${rows(d.inserted)}`);
    }
  }
  const calls = c.http?.count ?? 0;
  if (calls) parts.push(`makes ${num(calls)} API call${calls === 1 ? "" : "s"}`);
  if (!parts.length) return "If approved, nothing would change: no rows, no money, no emails.";
  const blocked = c.blocked.length ? ` It also tried to reach ${c.blocked[0].target}, which was blocked.` : "";
  const list = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}` : parts[0];
  return `If approved, this ${list}.${blocked} Nothing else leaves the sandbox.`;
}

export function viewFromAttempt(task: string, a: Attempt, verdict: Verdict | null, flags: Flag[]): ApprovalView {
  const c = a.consequences;
  const tables = Object.entries(c.tables);
  const rows = tables.reduce((s, [, t]) => s + t.deleted + t.updated + t.inserted, 0);
  const big = tables.sort((x, y) => (y[1].deleted + y[1].updated + y[1].inserted) - (x[1].deleted + x[1].updated + x[1].inserted))[0];
  const biggest = big ? `${big[0]}: ${[big[1].deleted && `${num(big[1].deleted)} deleted`, big[1].updated && `${num(big[1].updated)} updated`, big[1].inserted && `${num(big[1].inserted)} added`].filter(Boolean).join(", ")}` : undefined;
  const cl = c.cloud;
  const cloud = cl && cl.servers_before && (cl.deleted.length + cl.stopped.length + cl.resized.length) ? cl : null;
  return { task, moneyCents: c.payments.total_cents, refunds: c.payments.count,
    ...(cloud ? { cloudSavingsCents: cloud.monthly_savings_cents, serversDeleted: cloud.deleted.length } : {}), emails: c.emails.count, rowsChanged: rows, biggestChange: biggest,
    verdict, flags, sandboxId: c.sandbox?.id, sandboxMs: c.sandbox?.wall_ms, runtime: c.sandbox?.runtime, plain: plainEnglish(c) };
}

function tone(v: ApprovalView) {
  if (v.flags.some((f) => f.severity === "critical") || v.verdict?.verdict === "dangerous") return "danger";
  if (v.verdict?.verdict === "concerns" || v.flags.some((f) => f.severity === "high")) return "warn";
  if (v.verdict?.verdict === "looks_right") return "ok";
  return "checked"; // passed every deterministic check; no AI verdict (yet)
}

const VOTE = { looks_right: ["Looks right", "bg-safe"], concerns: ["Objects", "bg-[#E8A33D]"], dangerous: ["Dangerous", "bg-damage"] } as const;

/** The AI jury: independent models from different labs on Vultr Serverless Inference, each with its own words. */
function Jury({ jury }: { jury: NonNullable<NonNullable<ApprovalView["verdict"]>["jury"]> }) {
  return (
    <div className="rounded-xl border bg-background p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 px-1">
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">AI jury · {jury.votes.length} labs on Vultr Serverless Inference</div>
        <div className="font-mono text-[11px] text-muted-foreground">{jury.agree} of {jury.cast} agree · each investigated the data on its own</div>
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        {jury.votes.map((v) => {
          const [label, dot] = v.verdict ? VOTE[v.verdict] : ["Abstained", "bg-muted-foreground/40"];
          return (
            <div key={v.model} className="min-w-0 rounded-lg border px-3 py-2" title={v.model}>
              <div className="flex items-center gap-1.5 text-sm"><span className={cn("size-2 shrink-0 rounded-full", dot)} /><span className="font-medium">{v.lab}</span><span className="ml-auto text-xs text-muted-foreground">{label}</span></div>
              <div className="mt-1 line-clamp-2 text-xs leading-snug text-muted-foreground">{v.headline}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Stat({ label, value, hot, good, sub, small }: { label: string; value: React.ReactNode; hot?: boolean; good?: boolean; sub?: string; small?: boolean }) {
  return (
    <div className={cn("min-w-0 rounded-xl border px-4 py-3", hot && small ? "border-damage/25 bg-damage-soft/60" : good ? "border-safe/25 bg-safe-soft/70" : "bg-background")}>
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={cn("mt-1 truncate tabular", small ? "pt-1 font-display text-[22px] leading-[1.15] 2xl:text-[26px]" : "font-mono text-2xl sm:text-[28px]", hot && "text-damage", good && "text-safe")}>{value}</div>
      {sub ? <div className="mt-0.5 truncate text-xs text-muted-foreground">{sub}</div> : null}
    </div>
  );
}

export function ApprovalCard({ view, children, className, label = "Approval required", applied }: { view: ApprovalView; children?: React.ReactNode; className?: string; label?: string; applied?: string }) {
  const t = tone(view);
  const hot = t === "danger" || t === "warn";
  const issues = [...view.flags.map((f) => ({ severity: f.severity, title: f.title, detail: f.detail })), ...(view.verdict?.concerns ?? [])];
  return (
    <div className={cn("overflow-hidden rounded-2xl border bg-card text-left shadow-[0_1px_0_rgba(0,0,0,.04),0_24px_48px_-24px_rgba(0,0,0,.18)]", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-muted/60 px-5 py-2.5 font-mono text-[11px] text-muted-foreground">
        <span className="flex items-center gap-2 uppercase tracking-wider text-foreground">
          <span className={cn("size-1.5 rounded-full", hot ? "bg-damage" : applied || t === "ok" ? "bg-safe shadow-[0_0_0_3px_var(--safe-soft)]" : "bg-signal shadow-[0_0_0_3px_var(--signal-soft)]")} />{label}
        </span>
        {view.sandboxId ? <span className="truncate">rehearsed in {view.sandboxId} · {view.runtime === "runsc" ? "gVisor" : `${view.runtime} (dev host, no gVisor)`} · {view.sandboxMs} ms · destroyed</span> : null}
      </div>
      <div className="space-y-5 p-5 sm:p-6">
        <div className="space-y-1.5">
          <div className="text-[15px] leading-snug text-muted-foreground">“{view.task}”</div>
          {applied ? <p className="text-[15px] leading-snug">{applied}</p> : view.plain ? <p className="text-[15px] leading-snug">{view.plain}</p> : null}
        </div>
        <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4">
          {view.cloudSavingsCents !== undefined && !view.refunds
            ? <Stat label="Vultr bill" value={<>{view.cloudSavingsCents >= 0 ? "−" : "+"}<CountUp value={Math.abs(view.cloudSavingsCents)} format="usd" /></>} sub={`per month · ${num(view.serversDeleted ?? 0)} servers deleted`} />
            : <Stat label="Money out" value={<CountUp value={view.moneyCents} format="usd" />} hot={hot && view.moneyCents > 0} sub={`${num(view.refunds)} refunds`} />}
          <Stat label="Emails" value={<CountUp value={view.emails} />} sub={applied ? "approved" : "would be sent"} />
          <Stat label="Rows changed" value={<CountUp value={view.rowsChanged} />} hot={t === "danger" && view.rowsChanged > 0} sub={view.biggestChange} />
          {view.checking && !hot ? <Stat label="Verdict" value="Checking…" small sub="AI verifier at work" />
            : <Stat label="Verdict" value={t === "ok" ? "Looks right" : t === "danger" ? "Critical" : t === "warn" ? "Check this" : "Rules pass"} hot={hot} good={!hot} small sub={view.verdict?.jury ? `${view.verdict.jury.cast} AI models` : view.verdict ? "checked by the AI" : "policy checks only"} />}
        </div>
        {view.verdict?.jury ? <Jury jury={view.verdict.jury} /> : null}
        {view.verdict || issues.length ? (
          <div className={cn("rounded-xl border p-4", hot ? "border-damage/30 bg-damage/[0.04]" : "bg-background")}>
            <div className="flex items-start gap-3">
              {t === "danger" ? <OctagonX className="mt-0.5 size-5 shrink-0 text-damage" /> : hot ? <AlertTriangle className="mt-0.5 size-5 shrink-0 text-damage" /> : view.verdict?.verdict === "looks_right" && !issues.length ? <CheckCircle2 className="mt-0.5 size-5 shrink-0" /> : <Info className="mt-0.5 size-5 shrink-0 text-muted-foreground" />}
              <div className="min-w-0 space-y-1.5">
                {view.verdict ? <div className="font-medium">{view.verdict.headline}</div> : null}
                {view.verdict ? <p className="text-sm text-muted-foreground">{view.verdict.summary}</p> : null}
                {issues.length ? (
                  <ul className="space-y-1.5 pt-1 text-sm">
                    {issues.slice(0, 5).map((c, i) => (
                      <li key={i} className="flex gap-2">
                        <span className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", c.severity === "critical" || c.severity === "high" ? "bg-damage" : "bg-muted-foreground")} />
                        {c.severity === "critical" ? <span className="mt-0.5 shrink-0 self-start rounded bg-damage/10 px-1 py-px font-mono text-[10px] uppercase leading-4 text-damage">blocks</span> : null}
                        <span><span className="font-medium">{c.title}.</span> <span className="text-muted-foreground">{c.detail}</span></span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
        {!view.verdict && !view.checking && !applied && t !== "danger" ? (
          <p className="rounded-xl border border-dashed px-4 py-3 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Only rules ran.</span> Rules check <em>what</em> a plan does, not whether it&apos;s what you <em>meant</em>.
            Telling “same item, same day” apart from “charged twice” is the AI verifier&apos;s job (Vultr Serverless Inference).
          </p>
        ) : null}
        {children ? <div className="flex flex-wrap items-center gap-2">{children}</div> : null}
        {!applied ? <div className="flex items-center gap-1.5 text-xs text-muted-foreground"><ShieldCheck className="size-3.5" /> Nothing real has happened yet. Approving replays exactly these changes, after a drift check.</div> : null}
      </div>
    </div>
  );
}
