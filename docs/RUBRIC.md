# Win rubric: how we score ourselves

lablab judges score **4 criteria, 1–5 each** (unweighted, max 20), after checking the challenge's hard requirements.
This rubric breaks each criterion into concrete checks so we can rate ourselves honestly and know what to build next.

Rating scale per check: **0** missing · **1** partial / untested · **2** done and verified.
Criterion score (1–5) = `1 + 4 × (points earned / points possible)`, rounded to one decimal.

---

## Gate: hard requirements (all must pass or we risk disqualification)

| # | Requirement (Challenge 01 + submission) | Status | Evidence |
|---|---|---|---|
| G1 | Vultr Cloud Compute VM backend | ✅ | vc2-2c-4gb in San Jose, provisioned by `infra/provision.py` (credit-guarded) |
| G2 | Web app hosted on Vultr, public URL | ✅ | https://149-28-206-186.sslip.io (10-step browser e2e passes against it) |
| G3 | Vultr Serverless Inference for the agent's LLM calls | ✅ | glm-5.3-flash agent + verifier (qwen3.8-flash-next fallback) on the live server; `docs/EVAL.md`, `docs/VERIFIER_EVAL.md` |
| G4 | Isolated sandbox per task (process isolation, no secrets, limits, destroyed) | ✅ gVisor on Vultr | `/api/health` → `sandbox_runtime: runsc`, `runsc ready` |
| G5 | Containment moment shown in the demo video | ✅ in app · ⏳ video | /app → Break it yourself |
| G6 | Public GitHub repo with setup docs | ✅ | README, CI green |
| G7 | Demo video (≤5 min), slide PDF, cover image, texts | ❌ | Day 4 |

---

## 1. Application of Technology

*"Judges check that the demo works, the repo has real commits across the event, and the AI does more than wrap a chatbot around a form."*

