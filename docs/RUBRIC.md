# Win rubric: how we score ourselves

lablab judges score **4 criteria, 1–5 each** (unweighted, max 20), after checking the challenge's hard requirements.
This rubric breaks each criterion into concrete checks so we can rate ourselves honestly and know what to build next.

Rating scale per check: **0** missing · **1** partial / untested · **2** done and verified.
Criterion score (1–5) = `1 + 4 × (points earned / points possible)`, rounded to one decimal.

---

## Gate: hard requirements (all must pass or we risk disqualification)

| # | Requirement (Challenge 01 + submission) | Status | Evidence |
|---|---|---|---|
| G1 | Vultr Cloud Compute VM backend | ⏳ pending keys | `infra/provision.py`, `infra/setup-vultr.sh` written, not run |
| G2 | Web app hosted on Vultr, public URL | ⏳ pending keys | compose + Caddy + sslip.io ready |
| G3 | Vultr Serverless Inference for the agent's LLM calls | ⏳ pending keys | `api/app/agent.py`, wiring tested with a scripted model |
| G4 | Isolated sandbox per task (process isolation, no secrets, limits, destroyed) | ✅ (Docker) · ⏳ gVisor | `api/tests/test_engine.py::test_containment` |
| G5 | Containment moment shown in the demo video | ✅ in app · ⏳ video | /app → Break it yourself |
| G6 | Public GitHub repo with setup docs | ✅ | README, CI green |
| G7 | Demo video (≤5 min), slide PDF, cover image, texts | ❌ | Day 4 |

---

## 1. Application of Technology

*"Judges check that the demo works, the repo has real commits across the event, and the AI does more than wrap a chatbot around a form."*

| Check | Pts now | Max | Notes |
|---|---|---|---|
| Agent really writes and executes code (not just chat) | 1 | 2 | Loop built; never run on a real model |
| Plan → dispatch → verify loop with self-correction | 1 | 2 | Fix flow built; untested live |
| Verification uses real measured results, not model opinion | 2 | 2 | Row diffs, recorders, read-only investigation |
| Sandbox isolation is real and tested | 2 | 2 | 7 engine tests, containment in CI |
| gVisor runtime on Vultr | 0 | 2 | Pending VM |
| Uses Vultr meaningfully (VM + Inference + API) | 0 | 2 | All pending keys |
| Production-grade apply (drift check, idempotency, policy) | 2 | 2 | Tested |
| Engineering quality (tests, CI, commits across the event) | 2 | 2 | 11 commits, 9 tests, CI green |
| **Total** | **10** | **16** | **→ 3.5 / 5** |

## 2. Presentation

*"Clarity over production value. If a judge can't grasp the value from the opening screen, you've already lost points."*

| Check | Pts now | Max | Notes |
|---|---|---|---|
| Value obvious in 30 s (first screen) | 2 | 2 | Hero shows "$37,404 → 744, 640 never double-charged" |
| Polished, coherent visual design | 2 | 2 | Landing + console + ledger, black-and-white system |
| Public live URL judges can use | 0 | 2 | Pending VM |
| Judges can trigger the wow moment themselves | 1 | 2 | "Break it yourself" exists; not public yet |
| Demo video, 4–5 min, golden path rehearsed | 0 | 2 | Day 4 |
| Slide deck (8–10 slides) | 0 | 2 | |
| Cover image + lablab texts | 0 | 2 | |
| **Total** | **5** | **14** | **→ 2.4 / 5** |

## 3. Business Value

*"A specific target user, a rough TAM, at least one revenue model, and why AI is essential."*

| Check | Pts now | Max | Notes |
|---|---|---|---|
| Named buyer and painful problem | 1 | 2 | Implied (ops leads); not stated in product or materials |
| Market size with sources | 0 | 2 | Research done (see PITCH.md once written) |
| Revenue model | 0 | 2 | |
| Why AI is essential (not a rules engine) | 1 | 2 | Verifier investigates intent; needs to be said clearly |
| Credible demo scenario with real numbers | 2 | 2 | Seeded trap with real measured numbers |
| Fit with the listed business areas (finance, support, sales ops) | 1 | 2 | Refunds = finance/support; show more examples |
| **Total** | **5** | **12** | **→ 2.7 / 5** |

## 4. Originality

*"A fresh angle that only became practical with current AI, not an existing product plus a chatbot."*

| Check | Pts now | Max | Notes |
|---|---|---|---|
| Distinct from the organizers' example list | 2 | 2 | Not in the list of 10 example directions |
| Distinct from existing products | 1 | 2 | Upsun clones + dry-run proxies exist; our angle is consequences for non-technical approvers |
| Memorable concept and name | 2 | 2 | "Let the double take the hit" |
| Novel mechanism (approve recorded effects, replay with drift check) | 2 | 2 | Agent code never touches prod |
| **Total** | **7** | **8** | **→ 4.5 / 5** |

---

## Scorecard

| Criterion | Now (Tue night) | Target (Sun) |
|---|---|---|
| Application of Technology | 3.5 | 5.0 |
| Presentation | 2.4 | 5.0 |
| Business Value | 2.7 | 4.5 |
| Originality | 4.5 | 4.5 |
| **Total (/20)** | **13.1** | **19.0** |
| Gate | ❌ (G1–G3, G7 open) | ✅ |

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
