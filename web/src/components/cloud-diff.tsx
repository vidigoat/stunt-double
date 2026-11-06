import { Lock, Server } from "lucide-react";
import { BrandLogo } from "@/components/brand-logos";
import { cn } from "@/lib/utils";
import { num, usd } from "@/lib/api";
import type { CloudConsequences, CloudServer } from "@/lib/api";

/** True if the plan changed the Vultr fleet (deleted, stopped or resized a server). */
export function cloudChanged(cl?: CloudConsequences | null): cl is CloudConsequences {
  return !!cl && !!cl.servers_before && (cl.deleted.length + cl.stopped.length + cl.resized.length) > 0;
}

/** The fleet as server cards: what the plan would delete, stop or resize, and what it does to the monthly bill. */
export function CloudDiff({ cl }: { cl: CloudConsequences }) {
  const deleted = new Set(cl.deleted.map((s) => s.id));
  const stopped = new Set(cl.stopped.map((s) => s.id));
  const resized = new Map(cl.resized.map((s) => [s.id, s]));
  const prodHit = cl.production_touched.length > 0;
  return (
    <div className={cn("animate-rise rounded-2xl border bg-card p-5", prodHit && "border-damage/30")}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <BrandLogo name="vultr" tone="brand" className="size-4" />
        <div className="text-sm font-medium">Vultr fleet · the double</div>
        <div className="ml-auto font-mono text-xs text-muted-foreground tabular">
          {num(cl.servers_before)} → {num(cl.servers_after)} servers ·{" "}
          <span className={cn(cl.monthly_savings_cents > 0 && !prodHit && "text-safe")}>
            {cl.monthly_savings_cents >= 0 ? "−" : "+"}{usd(Math.abs(cl.monthly_savings_cents))}/month
          </span>
        </div>
      </div>
      {prodHit ? (
        <p className="mt-2 text-sm text-damage">
          Would remove production: <b className="font-medium">{cl.production_touched.join(", ")}</b>. Low CPU is not the same as unused.
        </p>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">Nothing tagged production is touched. Deleted servers can&apos;t be undone, so this still needs your approval.</p>
      )}
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
        {cl.fleet.map((s) => <ServerCard key={s.id} s={s} state={deleted.has(s.id) ? "deleted" : stopped.has(s.id) ? "stopped" : resized.has(s.id) ? "resized" : "kept"} to={resized.get(s.id)} />)}
      </div>
    </div>
  );
}

function ServerCard({ s, state, to }: { s: CloudServer; state: "deleted" | "stopped" | "resized" | "kept"; to?: CloudServer & { from_plan?: string } }) {
  const bad = state !== "kept" && s.production;
  return (
    <div className={cn("relative min-w-0 rounded-xl border p-3 text-xs transition",
      state === "kept" && "bg-background opacity-60",
      state !== "kept" && !bad && "border-foreground/30 bg-background",
      bad && "border-damage/50 bg-damage-soft/60")}>
      <div className="flex items-center gap-1.5">
        {s.production ? <Lock className="size-3 shrink-0" /> : <Server className="size-3 shrink-0 text-muted-foreground" />}
        <span className={cn("truncate font-mono text-[12px] font-medium", state === "deleted" && "line-through decoration-damage/70")}>{s.label}</span>
      </div>
      <div className="mt-1 truncate text-muted-foreground" title={s.purpose}>{s.purpose}</div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-x-2 font-mono text-[11px] tabular text-muted-foreground">
        <span className="whitespace-nowrap">{s.region} · {state === "resized" && to ? `${to.from_plan} → ${s.plan}` : s.plan}</span>
        <span className="whitespace-nowrap">{s.cpu_avg_7d != null ? `CPU ${s.cpu_avg_7d}%` : "CPU not reported"}</span>
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className={cn("rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider",
          state === "kept" ? "bg-muted text-muted-foreground" : bad ? "bg-damage text-white" : "bg-foreground text-background")}>
          {state === "kept" ? "unchanged" : state}
        </span>
        <span className="font-mono text-[11px] tabular">{usd(s.monthly_cost_cents)}/mo</span>
      </div>
    </div>
  );
}