| Check | Pts now | Max | Notes |
|---|---|---|---|
| Agent really writes and executes code (not just chat) | 2 | 2 | Real agent on Vultr Inference investigates with SQL, writes Python plans, runs them in gVisor on the live server |
| Plan → dispatch → verify loop with self-correction | 2 | 2 | Live: the verifier caught an agent plan that missed 87 of 104 customers; fix flow + forced decisions tested |
| Verification uses real measured results, not model opinion | 2 | 2 | Row diffs, recorders, read-only investigation |
| Sandbox isolation is real and tested | 2 | 2 | 7 engine tests, containment in CI |
| gVisor runtime on Vultr | 2 | 2 | `runsc` live on the Vultr VM; every rehearsal runs in it |
| Uses Vultr meaningfully (VM + Inference + API) | 2 | 2 | VM (gVisor), Serverless Inference (agent + verifier), Vultr API for credit-guarded provisioning |
| Production-grade apply (drift check, idempotency, policy) | 2 | 2 | Tested |
| Engineering quality (tests, CI, commits across the event) | 2 | 2 | 60+ commits, 140 API tests + MCP client test + 11-step browser e2e, 4 CI jobs green |
| Defence in depth beyond the brief | 2 | 2 | Two-phase measurement (the plan can't lie), O_NOFOLLOW copies, ulimits, integrity hash, policy engine, 6 adversarial tests |
| Works with any agent | 2 | 2 | MCP server (stdio + HTTP), tested with a real MCP client in CI; Connect page in the app |
| Independent security review, all findings fixed with regression tests | 2 | 2 | Three rounds: 1 critical, 5 high, 11 medium, ~12 low; all fixed with tests (`test_security3.py` covers round 3); see SECURITY.md |
| Deployment proven before the VM exists | 2 | 2 | Full compose stack (Caddy HTTPS, web, api, mcp, Mailpit) run end to end; browser e2e passes over HTTPS; 104 emails delivered |
| **Total** | **24** | **24** | **→ 5.0 / 5** |

## 2. Presentation

*"Clarity over production value. If a judge can't grasp the value from the opening screen, you've already lost points."*

| Check | Pts now | Max | Notes |
|---|---|---|---|
| Value obvious in 30 s (first screen) | 2 | 2 | Hero shows "$37,404 → 744, 640 never double-charged" |
| Polished, coherent visual design | 2 | 2 | Landing + console + ledger, black-and-white system |
| Public live URL judges can use | 2 | 2 | https://149-28-206-186.sslip.io |
| Judges can trigger the wow moment themselves | 2 | 2 | Judge mode on the live site: four one-click rehearsals, live AI investigation stream |
| Demo video, 4–5 min, golden path rehearsed | 1 | 2 | 30 s recorded demo (GIF/MP4) in README; narrated 4-min video still Day 4 |
| Slide deck (8–10 slides) | 2 | 2 | `presentation/stunt-double-deck.pdf`, 10 slides |
| Cover image + lablab texts | 2 | 2 | `presentation/cover.png`, `docs/SUBMISSION.md` (lengths checked) |
| **Total** | **13** | **14** | **→ 4.6 / 5** |

## 3. Business Value

*"A specific target user, a rough TAM, at least one revenue model, and why AI is essential."*

| Check | Pts now | Max | Notes |
|---|---|---|---|
| Named buyer and painful problem | 2 | 2 | Landing "Who it's for", PITCH.md, deck slide 8 |
| Market size with sources | 2 | 2 | $7.6B → $50B (2025→2030), Gartner adoption stats, sourced in PITCH.md |
| Revenue model | 2 | 2 | Pricing section on landing + deck |
| Why AI is essential (not a rules engine) | 2 | 2 | Deck slide 7 table; verifier still to prove live |
| Credible demo scenario with real numbers | 2 | 2 | Seeded trap with real measured numbers |
| Fit with the listed business areas (finance, support, sales ops) | 2 | 2 | Five traps: finance (refunds), support (ticket inbox), marketing/sales (consent), operations in a browser (subscriptions), IT/cloud (Vultr fleet) |
| **Total** | **12** | **12** | **→ 5.0 / 5** |

## 4. Originality

*"A fresh angle that only became practical with current AI, not an existing product plus a chatbot."*

| Check | Pts now | Max | Notes |
|---|---|---|---|
| Distinct from the organizers' example list | 2 | 2 | Not in the list of 10 example directions |
| Distinct from existing products | 2 | 2 | Consequences for non-technical approvers + trusted two-phase measurement + replay of approved effects; no tool found doing this |
| Memorable concept and name | 2 | 2 | "Let the double take the hit" |
| Novel mechanism (approve recorded effects, replay with drift check) | 2 | 2 | Agent code never touches prod |
| **Total** | **8** | **8** | **→ 5.0 / 5** |

---

## Scorecard

| Criterion | Now (Tue night) | Target (Sun) |
|---|---|---|
| Application of Technology | 3.5 → 3.8 → 3.9 → 4.0 → **5.0** | 5.0 |
| Presentation | 2.4 → 3.6 → 3.9 → **4.6** | 5.0 |
| Business Value | 2.7 → 4.7 → **5.0** | 5.0 |
| Originality | 4.5 → **5.0** | 5.0 |
| **Total (/20)** | 13.1 → 16.3 → 17.4 → 17.8 → 17.9 → **19.6** | 19.5 |
| Gate | ❌ (G7 video open) | ✅ |

**Biggest score movers, in order:**
1. Keys → VM live + real model runs (unlocks G1–G3, +1.5 Tech, +0.6 Presentation).
2. Business case written into the product and deck (buyer, TAM, pricing, why AI) (+1.5 Business).
3. Video + deck + cover (+1.7 Presentation).
4. gVisor verified on Vultr (+0.5 Tech).

Re-score after every milestone and log it below.

## Score log
| When (IST) | Total | Change |
|---|---|---|
| Tue Nov 3, 22:45 | 13.1 | First rating. Engine, tests, CI, landing and console done; nothing on Vultr yet. |
| Tue Nov 3, 23:30 | 16.3 | Pitch, pricing + buyer on landing, 10-slide deck, cover, submission texts, video script. Still blocked on Vultr keys (gate G1–G3). |
| Wed Nov 4, 07:15 | 17.4 | Agent robustness, policy engine, two-phase sandbox + adversarial tests, audit trail + SSE, MCP server, browser e2e in CI, README media, 11-slide deck. Gate G1–G3 still needs keys. |
| Wed Nov 4, 19:25 | 17.9 | Platform depth: HTTP connectors (Slack, CRM) with server-side credentials, rehearsed undo, two-person rule, bring-your-own SQLite, policy simulator, every-row diff explorer, Python SDK + CLI, decision notes, CSV audit export, rehearsal expiry; security review 3 fixed. The score doesn't move: every remaining point needs the Vultr VM, real inference or the video. |
| Wed Nov 4, 23:45 | 19.6 | Live on Vultr: VM with gVisor, real agent + verifier on Serverless Inference, judge mode, live AI stream. Eval on the live server: 36/36 bad plans caught, 0/18 false alarms. Remaining point: the video. |

## Before submitting: claims to re-verify against live runs
- [x] Deck and landing hero: the verifier headline is now a real live output ("Plan refunds 640 customers who were never double-charged", 9/9 runs)
- [ ] Deck slide 7: VIP and crash rows reflect real verifier behaviour
- [x] "gVisor (runsc)" everywhere: confirmed by `/api/health` → `sandbox_runtime: runsc` on the Vultr VM
- [ ] Model names on slides match production (glm-5.3-flash agent + verifier, qwen3.8-flash-next fallback)
- [x] `docs/EVAL.md` + `docs/VERIFIER_EVAL.md` exist with real numbers from the live server; quote only those
- [ ] `docs/BENCH.md` re-measured on the VM with gVisor
- [ ] Object Storage archive: `/api/health` shows `evidence_archive` and an approved run has an `archive.key` (only then mention it)
| Wed Nov 4, 07:55 | 17.8 | Three traps (finance/support/marketing), glossary-aware verifier, Checks tab, named approvals + evidence export, Connect page, guided tour, spend protection, Object Storage archive (untested), full compose stack verified over HTTPS. Gate G1–G3 still needs keys. |
| Wed Nov 4, 08:15 | 17.9 | Independent security review: 1 critical + 3 high + 3 medium fixed with 10 regression tests (42 API tests total). Remaining points are all behind the Vultr keys: live URL, real AI runs, gVisor, narrated video. |
| Wed Nov 4, 08:30 | 17.9 | Second security review round fixed (46 API tests), proof strip + honest hero caption, 12-slide deck, 2:34 video preview built. Next points need the keys (gate G1–G3). |
