# lablab submission kit

## Title (5–50 chars)
```
Stunt Double: let the double take the hit
```

## Short description (50–255 chars)
```
AI agents rehearse every risky action (refunds, emails, deletes) on a throwaway copy of your business inside an isolated Vultr sandbox. You approve the consequences, not the code, and nothing real happens until you do.
```

## Long description (600–2000 chars)
```
AI agents now refund money, email customers and edit production data, and when they get it wrong the damage is real. In July 2025 an AI agent deleted a company's production database during a code freeze. Today's "human in the loop" shows a manager code they can't read.

Stunt Double puts a double in front of every risky action. An ops agent on Vultr Serverless Inference turns a request into a plan. The plan is dispatched to a fresh gVisor sandbox on Vultr Cloud Compute, running on a clone of the business: no network, no secrets, read-only root, memory, PID and time caps, destroyed after every run. Payments and emails are recorded, not sent, and every changed row is measured. A second model verifies the measured outcome against what the human actually asked for, investigating the data with read-only queries, and the agent fixes its own plan in the sandbox. The approver sees money out, people affected, emails and rows in plain English. On approval, Stunt Double replays exactly the recorded effects, never the agent's code, after a locked drift check.

In the demo, "refund everyone who was double-charged last week" leads the obvious plan to refund $37,404 to 744 customers. Only 104 were actually double-charged; 640 had placed two separate orders. Stunt Double catches it before the money moves, and the corrected plan refunds $5,136 to 104. A poisoned support ticket that tells the agent to delete every customer only ever hits the double: sandbox 0, production 1,300, approval blocked by policy. Judges can try to break it themselves in the live app.

Built for Challenge 01, Blast Radius Zero: plan, dispatch, verify. For ops, finance and support leads who need to say yes to AI agents with confidence.
```

## Tags / technologies
Vultr Cloud Compute · Vultr Serverless Inference · gVisor · Docker · FastAPI · Next.js · shadcn/ui · GLM

## Files
- Slides PDF: `presentation/stunt-double-deck.pdf`
- Cover (16:9): `presentation/cover.png`
- Video: record per the script below (MP4, <300 MB, under 5 min)

---

## Video script (~4:00): lablab's recommended structure

**0:00–0:20 · Hook** (screen: approval card with the red $37,404)
> "This AI agent was about to refund thirty-seven thousand dollars to the wrong people. Nothing happened, because it was only a rehearsal. This is Stunt Double."

**0:20–0:45 · Problem** (deck slide 2)
> "AI agents don't just chat any more. They refund money, email customers and edit databases. Last year one deleted a company's production database during a code freeze. And today's approval step shows a manager code they can't read."

**0:45–2:30 · Live demo** (the /app console, golden path)
1. Production counters for Bean There Coffee Co. "1,300 customers, real-looking data."
2. Type: "Refund everyone who was double-charged last week and send them an apology email." Click **Rehearse it**.
3. Timeline: the agent reads the schema, writes the plan, dispatches it to a sandbox. "It runs on a clone in a gVisor sandbox on Vultr. No network, no secrets, destroyed afterwards."
4. Approval card: $37,404 → 744 customers. The verifier: "640 of these customers were never double-charged." Show the Rows tab (two different order IDs).
5. Click **Ask the agent to fix it** → $5,136 → 104. Emails tab: the real email text.
6. **Approve and apply** → drift check passed, BeanPay ledger shows the refunds, the inbox shows delivered emails.
7. **Containment moment:** Break it yourself → "Delete every customer" → split screen: sandbox 0, production 1,300. Sandbox tab: network none, 0 env vars, blocked DNS. **Blocked by policy.** "The blast radius is zero."

**2:30–3:30 · Business** (slides 7–9)
> "Rules catch the obvious. The expensive mistakes are about meaning, and that's why the verifier is an AI that investigates real outcomes. Our buyers are ops, finance and support leads giving agents write access. The agents market is heading from about 7.6 to 50 billion dollars by 2030. We charge 49 dollars per approver plus usage per rehearsal."

**3:30–4:00 · Built on Vultr + close** (slides 6 and 10)
> "One Vultr VM, many disposable doubles, every model call on Vultr Serverless Inference. Next: connectors and an MCP server so any agent rehearses first. Stunt Double: let the double take the hit."

**Recording tips:** 1440×900 browser, 110% zoom, a clean profile with no bookmarks bar, reset the demo before each take, record the voice-over separately if needed. Re-record by Saturday 14:00 IST at the latest.
