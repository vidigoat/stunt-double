import {
  siAnthropic, siClaude, siCursor, siDocker, siFastapi, siGithub, siModelcontextprotocol, siNextdotjs, siPython, siSlack, siSqlite, siVultr,
  type SimpleIcon,
} from "simple-icons";
import { cn } from "@/lib/utils";

/** Official brand marks from Simple Icons (CC0 paths; trademarks belong to their owners). */
export const LOGOS = {
  vultr: siVultr, slack: siSlack, python: siPython, claude: siClaude, anthropic: siAnthropic, cursor: siCursor,
  sqlite: siSqlite, docker: siDocker, nextjs: siNextdotjs, mcp: siModelcontextprotocol, github: siGithub, fastapi: siFastapi,
} satisfies Record<string, SimpleIcon>;
export type LogoName = keyof typeof LOGOS;

/** `tone="brand"` uses the brand's own color; `mono` follows the text color (dark-mode safe for near-black marks). */
export function BrandLogo({ name, className, tone = "mono", title }: { name: LogoName; className?: string; tone?: "brand" | "mono"; title?: string }) {
  const icon = LOGOS[name];
  const dark = ["000000", "191919", "181717"].includes(icon.hex);
  return (
    <svg role="img" viewBox="0 0 24 24" aria-label={title ?? icon.title} className={cn("size-5 shrink-0", className)}
      fill={tone === "brand" && !dark ? `#${icon.hex}` : "currentColor"}>
      <path d={icon.path} />
    </svg>
  );
}

const STRIP: { name: LogoName; label: string }[] = [
  { name: "vultr", label: "Vultr" }, { name: "claude", label: "Claude Code" }, { name: "cursor", label: "Cursor" },
  { name: "mcp", label: "MCP" }, { name: "python", label: "Python" }, { name: "slack", label: "Slack" },
  { name: "sqlite", label: "SQLite" }, { name: "docker", label: "Docker" },
];

/** "Works with" row: monochrome by default, each logo lights up in its brand color on hover. */
export function LogoStrip({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-wrap items-center justify-center gap-x-7 gap-y-3", className)}>
      {STRIP.map((l) => (
        <span key={l.name} className="group inline-flex items-center gap-2 text-muted-foreground transition-colors hover:text-foreground">
          <BrandLogo name={l.name} className="size-[18px] opacity-70 transition group-hover:hidden" />
          <BrandLogo name={l.name} tone="brand" className="hidden size-[18px] group-hover:block" />
          <span className="text-[13px] font-medium tracking-tight">{l.label}</span>
        </span>
      ))}
    </div>
  );
}
