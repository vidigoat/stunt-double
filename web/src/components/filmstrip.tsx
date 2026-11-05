import { MousePointerClick, Search, Globe, Eye } from "lucide-react";

export type BrowserStep = { n: number; action: string; target: string; url: string; shot: string | null };

const ICON: Record<string, typeof Globe> = { open: Globe, search: Search, click: MousePointerClick, look: Eye };

/** What the agent did on screen, step by step: real screenshots from the Chromium inside the sandbox. */
export function Filmstrip({ runId, attempt, steps, verdict }: { runId: string; attempt: number; steps: BrowserStep[]; verdict?: string | null }) {
  const shots = steps.filter((s) => s.shot);
  if (!shots.length) return null;
  return (
    <div className="animate-rise overflow-hidden rounded-2xl border bg-foreground text-background">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 pt-4">
        <span className="relative flex size-2"><span className="relative inline-flex size-2 rounded-full bg-signal" /></span>
        <div className="text-sm font-medium">The agent in a browser · the double of your admin site</div>
        <div className="ml-auto font-mono text-[11px] opacity-60">{shots.length} screens · real Chromium in the sandbox · no network</div>
      </div>
      {verdict ? <p className="px-5 pt-2 text-sm opacity-80">AI vision check: <span className="font-medium opacity-100">{verdict}</span></p> : null}
      <div className="mt-4 grid gap-4 px-5 pb-5">
        {(() => {
          const last = shots[shots.length - 1];
          const Icon = ICON[last.action] ?? Eye;
          return (
            <a href={`/api/runs/${runId}/shots/${last.n}.png?attempt=${attempt}`} target="_blank" rel="noreferrer" className="min-w-0">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/api/runs/${runId}/shots/${last.n}.png?attempt=${attempt}`} alt={`Final screen: ${last.action} ${last.target}`}
                   className="mx-auto w-full max-w-[640px] rounded-lg border border-white/10 bg-white ring-2 ring-signal/60" />
              <div className="mt-2 flex items-center gap-1.5 font-mono text-[11px] opacity-80">
                <span className="opacity-60">final screen · step {last.n}</span><Icon className="size-3" /><span>{last.action}</span><span className="truncate opacity-60">{last.target}</span>
              </div>
            </a>
          );
        })()}
        <ol className="flex gap-3 overflow-x-auto">
          {shots.map((s) => {
            const Icon = ICON[s.action] ?? Eye;
            return (
              <li key={s.n} className="w-[180px] shrink-0">
                <a href={`/api/runs/${runId}/shots/${s.n}.png?attempt=${attempt}`} target="_blank" rel="noreferrer" className="group block">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={`/api/runs/${runId}/shots/${s.n}.png?attempt=${attempt}`} alt={`Step ${s.n}: ${s.action} ${s.target}`} loading="lazy"
                       className="w-full rounded-md border border-white/10 bg-white transition group-hover:border-white/40" />
                  <div className="mt-1 flex items-center gap-1 font-mono text-[10px] opacity-75"><span className="opacity-60">{s.n}</span><Icon className="size-3" />
                    <span className="truncate">{s.action} {s.target}</span></div>
                </a>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
