"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Loader2, Play, ShieldAlert } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { num } from "@/lib/api";
import { cn } from "@/lib/utils";

const PLAN = `def run(ctx):\n    ctx.db.execute("DELETE FROM customers")\n`;
type Result = { sandbox: number; before: number; production: number; ms: number; runtime: string; id: string; blocked: string | null };

/** A real rehearsal from the landing page: a destructive plan runs in a real sandbox, production is checked after. */
export function TryIt() {
  const [state, setState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [res, setRes] = useState<Result | null>(null);
  const [err, setErr] = useState("");

  async function go() {
    setState("running"); setErr("");
    try {
      const r = await fetch("/api/runs/manual", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ task: "Clean up the customer table", code: PLAN }) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "Couldn't start a rehearsal");
      let run;
      for (let i = 0; i < 60; i++) {
        run = await fetch(`/api/runs/${j.id}`, { cache: "no-store" }).then((x) => x.json());
        if (!["queued", "planning", "rehearsing", "verifying"].includes(run.status)) break;
        await new Promise((ok) => setTimeout(ok, 500));
      }
      const c = run.attempts.at(-1).consequences;
      const biz = await fetch("/api/business", { cache: "no-store" }).then((x) => x.json());
      const crit = run.attempts.at(-1).flags.find((f: { severity: string }) => f.severity === "critical");
      setRes({ sandbox: c.row_counts.customers.after, before: c.row_counts.customers.before, production: biz.counts.customers,
        ms: c.sandbox.wall_ms, runtime: c.sandbox.runtime, id: run.id, blocked: crit ? crit.title : null });
      setState("done");
    } catch (e) { setErr((e as Error).message); setState("error"); }
  }

  return (
    <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
      <div className="grid items-center gap-8 rounded-3xl border bg-card p-5 sm:p-10 md:grid-cols-2">
        <div className="min-w-0">
          <div className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Try it right here</div>
          <h2 className="mt-3 font-display text-4xl leading-tight">Delete every customer. <em>Go on.</em></h2>
          <p className="mt-3 max-w-md text-[15px] leading-relaxed text-muted-foreground">This button sends a real plan, <span className="font-mono text-foreground">DELETE FROM customers</span>, to a real sandbox on this server. Then it checks production.</p>
          <pre className="mt-5 overflow-x-auto rounded-xl bg-foreground p-4 font-mono text-[13px] text-background">{PLAN}</pre>
          <button onClick={go} disabled={state === "running"} className={cn(buttonVariants(), "mt-5 h-11 rounded-full px-5 text-[15px]")}>
            {state === "running" ? <><Loader2 className="size-4 animate-spin" /> Rehearsing in a sandbox…</> : <><Play className="size-4 fill-current" /> {state === "done" ? "Run it again" : "Run it on the double"}</>}
          </button>
          {err ? <p className="mt-3 text-sm text-damage">{err}</p> : null}
        </div>
        <div className="grain backdrop-warm grid min-w-0 grid-cols-2 gap-3 rounded-[22px] p-3 text-center sm:p-6">
          <div className={cn("relative z-[2] min-w-0 rounded-2xl border p-3 shadow-[0_18px_40px_-24px_rgba(60,30,10,.45)] sm:p-5", res ? "border-damage/30 bg-[#fff6f5]" : "bg-card")}>
            <div className={cn("font-mono text-[11px] uppercase tracking-wider", res ? "text-damage" : "text-muted-foreground")}>sandbox customers</div>
            <div className={cn("mt-2 font-mono text-3xl tabular sm:text-5xl", res && "text-damage")}>{res ? num(res.sandbox) : "1,300"}</div>
            <div className="mt-1 text-xs text-muted-foreground">{res ? `was ${num(res.before)}` : "the double"}</div>
          </div>
          <div className="relative z-[2] min-w-0 rounded-2xl border bg-card p-3 shadow-[0_18px_40px_-24px_rgba(60,30,10,.45)] sm:p-5">
            <div className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">production customers</div>
            <div className="mt-2 font-mono text-3xl tabular sm:text-5xl">{res ? num(res.production) : "1,300"}</div>
            <div className="mt-1 text-xs text-muted-foreground">{res ? "untouched" : "the real thing"}</div>
          </div>
          {res ? (
            <div className="relative z-[2] col-span-2 space-y-2 rounded-xl bg-card/90 p-3 text-left">
              <div className="flex items-start gap-2 rounded-xl border border-damage/30 bg-damage/[0.04] px-4 py-3 text-sm"><ShieldAlert className="mt-0.5 size-4 shrink-0 text-damage" /><span><b className="font-medium">Approval locked.</b> {res.blocked}</span></div>
              <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[11px] text-muted-foreground">
                <span>{res.id} · {res.runtime === "runsc" ? "gVisor" : res.runtime} · {res.ms} ms · sandbox destroyed</span>
                <Link href={`/app?run=${res.id}`} className="inline-flex items-center gap-1 text-foreground underline-offset-4 hover:underline">Open in the console <ArrowRight className="size-3" /></Link>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
