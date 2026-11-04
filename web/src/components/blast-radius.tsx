import type { Consequences } from "@/lib/api";
import { num, usd } from "@/lib/api";
import { cn } from "@/lib/utils";

/** The blast radius of a rehearsal: how much of each table it touches, plus every side effect that leaves the building. */
export function BlastRadius({ c, className }: { c: Consequences; className?: string }) {
  const tables = Object.entries(c.tables);
  const side = [
    { k: "money out", v: usd(c.payments.total_cents), n: c.payments.count },
    { k: "emails", v: num(c.emails.count), n: c.emails.count },
    { k: "API calls", v: num(c.http?.count ?? 0), n: c.http?.count ?? 0 },
  ];
  const untouched = !tables.length && side.every((x) => !x.n);
  return (
    <div className={cn("rounded-2xl border bg-card p-5", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <div className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Blast radius</div>
        <div className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          <span className="flex items-center gap-1"><span className="size-2 rounded-sm bg-damage" />deleted</span>
          <span className="flex items-center gap-1"><span className="size-2 rounded-sm bg-foreground" />changed</span>
          <span className="flex items-center gap-1"><span className="size-2 rounded-sm bg-muted-foreground/40" />added</span>
        </div>
      </div>
      {untouched ? <p className="mt-3 text-sm text-muted-foreground">Nothing would change: no rows, no money, no messages.</p> : null}
      <div className="mt-4 space-y-3">
        {tables.map(([t, d]) => {
          const total = Math.max(d.rows_before, d.rows_after, 1);
          const pct = (x: number) => (x ? Math.max(0.8, (x / total) * 100) : 0);
          const touched = d.deleted + d.updated + d.inserted;
          return (
            <div key={t}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="font-mono">{t}{d.dropped ? " · dropped" : d.schema_changed ? " · columns altered" : ""}</span>
                <span className={cn("font-mono tabular", d.deleted / total > 0.05 || d.dropped ? "text-damage" : "text-muted-foreground")}>
                  {num(touched)} of {num(d.rows_before)} rows · {Math.round((touched / total) * 100)}%
                </span>
              </div>
              <div className="mt-1.5 flex h-2.5 w-full overflow-hidden rounded-full bg-muted" role="img" aria-label={`${t}: ${d.deleted} deleted, ${d.updated} changed, ${d.inserted} added`}>
                <span className="h-full bg-damage" style={{ width: `${d.dropped ? 100 : pct(d.deleted)}%` }} />
                <span className="h-full bg-foreground" style={{ width: `${pct(d.updated)}%` }} />
                <span className="h-full bg-muted-foreground/40" style={{ width: `${pct(d.inserted)}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2">
        {side.map((x) => (
          <div key={x.k} className={cn("rounded-lg border px-3 py-2", x.n ? "bg-background" : "bg-muted/40 text-muted-foreground")}>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{x.k}</div>
            <div className="font-mono text-sm tabular">{x.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
