import Link from "next/link";
import { Mark } from "@/components/brand";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-4 text-center">
      <Mark className="size-12" />
      <div className="eyebrow mt-8 justify-center">404</div>
      <h1 className="mt-3 font-display text-5xl sm:text-6xl">This page <em>took the hit.</em></h1>
      <p className="mt-4 max-w-md text-[15px] leading-relaxed text-muted-foreground">Nothing real was harmed. The page you asked for doesn&apos;t exist.</p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link href="/app" className="inline-flex h-11 items-center rounded-full bg-foreground px-5 text-sm font-medium text-background hover:opacity-90">Open the console</Link>
        <Link href="/" className="inline-flex h-11 items-center rounded-full border px-5 text-sm hover:bg-accent">Home</Link>
      </div>
    </main>
  );
}
