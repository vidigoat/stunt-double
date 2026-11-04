# Stunt Double: 5-day plan to win 1st place

**Event:** Vultr Agent Rush (lablab.ai) · Challenge 1: Blast Radius Zero
**Build window (IST):** Tue Nov 3, 21:30 → Mon Nov 9, 04:30 (official deadline, 5-minute grace)
**Our deadline:** **Sun Nov 8, 20:00 IST**. We submit early and spend the rest of the time on Q&A prep.

---

## 0. How we win #1 (the rubric, and what we do for each item)

Judges score 4 criteria, each 1–5, unweighted (lablab default). These are lablab's own "how to win" tips mapped to our moves:

| Criterion | What lablab says judges check | Our move |
|---|---|---|
| **Application of Technology** | The demo works. The repo has **real commits across the event**. The AI does more than wrap a chatbot around a form. | The agent writes code, runs it in a gVisor sandbox on a Vultr VM, reads the real result and fixes itself. Vultr Serverless Inference for every LLM call. Commit at least every few hours, with clear messages. |
| **Presentation** | Clarity over production value. Value obvious in **30 seconds** from the opening screen. | The first frame of the video and the landing page show **"$56,160 → 1,404 customers"** in red. One golden path, rehearsed. |
| **Business Value** | A named target user, a rough TAM, at least one revenue model, and why AI is essential. | Buyer: heads of ops, finance and support who give AI agents refund, CRM or billing access. Revenue: usage (per rehearsal) plus per-approver seats. TAM: a sourced number added on Day 4. |
| **Originality** | A fresh angle that is only practical with current AI, not "existing product plus chatbot". | "Approve consequences, not code." We found no tool that runs the agent's plan on a copy of the data and explains the damage in plain English. |

**Challenge 1's own core idea:** "containment-first. The system should **plan, dispatch and verify** real executed work, not just describe what it would do." Stunt Double maps onto this one-to-one: the agent **plans**, the plan is **dispatched** to a gVisor sandbox, the real result is **verified** (diff, intent check, render check), and only then is it applied for real. Use these three words in the video and the README.

**Event-specific must-haves (Challenge 1 badges: Vultr VM backend · Web app on Vultr · Serverless Inference · Isolated sandbox):**
- Vultr Cloud Compute VM backend.
- Vultr Serverless Inference for the agent's LLM calls.
- Isolated sandbox: process isolation, **no secrets inside**, time and memory caps, destroyed after every task.
- A **containment moment** in the video.
- Public demo URL, public GitHub repo with setup docs, and a README explaining Vultr usage, architecture and use case.
- Video (≤5 min, MP4 under 300 MB), slide PDF, 16:9 cover image.
- Title 5–50 characters, short description 50–255, long description 600–2000.

**Edges most teams won't have:**
1. A **"Break it yourself"** box, so judges trigger the containment moment live.
2. The final apply step runs for real: refunds land in our own **BeanPay** payments service (its own ledger and dashboard on the VM) and emails arrive in a real **Mailpit** inbox. "Real executed results, not described ones", with no third-party accounts.
3. The prompt-injection containment moment. It's very topical (the 2026 skill and MCP attacks).
4. A polished landing page that looks like a funded startup.
5. Submit a day early and stay in the Discord. Answer questions and help others; mentors notice.

**Biggest open risk:** the in-person day (Nov 8, Salt Lake City). **Ask in the lablab Discord on Day 1** whether remote teams can place.

---

## 1. Architecture (one Vultr VM)

```
Browser ──HTTPS──► Caddy (VM) ──► web: Next.js 15 + React + shadcn/ui (landing + /app)
                                   └─► api: FastAPI (Python) orchestrator
                                          ├─ Agent loop ─────► Vultr Serverless Inference (OpenAI-compatible)
                                          │                      • glm-5.3: plan + code + self-fix (tool calling)
                                          │                      • qwen3.8-flash-next: email render check (vision), summaries
                                          ├─ Rehearsal runner ─► docker run --runtime=runsc (gVisor)
                                          │                      --network none --read-only --memory 256m
                                          │                      --pids-limit 64 --cap-drop ALL, empty env, 60s timeout
                                          │                      inside: Postgres restored from a snapshot of prod,
                                          │                      plan runs; payments/emails → recorders (JSON out)
                                          │                      → diff → consequences.json → container destroyed
                                          ├─ Apply (after approval + drift check) ─► prod Postgres,
                                          │                      BeanPay (our payments service + ledger UI), Mailpit (real SMTP inbox)
                                          └─ Audit log (who approved which plan hash, when)
prod: Postgres 16 "Bean There Coffee Co." (customers, charges, tickets, subscriptions)
```

**Rules:**
- Secrets live only in the API container. A sandbox never gets an API key.
- Anything the sandbox tries outside the recorders fails, because there's no network. It is reported as "unknown side effect, blocked".
- One fake business only. Don't generalise.

---

## 2. Day-by-day (IST)

### Day 0: Tue Nov 3, 21:30 → ~01:00. Setup and skeleton
- [ ] **You:** create a Vultr account with a fresh email, redeem the $200 hackathon credit, and create an API key for **Serverless Inference** and one for the **Vultr API**.
- [ ] **You:** create an empty **public** GitHub repo `vidigoat/stunt-double` on github.com. I'll attach it to this session and push.
- [ ] **Me:** provision the VM (Ubuntu 24.04, 4 vCPU / 8 GB) through the Vultr API. Install Docker, gVisor and Caddy. Point a domain or `sslip.io` hostname at it.
- [ ] **Me:** scaffold the monorepo (`web/` Next.js and shadcn, `api/` FastAPI, `sandbox/` image, `infra/` compose and Caddy). First commit.
- [ ] **Me:** a "hello" agent call to Vultr Inference with tool calling, and the first sandbox run on the VM with `runsc`.
- [ ] **You:** post in the lablab Discord asking whether remote teams can win and whether we must be on site. Find a teammate if you want one for the video voice-over and slides (optional).

