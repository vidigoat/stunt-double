"use client";

import { useEffect, useState } from "react";
import { Cloud, FileLock2, ShieldCheck, ShieldX } from "lucide-react";
import { cn } from "@/lib/utils";
import { verifyInBrowser, type Check, type Sealed } from "@/lib/evidence";
import type { Archived } from "@/lib/api";

type Evidence = { chain: Sealed };

/** "Is this record what the server signed?" answered in the visitor's own browser, then one changed cent to watch it fail. */
export function EvidenceCheck({ runId, archive }: { runId: string; archive?: Archived | null }) {
  const [ev, setEv] = useState<{ ev: Evidence; key: string } | null>(null);
  const [arch, setArch] = useState<Archived | null>(archive ?? null);
  useEffect(() => {   // the archive upload finishes a moment after the decision: look for it a few times
    setArch(archive ?? null);
    if (archive?.key) return;
    let n = 0; let alive = true;
    const tick = async () => {
      if (!alive || n++ > 6) return;
      const r = await fetch(`/api/runs/${runId}`).then((x) => x.json()).catch(() => null);
      if (alive && r?.archive?.key) setArch(r.archive); else setTimeout(tick, 1500);
    };
    const t = setTimeout(tick, 1200);
    return () => { alive = false; clearTimeout(t); };
  }, [runId, archive]);
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
    <>
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
    {arch?.key ? (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t px-5 py-2.5 text-sm">
        <Cloud className="size-4 shrink-0 text-signal" />
        <span className="text-muted-foreground">Stored on <span className="font-medium text-foreground">Vultr Object Storage</span>{arch.host ? <span className="font-mono text-xs"> · {arch.host}</span> : null}{arch.sha256 ? <span className="font-mono text-xs"> · sha256 {arch.sha256.slice(0, 12)}…</span> : null}</span>
        <a href={`/api/runs/${runId}/archive`} target="_blank" rel="noreferrer" className="font-medium text-signal hover:underline">Download it from Vultr ↗</a>
      </div>
    ) : null}
    </>
  );
}
