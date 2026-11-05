"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Copy } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { BrandLogo, type LogoName } from "@/components/brand-logos";

function Snippet({ title, body, code, logos = [] }: { title: string; body: string; code: string; logos?: LogoName[] }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="rounded-2xl border bg-card p-5">
      <div className="flex items-center gap-2.5 font-medium">
        {logos.map((l) => <span key={l} className="flex size-8 items-center justify-center rounded-lg border bg-background"><BrandLogo name={l} tone="brand" className="size-4" /></span>)}
        {title}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">{body}</p>
      <div className="relative mt-3">
        <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-xl bg-foreground p-4 pr-12 font-mono text-[13px] leading-relaxed text-background">{code}</pre>
        <button aria-label="Copy" onClick={async () => { try { await navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { toast.error("Couldn't copy"); } }}
          className="absolute right-2 top-2 rounded-lg p-2 text-background/70 hover:bg-background/10 hover:text-background">{copied ? <Check className="size-4" /> : <Copy className="size-4" />}</button>
      </div>
    </div>
  );
}

export default function ConnectPage() {
  const [origin, setOrigin] = useState("https://<your-host>");
  useEffect(() => setOrigin(window.location.origin), []);
  const mcp = `${origin}/mcp`;
  return (
    <div className="min-h-dvh">
      <AppHeader />
      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <div className="eyebrow">Connect an agent</div>
        <h1 className="mt-2 font-display text-5xl">Rehearse <em>before</em> it acts.</h1>
        <p className="mt-3 max-w-xl text-muted-foreground">Any MCP client can call Stunt Double. The agent gets the measured consequences, the engine&apos;s decision and a link for a human. It can never approve its own plan: there is no approve tool.</p>
        <div className="mt-8 space-y-4">
          <Snippet logos={["claude"]} title="Claude Code" body="Adds this deployment as an MCP server over streamable HTTP." code={`claude mcp add --transport http stunt-double ${mcp}`} />
          <Snippet logos={["cursor", "mcp"]} title="Cursor, Windsurf and other MCP clients" body="Add this to the client's MCP configuration (mcp.json)." code={JSON.stringify({ mcpServers: { "stunt-double": { url: mcp } } }, null, 2)} />
          <Snippet logos={["anthropic"]} title="Tell your agent how to use it" body="A line for the agent's system prompt or CLAUDE.md." code={"Before you write a plan, call the stunt-double `what_does_this_mean` tool to see the promises it must keep.\nBefore changing business data, issuing refunds or sending emails, call the stunt-double `rehearse` tool with your plan.\nIf it reports blocking flags or a verdict other than looks_right, fix the plan and rehearse again.\nIf its decision is cut, call keep_only_what_is_right to re-rehearse just the part that is right.\nNever say a change was applied until get_run_status reports status == 'applied'."} />
          <Snippet logos={["fastapi"]} title="Plain HTTP" body="No MCP? The same thing over the REST API." code={`curl -s ${origin}/api/runs/manual \\\n  -H 'content-type: application/json' \\\n  -d '{"task": "Refund double charges", "code": "def run(ctx):\\n    ..."}'\n# then poll ${origin}/api/runs/<id>  ·  API docs: ${origin}/api/docs`} />
        </div>
        <div className="mt-8 rounded-2xl border bg-card p-5">
          <div className="font-medium">Tools</div>
          <ul className="mt-3 space-y-2 font-mono text-[13px]">
            <li><span className="text-foreground">describe_business()</span> <span className="text-muted-foreground">: tables, columns and the plan API</span></li>
            <li><span className="text-foreground">rehearse(task, plan_code)</span> <span className="text-muted-foreground">: consequences, policy flags, verdict, approval_url</span></li>
            <li><span className="text-foreground">get_run_status(run_id)</span> <span className="text-muted-foreground">: awaiting approval, applied, rejected or drifted</span></li>
          </ul>
        </div>
      </main>
    </div>
  );
}
