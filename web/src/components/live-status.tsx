"use client";

import { useEffect, useState } from "react";

type Health = { sandbox_runtime?: string; sandbox_ready?: boolean; inference_configured?: boolean; agent_model?: string; verifier_model?: string };

/** Proof, not a claim: what this server is actually running right now, read from /api/health. */
export function LiveStatus() {
  const [h, setH] = useState<Health | null>(null);
  useEffect(() => { fetch("/api/health", { cache: "no-store" }).then((r) => r.json()).then(setH).catch(() => setH(null)); }, []);
  if (!h) return null;
  const live = h.sandbox_ready && h.inference_configured;
  const sandbox = h.sandbox_runtime === "runsc" ? "gVisor (runsc)" : `${h.sandbox_runtime} sandbox`;
  return (
    <div className="mt-5 inline-flex max-w-full flex-wrap items-center justify-center gap-x-2 gap-y-1 rounded-full border bg-card px-3 py-1 font-mono text-[11px] text-muted-foreground">
      <span className={live ? "relative flex size-2" : "flex size-2"}>
        {live ? <span className="absolute inline-flex size-full animate-ping rounded-full bg-safe opacity-60" /> : null}
        <span className={`relative inline-flex size-2 rounded-full ${live ? "bg-safe" : "bg-muted-foreground"}`} />
      </span>
      <span className="text-foreground">{live ? "Live now" : "Server status"}</span>
      <span>· {sandbox}</span>
      {h.inference_configured ? <span>· {h.agent_model} on Vultr Serverless Inference</span> : <span>· AI offline</span>}
    </div>
  );
}
