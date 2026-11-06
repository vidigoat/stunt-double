"use client";

import { useEffect, useRef, useState } from "react";
import { Cloud, CreditCard, Database, Lock, Mail, MousePointerClick, Server, Webhook } from "lucide-react";
import { BrandLogo, type LogoName } from "@/components/brand-logos";
import { cn } from "@/lib/utils";

type Item = { key: string; icon: typeof Database; name: string; line: string; visual: () => React.ReactNode; logos?: LogoName[] };

const ROWS = [["#18", "charges", "status", "succeeded", "refunded"], ["#93", "charges", "status", "succeeded", "refunded"], ["#240", "charges", "refunded_at", "—", "2026-11-05"]];

const ITEMS: Item[] = [
  { key: "db", icon: Database, logos: ["postgres", "sqlite"], name: "Your database", line: "Your SQLite or PostgreSQL data, cloned. Every changed row is measured and replayed only if nobody touched it since.",
    visual: () => (
      <div className="w-full max-w-md rounded-xl border bg-card p-4 shadow-sm">
        <div className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Rows · 104 updated in charges</div>
        <div className="mt-3 divide-y rounded-lg border font-mono text-[12px]">
          {ROWS.map(([id, t, col, a, b]) => (
            <div key={id + col} className="grid grid-cols-[48px_1fr_auto] items-center gap-2 px-3 py-2">
              <span className="text-muted-foreground">{id}</span><span className="truncate">{t}.{col}</span>
              <span><span className="text-muted-foreground line-through">{a}</span> → <span className="text-foreground">{b}</span></span>
            </div>
          ))}
        </div>
        <div className="mt-3 text-xs text-muted-foreground">Drift check before apply: <span className="text-safe">passed</span></div>
      </div>
    ) },
  { key: "pay", icon: CreditCard, name: "Payments", line: "Refunds are recorded, checked against the real charge and the ledger, and paid once per charge.",
    visual: () => (
      <div className="w-full max-w-md rounded-xl border bg-card p-5 font-mono text-[12px] shadow-sm">
        <div className="flex justify-between text-muted-foreground"><span>BEANPAY · REHEARSED</span><span>NOV 5</span></div>
        <div className="mt-4 space-y-1.5">
          {[["refund ch_18", "$40.00"], ["refund ch_93", "$54.00"], ["refund ch_240", "$36.00"], ["… 101 more", ""]].map(([a, b]) => <div key={a} className="flex justify-between"><span>{a}</span><span>{b}</span></div>)}
        </div>
        <div className="mt-4 flex justify-between border-t border-dashed pt-3 text-[13px]"><span>TOTAL · 104 refunds</span><span>$5,136.00</span></div>
        <div className="mt-1 flex justify-between text-muted-foreground"><span>already refunded</span><span>0</span></div>
      </div>
    ) },
  { key: "mail", icon: Mail, name: "Email", line: "One real customer per message, no broken templates, no leaked data; unsubscribes respected.",
    visual: () => (
      <div className="w-full max-w-md rounded-xl border bg-card shadow-sm">
        <div className="border-b px-4 py-3 text-xs text-muted-foreground"><div>To: <span className="text-foreground">nora.dubois7@example.com</span></div><div>Subject: <span className="text-foreground">We refunded your duplicate charge</span></div></div>
        <div className="space-y-2 px-4 py-4 text-[13px] leading-relaxed"><p>Hi Nora,</p><p>We charged you twice for order #16. We&apos;ve refunded the extra $40.00. Sorry about that.</p><p className="text-muted-foreground">Bean There Coffee Co.</p></div>
        <div className="border-t px-4 py-2 font-mono text-[11px] text-muted-foreground">transactional · consent ok · 1 of 104</div>
      </div>
    ) },
  { key: "http", icon: Webhook, logos: ["slack"], name: "Any HTTP API", line: "Calls are recorded in the sandbox and delivered through a connector after approval, with the real token added then.",
    visual: () => (
      <div className="w-full max-w-md space-y-2 font-mono text-[12px]">
        <div className="rounded-xl border bg-card p-4 shadow-sm"><div className="flex items-center gap-2"><BrandLogo name="slack" tone="brand" className="size-4" /><span>POST hooks.slack.com/services/…</span></div>
          <div className="mt-2 text-muted-foreground">{`{ "text": "104 refunds are going out" }`}</div></div>
        <div className="rounded-xl border border-dashed p-3 text-muted-foreground">sandbox: recorded, not sent · token: none<br />after approval: delivered once · Idempotency-Key</div>
      </div>
    ) },
  { key: "browser", icon: MousePointerClick, name: "A real browser", line: "Agents click through a double of the admin site in a real Chromium, inside the sandbox. Every screen is captured; an AI vision check reads them.",
    visual: () => (
      <div className="w-full max-w-lg">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/doubles/browser.png" alt="A real screenshot from the sandbox: the agent cancelled #4141 instead of #4411" className="w-full rounded-xl border bg-white shadow-sm" />
        <div className="mt-3 rounded-xl border border-damage/30 bg-damage-soft/60 px-4 py-3 text-[13px]">
          <span className="font-medium">AI vision check:</span> “Agent cancelled her original subscription, not the duplicate.”
        </div>
      </div>
    ) },
  { key: "cloud", icon: Cloud, logos: ["vultr"], name: "Your Vultr cloud", line: "Import a read-only double of your real Vultr fleet (the key is used once, never kept). Delete, stop or resize servers there first: blast radius and bill change, production protected.",
    visual: () => (
      <div className="grid w-full max-w-md grid-cols-2 gap-2 text-xs">
        {[["prod-db-replica", true, "$40", "would delete"], ["prod-backup-runner", true, "$10", "would delete"], ["ci-runner-old", false, "$20", "delete"], ["ml-experiment", false, "$40", "delete"]].map(([l, prod, cost, st]) => (
          <div key={String(l)} className={cn("rounded-xl border p-3 shadow-sm", prod ? "border-damage/50 bg-damage-soft/60" : "bg-card")}>
            <div className="flex items-center gap-1.5 font-mono font-medium">{prod ? <Lock className="size-3" /> : <Server className="size-3 text-muted-foreground" />}<span className="truncate">{l}</span></div>
            <div className="mt-2 flex justify-between"><span className={cn("rounded px-1.5 py-0.5 font-mono text-[10px] uppercase", prod ? "bg-damage text-white" : "bg-foreground text-background")}>{st}</span><span className="font-mono">{cost}/mo</span></div>
          </div>
        ))}
        <div className="col-span-2 rounded-xl border bg-card px-3 py-2 font-mono text-[11px] text-muted-foreground">production touched: 2 → <span className="text-damage">blocked by policy</span></div>
      </div>
    ) },
];

