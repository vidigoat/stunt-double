import { cn } from "@/lib/utils";

/** A product shot framed as an app window, on a painterly, grainy backdrop (decorative frame, real screenshot inside). */
export function Showcase({ src, alt, title, tone = "blue", width, height, className, children }: {
  src?: string; alt?: string; title: string; tone?: "blue" | "warm" | "green"; width?: number; height?: number; className?: string; children?: React.ReactNode;
}) {
  return (
    <div className={cn("grain overflow-hidden rounded-[22px] p-4 sm:p-8", `backdrop-${tone}`, className)}>
      <div className="relative z-[2] overflow-hidden rounded-xl border border-black/10 bg-card shadow-[0_30px_60px_-30px_rgba(20,30,60,.45),0_8px_20px_-12px_rgba(20,30,60,.25)]">
        <div className="flex items-center gap-1.5 border-b bg-muted/60 px-3 py-2">
          <span className="size-2.5 rounded-full bg-black/15" /><span className="size-2.5 rounded-full bg-black/15" /><span className="size-2.5 rounded-full bg-black/15" />
          <span className="mx-auto pr-8 font-mono text-[11px] text-muted-foreground">{title}</span>
        </div>
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt={alt ?? title} width={width} height={height} loading="lazy" className="block h-auto w-full" />
        ) : children}
      </div>
    </div>
  );
}
