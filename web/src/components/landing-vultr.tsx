import Link from "next/link";
import { BrandLogo } from "@/components/brand-logos";

const GITHUB = "https://github.com/vidigoat/stunt-double";

const SERVICES = [
  { name: "Cloud Compute", what: "Runs the app, the API, the MCP server and every rehearsal as two fresh gVisor sandboxes: one runs the plan, one measures it.",
    n: "1.8 s", k: "median rehearsal, sealed and offline" },
  { name: "Serverless Inference", what: "Four labs, five jobs. Qwen writes the contract, DeepSeek cross-checks it, and GLM, DeepSeek and MiniMax judge the outcome.",
    n: "3 of 3", k: "jurors caught every trap on production" },
  { name: "Object Storage", what: "Every sealed rehearsal and decision is archived with its SHA-256. Download any run's evidence straight from Vultr.",
    n: "Ed25519", k: "signed evidence, kept on the Archival tier" },
  { name: "Vultr API", what: "A read-only double of your own server fleet, and a brand-new VM for a risky rehearsal, destroyed when it's done.",
    n: "36.5 s", k: "to a fresh VM, gone 0.4 s after" },
];

/** The four Vultr services, each doing real work on every request. */
export function Vultr() {
  return (
    <section id="vultr" className="mx-auto max-w-6xl scroll-mt-20 px-4 pb-24 sm:px-6">
      <div className="card-hard overflow-hidden rounded-[22px] border bg-card">
        <div className="grain backdrop-blue px-6 pb-8 pt-9 sm:px-10 [&>*]:relative [&>*]:z-[2]">
          <div className="eyebrow">Built on Vultr</div>
          <h2 className="mt-3 max-w-3xl font-display text-4xl sm:text-5xl">One Vultr VM. Four AI labs. <em>A disposable double for every action.</em></h2>
          <p className="mt-4 max-w-2xl text-muted-foreground">Every rehearsal, every model call and every piece of evidence runs on Vultr. The whole build, every test and eval included, cost $8.64 of Vultr credit.</p>
        </div>
        <div className="grid gap-px border-t bg-border sm:grid-cols-2 lg:grid-cols-4">
          {SERVICES.map((s) => (
            <div key={s.name} className="flex flex-col bg-card p-6">
              <div className="flex items-center gap-2 font-medium"><BrandLogo name="vultr" tone="brand" className="size-4" />{s.name}</div>
              <p className="mt-3 flex-1 text-sm text-muted-foreground">{s.what}</p>
              <div className="mt-6 font-mono text-3xl tabular">{s.n}</div>
              <div className="mt-1 min-h-[2.5rem] text-[13px] text-muted-foreground">{s.k}</div>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t px-6 py-4 text-sm sm:px-10">
          <span className="font-mono text-[13px] text-muted-foreground">vc2-2c-4gb · Silicon Valley · gVisor (runsc) · Archival tier, sjc1</span>
          <span className="flex flex-wrap gap-x-5 gap-y-1">
            <a href={`${GITHUB}#6-built-on-vultr`} target="_blank" rel="noreferrer" className="text-signal hover:underline">The architecture ↗</a>
            <Link href="/control" className="text-signal hover:underline">Watch it live in Mission control →</Link>
          </span>
        </div>
      </div>
    </section>
  );
}
