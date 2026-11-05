# lablab submission kit

Form: lablab.build/ai-hackathons/vultr-hackathon/dragon/submission, three steps. Step 1 "Basic Information" is below
(field limits as the form shows them). Steps 2 and 3 aren't visible until step 1 is filled; the official page lists
video presentation, slide presentation, cover image, application URL and a public GitHub repo, so those are below too.
Deadline: Mon Nov 9, about 04:30 IST (Sun Nov 8 23:00 UTC), from the live countdown. Prizes are overall (1st: $5,000 +
$3,000 Vultr credits), judged on Application of Technology, Presentation, Business Value, Originality.

## Step 1 · Submission Title (5–50 chars, this is 48)
```
Stunt Double: Rehearse AI Agent Actions on Vultr
```

## Step 1 · Short Description (50–255 chars, this is 249)
```
AI agents now move money, email customers and manage servers. Stunt Double runs every agent action on a throwaway double of your business in a gVisor sandbox on Vultr first, shows the consequences, and changes production only after a human approves.
```

## Step 1 · Long Description (600–2000 chars and 100+ words, this is 1688 chars, 282 words)
```
AI agents are starting to act on real systems: refunding customers, sending email, clicking through admin sites and deleting cloud servers. One wrong plan can do irreversible damage before anyone notices. Stunt Double makes every agent action a rehearsal first.

The plan runs on a double of the business (database, payments, email, any HTTP API, a real Chromium browser, and Vultr servers, including read-only doubles of your own Postgres database and Vultr fleet) inside a fresh gVisor sandbox on Vultr Cloud Compute with no network and no secrets. A second, trusted container measures what actually changed, so the plan can't lie about what it did. Policy rules check the blast radius, and an AI verifier on Vultr Serverless Inference investigates the data with read-only SQL and reads browser screenshots.

Humans approve consequences, not code: "refunds $37,404 to 744 people, 640 of whom were never double-charged." Approval replays exactly the recorded effects after a drift check. Big changes and every undo need two people, and each approval is bound to a SHA-256 of the plan and its effects.

Every catch becomes a rule: the AI writes the SQL check it used, and one click makes it a rule that blocks the same mistake instantly, without AI. Small, clean, AI-confirmed changes can apply on their own within a budget.

On the live Vultr server it caught 48 of 48 bad plans with 0 false alarms on 26 correct ones. Agents connect over MCP, a Python SDK, a CLI or REST, and there is no approve tool. Built on Vultr Cloud Compute, Serverless Inference and the Vultr API, with gVisor, FastAPI, Next.js and Playwright; 132 API tests and an end-to-end test that passes against production.
```

## Step 1 · Participation Mode
Online.

## Step 1 · Categories
Pick Challenge 01 / Blast Radius Zero if it is listed, plus anything like AI agents, security or developer tools.

## Step 1 · Technologies Used
Vultr · Vultr Cloud Compute · Vultr Serverless Inference · Vultr API · gVisor · Docker · Python · FastAPI · Next.js · Playwright · PostgreSQL ·
MCP · SQLite · GLM

## Links
- Application URL: https://149-28-206-186.sslip.io (judge mode: open /app, seven one-click steps; Mission control at /control)
- MCP endpoint: https://149-28-206-186.sslip.io/mcp
- Repo: https://github.com/vidigoat/stunt-double

## Files
- Slides PDF: `presentation/stunt-double-deck.pdf`
- Cover (16:9): `presentation/cover.png`
- Video: required. The official page sets no length limit; Challenge 01 requires it to show at least one containment
  moment (judge step 1 does: sandbox 0, production 1,300, approval locked). Shot list: docs/DEMO_1MIN.md.

---

## Optional longer cut (~4:00). The planned video is the 1-minute one in docs/DEMO_1MIN.md

**0:00–0:20 · Hook** (screen: approval card with the red $37,404)
> "This AI agent was about to refund thirty-seven thousand dollars to the wrong people. Nothing happened, because it was only a rehearsal. This is Stunt Double."

**0:20–0:45 · Problem** (deck slide 2)
> "AI agents don't just chat any more. They refund money, email customers and edit databases. Last year one deleted a company's production database during a code freeze. And today's approval step shows a manager code they can't read."

**0:45–2:30 · Live demo** (the /app console, golden path)
1. Production counters for Bean There Coffee Co. "1,300 customers, real-looking data."
2. Type: "Refund everyone who was double-charged last week and send them an apology email." Click **Rehearse it**.
3. Timeline: the agent reads the schema, writes the plan, dispatches it to a sandbox. "It runs on a clone in a gVisor sandbox on Vultr. No network, no secrets, destroyed afterwards."
4. Approval card: $37,404 → 744 customers. The verifier (real words): "Plan refunds 640 customers who were never double-charged." Show the Rows tab (two different order IDs).
5. Click **Ask the agent to fix it** → $5,136 → 104. Emails tab: the real email text.
6. **Approve and apply** → drift check passed, BeanPay ledger shows the refunds, the inbox shows delivered emails.
7. **Containment moment:** Break it yourself → "Delete every customer" → split screen: sandbox 0, production 1,300. Sandbox tab: network none, 0 env vars, blocked DNS. **Blocked by policy.** "The blast radius is zero."

**2:30–3:30 · Business** (slides 7–9)
> "Rules catch the obvious. The expensive mistakes are about meaning, and that's why the verifier is an AI that investigates real outcomes. Our buyers are ops, finance and support leads giving agents write access. The agents market is heading from about 7.6 to 50 billion dollars by 2030. We charge 49 dollars per approver plus usage per rehearsal."

**3:30–4:00 · Built on Vultr + close** (slides 6 and 10)
> "One Vultr VM, many disposable doubles, every model call on Vultr Serverless Inference. Next: connectors and an MCP server so any agent rehearses first. Stunt Double: let the double take the hit."

**Recording tips:** 1440×900 browser, 110% zoom, a clean profile with no bookmarks bar, reset the demo before each take, record the voice-over separately if needed. Re-record by Saturday 14:00 IST at the latest.
