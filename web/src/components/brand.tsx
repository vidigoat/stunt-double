import { siGithub } from "simple-icons";
import { cn } from "@/lib/utils";

export function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-6", className)} aria-hidden>
      <g fill="var(--signal-soft)" stroke="var(--signal)" strokeWidth="2"><circle cx="19" cy="9" r="4.5" /><path d="M12 29v-6a7 7 0 0 1 14 0v6z" /></g>
      <g fill="currentColor"><circle cx="12" cy="10" r="4.5" /><path d="M5 30v-6a7 7 0 0 1 14 0v6z" /></g>
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-foreground", className)}>
      <Mark />
      <span className="font-display text-[22px] leading-none">Stunt <em>Double</em></span>
    </span>
  );
}

export function GithubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={cn("size-4", className)} aria-hidden>
      <path d={siGithub.path} />
    </svg>
  );
}
