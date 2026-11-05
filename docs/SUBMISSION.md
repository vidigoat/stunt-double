# lablab submission kit

Form: lablab.build/ai-hackathons/vultr-hackathon/dragon/submission, three steps. Step 1 "Basic Information" is below
(field limits as the form shows them). Steps 2 and 3 aren't visible until step 1 is filled; the official page lists
video presentation, slide presentation, cover image, application URL and a public GitHub repo, so those are below too.
Deadline: Mon Nov 9, about 04:30 IST (Sun Nov 8 23:00 UTC), from the live countdown. Prizes are overall (1st: $5,000 +
$3,000 Vultr credits), judged on Application of Technology, Presentation, Business Value, Originality.

## Step 1 · Submission Title (5–50 chars, this is 41)
```
Stunt Double: Let the Double Take the Hit
```

## Step 1 · Short Description (50–255 chars, this is 188)
```
Every AI agent now holds the keys to something real. Stunt Double lets it try every action on a perfect copy of your business first, on Vultr. Nothing real happens until a person says yes.
```

## Step 1 · Long Description (600–2000 chars and 100+ words, this is 1594 chars, 287 words)
```
In the movies, the star never jumps from the burning building. The stunt double does.

AI agents are becoming the stars of our businesses. They refund customers, send emails, click through admin pages and delete servers. They are fast, tireless and usually right. But when they are wrong, they are wrong with real money, real inboxes and real data. There is no second take.

Stunt Double gives every agent a double. Before any action touches the real world, it is rehearsed on a copy of the business, sealed inside a Vultr sandbox with no internet and no secrets. Then a second sandbox measures what truly changed, so the agent cannot hide a single thing.

Ask it to refund everyone who was charged twice. Before the agent writes a line, Stunt Double writes down what you meant: 104 refunds, and nothing else. The agent's plan refunds 744. A jury of three AI models from different labs agrees it is wrong. Stunt Double proves which line of the plan chose the 640 wrong people, cuts them out, and hands back exactly the 104. $32,268 saved, and every right customer still paid.

A person sees it all in plain words, not code. Only what they approve ever happens, and every decision is sealed in a signed record that breaks if anyone changes a single byte.

And it learns. Every mistake it catches becomes a rule, so the same mistake is stopped instantly next time, without asking the AI at all.

Built on Vultr from end to end. In live tests it caught 48 of 48 bad plans, with no false alarms.

Agents should be bold. Businesses should be safe. Now they can be both.

Let the double take the hit.
```

<details><summary>Backup: the earlier, more technical version</summary>

#### Submission Title (5–50 chars, this is 48)
```
Stunt Double: Rehearse AI Agent Actions on Vultr
```

#### Short Description (50–255 chars, this is 249)
```
AI agents now move money, email customers and manage servers. Stunt Double runs every agent action on a throwaway double of your business in a gVisor sandbox on Vultr first, shows the consequences, and changes production only after a human approves.
```

#### Long Description (600–2000 chars and 100+ words, this is 1947 chars, 329 words)
```
AI agents are starting to act on real systems: refunding customers, sending email, clicking through admin sites and deleting cloud servers. One wrong plan can do irreversible damage before anyone notices. Stunt Double makes every agent action a rehearsal first.

The plan runs on a double of the business (database, payments, email, any HTTP API, a real Chromium browser, and Vultr servers, including read-only doubles of your own Postgres database and Vultr fleet) inside a fresh gVisor sandbox on Vultr Cloud Compute with no network and no secrets. A second, trusted container measures what actually changed, so the plan can't lie about what it did. Policy rules check the blast radius, and an AI jury of three labs' models on Vultr Serverless Inference investigates the data independently with read-only SQL (and reads browser screenshots).

Humans approve consequences, not code: "refunds $37,404 to 744 people, 640 of whom were never double-charged." Approval replays exactly the recorded effects after a drift check. Big changes and every undo need two people, and each approval is bound to a SHA-256 of the plan and its effects.

Every catch becomes a rule: the AI writes the SQL check it used, Stunt Double proves it would not block work the AI judged correct, and one click makes it a rule that blocks the same mistake instantly, without AI. Every approval is the human-oversight and change record the EU AI Act (Art. 14) and SOC 2 (CC8.1) ask for. Measured on Vultr: $0.02–0.044 per AI jury check, 73% gross margin at $49 per approver; one caught mistake pays for a seat for decades.

On the live Vultr server it caught 48 of 48 bad plans with 0 false alarms on 26 correct ones. Agents connect over MCP, an SDK, a CLI or REST; there is no approve tool. Built on Vultr Cloud Compute, Serverless Inference and the Vultr API, with gVisor, FastAPI, Next.js and Playwright; 187 API tests and an end-to-end test that passes against production.
```


</details>

## Step 1 · Participation Mode
Online.

## Step 1 · Categories
Pick Challenge 01 / Blast Radius Zero if it is listed, plus anything like AI agents, security or developer tools.

## Step 1 · Technologies Used
Vultr · Vultr Cloud Compute · Vultr Serverless Inference · Vultr API · gVisor · Docker · Python · FastAPI · Next.js · Playwright · PostgreSQL ·
MCP · SQLite · GLM

## Links
- Application URL: https://149-28-206-186.sslip.io (judge mode: open /app, eight one-click steps; Mission control at /control)
- MCP endpoint: https://149-28-206-186.sslip.io/mcp
- Repo: https://github.com/vidigoat/stunt-double

## Files
- Slides PDF: being made by hand (the generated deck was removed)
- Cover (16:9): `presentation/cover.png`
- Video: required. The official page sets no length limit; Challenge 01 requires it to show at least one containment
  moment (judge step 2 does: sandbox 0, production 1,300, approval locked). Shot list: docs/DEMO_1MIN.md.

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
