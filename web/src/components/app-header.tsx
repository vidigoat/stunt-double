"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Wordmark } from "@/components/brand";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/app", label: "Console" },
  { href: "/history", label: "History" },
  { href: "/policy", label: "Policy" },
  { href: "/ledger", label: "Ledger" },
  { href: "/connect", label: "Connect" },
];

export function AppHeader({ right }: { right?: React.ReactNode }) {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-6">
          <Link href="/" aria-label="Stunt Double home" className="shrink-0"><Wordmark /></Link>
          <nav className="hidden items-center gap-1 text-sm md:flex">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className={cn("rounded-full px-3 py-1.5 text-muted-foreground hover:text-foreground", path === n.href && "bg-muted text-foreground")}>{n.label}</Link>
            ))}
            <a href="/mail/" target="_blank" rel="noreferrer" className="rounded-full px-3 py-1.5 text-muted-foreground hover:text-foreground">Inbox ↗</a>
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
