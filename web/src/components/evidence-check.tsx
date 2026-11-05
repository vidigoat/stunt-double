"use client";

import { useState } from "react";
import { FileLock2, ShieldCheck, ShieldX } from "lucide-react";
import { cn } from "@/lib/utils";
import { verifyInBrowser, type Check, type Sealed } from "@/lib/evidence";

type Evidence = { chain: Sealed };

/** "Is this record what the server signed?" answered in the visitor's own browser, then one changed cent to watch it fail. */
export function EvidenceCheck({ runId }: { runId: string }) {
  const [ev, setEv] = useState<{ ev: Evidence; key: string } | null>(null);
  const [res, setRes] = useState<Check | null>(null);
  const [tampered, setTampered] = useState<Check | null>(null);
  const [busy, setBusy] = useState(false);

  async function check(e: Evidence, key: string): Promise<Check> {
    try { return await verifyInBrowser(e.chain, key); }
    catch {   // a browser without Ed25519 in WebCrypto: ask the server to run the same check
      const r = await fetch("/api/evidence/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(e) }).then((x) => x.json());
      return { ok: !!r.ok, entries: r.entries ?? e.chain.entries.length, reason: r.reason ?? null, where: "server" };
    }
  }

  async function run() {
    setBusy(true); setTampered(null);
    try {
      const [e, k] = await Promise.all([fetch(`/api/runs/${runId}/evidence`).then((r) => r.json()), fetch("/api/evidence/key").then((r) => r.json())]);
      setEv({ ev: e, key: k.public_key });
      setRes(await check(e, k.public_key));
    } finally { setBusy(false); }
  }

  async function tamper() {
    if (!ev) return;
    const e: Evidence = JSON.parse(JSON.stringify(ev.ev));
    const step = e.chain.entries.find((x) => x.kind === "rehearsal") ?? e.chain.entries[0];
    const b = step.body as { measured?: { payments?: { total_cents?: number } }; task?: string };
    if (b.measured?.payments && typeof b.measured.payments.total_cents === "number") b.measured.payments.total_cents += 1;
    else b.task = `${b.task ?? ""}.`;
    setTampered(await check(e, ev.key));
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t px-5 py-3 text-sm">
      <FileLock2 className="size-4 shrink-0 text-muted-foreground" />
      {!res ? (
        <>
          <span className="text-muted-foreground">Every step of this run is sealed in a hash chain signed by the server.</span>
          <button onClick={run} disabled={busy} className="font-medium text-signal hover:underline disabled:opacity-50">{busy ? "Checking…" : "Verify it in your browser"}</button>
        </>
      ) : (
        <>
          <span className={cn("inline-flex items-center gap-1.5 font-medium", res.ok ? "text-safe" : "text-damage")}>
            {res.ok ? <ShieldCheck className="size-4" /> : <ShieldX className="size-4" />}
            {res.ok ? `Verified: ${res.entries} steps, each linked to the one before, signed with Ed25519` : `Not verified: ${res.reason}`}
          </span>
          <span className="text-xs text-muted-foreground">checked {res.where === "browser" ? "in your browser" : "by the server"}</span>
          {res.ok && !tampered ? <button onClick={tamper} className="text-signal hover:underline">Now change one cent and check again</button> : null}
          {tampered ? (
            <span className={cn("inline-flex items-center gap-1.5", tampered.ok ? "text-safe" : "text-damage")}>
              {tampered.ok ? <ShieldCheck className="size-4" /> : <ShieldX className="size-4" />}
              {tampered.ok ? "Still verifies (unexpected)" : `One cent changed: ${tampered.reason}`}
            </span>
          ) : null}
        </>
      )}
    </div>
  );
}