/** "Everything your agent touches": a list of doubles that auto-advances, with what each one shows the approver. */
export function DoublesShowcase() {
  const [i, setI] = useState(0);
  const paused = useRef(false);
  useEffect(() => {
    const t = setInterval(() => { if (!paused.current) setI((x) => (x + 1) % ITEMS.length); }, 4500);
    return () => clearInterval(t);
  }, []);
  const active = ITEMS[i];
  return (
    <div className="mt-10 grid items-stretch gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]" onMouseEnter={() => (paused.current = true)} onMouseLeave={() => (paused.current = false)}>
      <ol className="border-t">
        {ITEMS.map((it, k) => (
          <li key={it.key} className="border-b">
            <button onClick={() => setI(k)} className={cn("relative flex w-full items-start gap-3 py-4 text-left transition", k === i ? "opacity-100" : "opacity-45 hover:opacity-80")}>
              <it.icon className={cn("mt-0.5 size-4 shrink-0", k === i && "text-signal")} />
              <span>
                <span className="flex items-center gap-2 text-[16px] font-medium">{it.name}{it.logos?.map((l) => <BrandLogo key={l} name={l} tone="brand" className="size-4" />)}</span>
                {k === i ? <span className="mt-1 block text-[14px] leading-relaxed text-muted-foreground">{it.line}</span> : null}
              </span>
              {k === i ? <span key={i} className="absolute -bottom-px left-0 h-px w-full origin-left animate-[grow_4.5s_linear] bg-signal" /> : null}
            </button>
          </li>
        ))}
      </ol>
      <div className="grain backdrop-blue flex min-h-[380px] items-center justify-center overflow-hidden rounded-[22px] p-6 sm:p-10 [&>*]:relative [&>*]:z-[2]">
        <div key={active.key} className="animate-rise flex w-full justify-center">{active.visual()}</div>
      </div>
    </div>
  );
}