### Day 1: Wed Nov 4. The core loop end to end (clickable by hour 24)
- [ ] Seed "Bean There Coffee Co.": about 1,300 customers, about 1,400 charges with 104 real duplicates, VIP flags, about 50 support tickets (one poisoned).
- [ ] Rehearsal runner: snapshot → sandbox → run plan → row diff, recorded payments and emails → `consequences.json` → destroy.
- [ ] Agent loop: tools `inspect_schema`, `propose_plan(code)`, `rehearse(plan)`, `explain(consequences)`. Self-fix on rule mismatch.
- [ ] A basic `/app`: ask → rehearse → numbers. Ugly is fine.
- [ ] Deploy to the VM at a public URL. **The deployed version works end to end by tonight.**

### Day 2: Thu Nov 5. Make the golden path great
- [ ] The consequences screen (hero): big numbers, plain-English summary, mismatch alert, tabs for Rows, Emails, Calls and Code.
- [ ] The fix flow: before/after animation $56,160 → $4,160.
- [ ] The **containment moment**: poisoned ticket, then the split-screen counters, guard badges and shatter.
- [ ] BeanPay: a tiny payments service (FastAPI + its own DB + ledger page) that the business "uses". The sandbox gets a recorder in its place.
- [ ] Apply: drift check, then real BeanPay refunds and Mailpit emails, receipt and audit log.
- [ ] Email render check with the vision model (catches `Hi {{first_name}}`).

### Day 3: Fri Nov 6. Landing page, polish, "Break it yourself"
- [ ] Landing page per `DESIGN.md`. The hero uses the real approval-screen component, not a screenshot.
- [ ] Brand: logo mark, full favicon set, OG and cover image.
- [ ] "Break it yourself" box (rate-limited), plus a reset-demo button.
- [ ] Mobile pass, empty, loading and error states, and a 404.
- [ ] README: architecture diagram, Vultr services used, the containment model, setup steps, screenshots.

### Day 4: Sat Nov 7. Record (early!) and package
- [ ] **Feature freeze at 14:00.** Bugs on the golden path only.
- [ ] Video, about 4 minutes, following lablab's structure:
  - 0:00–0:20 hook: the $56,160 screen, then the Replit story in one line.
  - 0:20–2:30 live demo: ask → rehearse → caught → fix → containment moment → apply for real.
  - 2:30–3:30 business: buyer, why AI is essential, revenue model, market.
  - 3:30–4:00 architecture on Vultr and what's next.
- [ ] Slides (8–10, black and white, same fonts): problem · solution · demo · how it works · containment · Vultr architecture · business · roadmap · team.
- [ ] lablab texts: title, short description, long description, tags, cover.

### Day 5: Sun Nov 8. Buffer and submit
- [ ] Re-record anything weak. Final README pass. Check every link from an incognito window.
- [ ] **Submit by 20:00 IST**, then keep the demo URL up and monitored through judging.
- [ ] Prep judge Q&A (below). Share the project on the Vultr Community (optional bonus visibility).

---

## 3. Judge Q&A cheat sheet
- **"Why not staging plus a transaction?"** Staging data is stale or fake, and a transaction can't un-send an email or un-refund money. Approvers can't read SQL. We show consequences.
- **"What about side effects you didn't mock?"** The sandbox has no network, so unknown calls fail and are flagged as "unknown side effect, blocked". It fails closed.
- **"Isn't real customer data inside the sandbox risky?"** It's isolated (gVisor, no network, no secrets) and destroyed after every run. PII masking is on the roadmap.
- **"Does it scale to big databases?"** In production we'd use Vultr Managed Postgres *fork* (point-in-time clone) or copy-on-write branches, and rehearse on a sample plus exact counts.
- **"Why is AI essential?"** The agent writes the plan, reads the real diff, notices the result doesn't match the human's intent, and fixes itself. Then it explains the impact in plain English.

---

## 4. Already proven before kickoff (prototype in the session scratchpad, not in the repo)
- Buggy plan caught: $56,160 to 1,404 customers versus the correct $4,160 to 104. Prod byte-identical.
- Sandbox: no network, read-only root, 256 MB cap (kills a 600 MB grab), empty env, 0.32 s per create/run/destroy.
- Drift check: re-rehearses only when affected rows change.
- Vultr Inference endpoint live (OpenAI-compatible, tool calling documented).

## 5. What I need from you to start at 21:30
1. **Vultr API key** and **Serverless Inference API key**, added in the cloud environment settings as `VULTR_API_KEY` and `VULTR_INFERENCE_KEY`. Never paste them in chat.
2. An empty **public** repo `vidigoat/stunt-double`. Create it on github.com (this session can't create repos), and I'll attach it.
4. Optional: a domain. Otherwise we use a free `sslip.io` hostname.

## Progress (Wed Nov 4, 08:15 IST)
Ahead of plan on everything that doesn't need Vultr keys:
- Day 0–3 scope done: engine, two-phase sandbox, policy, verifier/agent (wiring tested), approval console, history/ledger/policy/connect pages,
  landing page, MCP server, deck (12 slides), cover, submission texts, video pipeline, README media, 42 API tests + MCP + browser e2e in CI.
- Full production compose stack verified end to end over HTTPS (Caddy, web, api, mcp, Mailpit).
- Blocked on keys: VM, real model runs + eval, gVisor benchmark, narration, final video. Follow docs/GO_LIVE.md.
