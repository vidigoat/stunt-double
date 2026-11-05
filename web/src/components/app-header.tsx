"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Wordmark } from "@/components/brand";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/app", label: "Console" },
  { href: "/history", label: "History" },
  { href: "/policy", label: "Policy" },
  { href: "/ledger", label: "Outbox" },
  { href: "/control", label: "Mission control" },
  { href: "/connect", label: "Connect" },
];

function usePending() {
  const [n, setN] = useState(0);
  useEffect(() => {
    let stop = false;
    const load = () => fetch("/api/runs", { cache: "no-store" }).then((r) => r.json())
      .then((runs: { status: string; blocked: boolean }[]) => { if (!stop) setN(runs.filter((x) => x.status === "review" && !x.blocked).length); })
      .catch(() => {});
    load();
    const t = setInterval(load, 15000);
    return () => { stop = true; clearInterval(t); };
  }, []);
  return n;
}

export function AppHeader({ right }: { right?: React.ReactNode }) {
  const path = usePathname();
  const pending = usePending();
  return (
    <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-6">
          <Link href="/" aria-label="Stunt Double home" className="shrink-0"><Wordmark /></Link>
          <nav className="hidden items-center gap-0.5 text-sm md:flex">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1.5 text-muted-foreground hover:text-foreground", path === n.href && "bg-muted text-foreground")}>
                {n.label}{n.href === "/history" && pending ? <span className="rounded-full bg-foreground px-1.5 font-mono text-[10px] text-background" title={`${pending} waiting for approval`}>{pending}</span> : null}
              </Link>
            ))}
            <a href="/mail/" target="_blank" rel="noreferrer" className="whitespace-nowrap rounded-full px-3 py-1.5 text-muted-foreground hover:text-foreground">Inbox ↗</a>
          </nav>
        </div>
        <div className="flex items-center gap-2">{right}</div>
      </div>
      <nav className="flex gap-1 overflow-x-auto border-t px-4 py-1.5 text-sm md:hidden">
        {NAV.map((n) => (
          <Link key={n.href} href={n.href} className={cn("shrink-0 rounded-full px-3 py-1 text-muted-foreground", path === n.href && "bg-muted text-foreground")}>{n.label}</Link>
        ))}
      </nav>
    </header>
  );
}
