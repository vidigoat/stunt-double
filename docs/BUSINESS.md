# The business case

Every number here is measured on the live Vultr deployment or taken from the Vultr API; nothing is projected from
assumptions we can't show.

## Who buys, and why now

**Buyer:** the person who signs off on what AI agents do: Heads of Operations, Support and Finance Ops at mid-market SaaS
and e-commerce companies that are giving agents write access to customer data, payments and email. **User:** the platform
engineer who wires the agent in (one MCP line, three lines of Python, or REST).

**Why now:**
- Agents have started acting, not just answering: refunds, customer email, admin-site clicks, cloud cleanups. The failure
  mode is no longer a wrong answer, it's an irreversible action (in July 2025 an AI agent deleted a company's production
  database during a code freeze).
- **Compliance asks for exactly this.** The EU AI Act requires effective human oversight for high-risk AI systems
  (Article 14) and automatic record-keeping of their operation (Article 12). SOC 2 asks that changes be authorized, tested
  and approved before they reach production (CC8.1, change management). Stunt Double produces that record for every agent
  action: what was tested (the rehearsal and its measured consequences), who approved it and why, and a SHA-256 fingerprint
  binding the approval to exactly what was applied, exportable as JSON evidence or a CSV audit trail.

## What a mistake costs, and what we cost

One caught plan in the demo, refunding 640 customers who were never double-charged, is **$32,268** of money out plus 640
wrong apology emails. A Team seat is $49 a month: **that single catch pays for the seat for almost 55 years.**

## Unit economics (measured)

| Cost | Measured | How |
|---|---|---|
| A rehearsal (two gVisor sandboxes) | **≈ $0.00003** | median 1.81 s on the $20/month vc2-2c-4gb VM ([BENCH.md](BENCH.md)); at only 25% utilization that VM runs ≈ 700,000 rehearsals a month |
| An AI jury check (3 models, each investigating the data) | **$0.020–$0.044** | real token usage of three checks on the demo traps (66k–134k input, 12k–40k output tokens across GLM, DeepSeek and MiniMax) × the per-token prices the Vultr API reports for this subscription |
| A repeated identical check | **$0** | the earlier live verdict is reused for identical request, effects, data, policy and models (labelled) |
| A repeated mistake | **$0 in AI** | a learned rule blocks it deterministically inside the sandbox |
| All the AI this project has used so far | **$1.95** | every eval, jury check and judge run on Vultr Serverless Inference this month, from the Vultr usage API (total Vultr charges including the VM: $2.58) |

**Pricing**

| Plan | Price | Includes |
|---|---|---|
| Free | $0 | self-host on your own Vultr account (MIT, one command), 200 rehearsals and 20 AI jury checks a month on our cloud |
| Team | $49 per approver per month | 2,000 rehearsals and 300 AI jury checks; then $0.005 per rehearsal and $0.10 per AI jury check |
| Enterprise | annual | SSO, audit export, dedicated Vultr sandboxes (a VM per rehearsal), policy packs |

**Gross margin:** a Team seat used to its full allowance costs us 2,000 × $0.00003 + 300 × $0.044 ≈ **$13.26**, so
**73% gross margin at full use** (higher in practice, because reused checks and learned rules cost nothing). Overage is
priced above measured cost: rehearsals ≈ 99% margin, jury checks ≥ 56%.

The product gets cheaper to run the more a team uses it: every catch that becomes a rule, and every identical re-check,
removes an AI call for good.

## Distribution

- **Open core, bottom-up:** MIT-licensed; `python3 infra/provision.py` deploys the whole stack on the team's own Vultr
  account in one command. Teams that want the hosted jury, SSO and audit export upgrade.
- **Inside the tools agents already use:** one line adds Stunt Double to Claude Code (`claude mcp add ...`), an MCP JSON
  entry to Cursor and other clients, three lines to Python agents. There is no approve tool: the agent rehearses, a human
  decides.
- **Works on the team's real systems on day one:** a read-only double of their PostgreSQL database (approved changes
  leave as drift-guarded SQL for their own pipeline), a read-only double of their Vultr fleet, any HTTP API through
  connectors, and a real browser for admin sites.

## Why we win against the alternatives

| Alternative | What it misses |
|---|---|
| Staging environments | stale or fake data; the damage depends on real data; can't un-send an email |
| Database transactions / dry runs | only the database; nothing about money, email, APIs or browsers; the approver still reads code |
| Agent sandboxes (code isolation) | contain the code, but don't measure business consequences or check them against what was asked |
| Policy engines / allow-lists | catch the obvious; miss "refunds 640 people who were never double-charged", which is a perfectly valid call |
| Human review of agent code | reviewers can't read SQL; consequences in dollars and people are what they can judge |

The moat compounds: every catch becomes a rule the business owns, so a team's Stunt Double gets stricter, faster and
cheaper the longer they use it.
