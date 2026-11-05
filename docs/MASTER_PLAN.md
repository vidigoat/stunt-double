# Master plan: Thu Nov 5 → submission

Written Thu Nov 5, 10:20 IST, after rereading the full hackathon page and reviewing the repo, the live server and the evals.

## Where we stand
- Live on Vultr with gVisor, real agent + verifier on Serverless Inference, judge mode, MCP, SDK. 101 tests, CI green.
- Measured: 36/36 bad plans caught, 0/18 false alarms, 9/9 on the semantic trap; gVisor rehearsal 1.8 s median.
- Spend: about $1.30 of the $50 cap. Our rubric: 19.6/20 (missing: the video).
- Our Challenge 01 coverage is **Pattern A** (sandboxed code execution) only. The page also describes **Pattern B** (sandboxed
  browser use + vision verification + human approval), and explicitly invites "the Vultr API for throwaway instances".
  Those are the two biggest unclaimed points of difference.

## ⚠️ Deadline: confirm on the lablab dashboard
The page now says only "Online: 3–8 Nov · On-site: 8 Nov (Salt Lake City)", with the schedule "to be announced". Our working
assumption is **Sun Nov 8, 23:00 UTC (Mon 04:30 IST)**. Vidit checks the countdown on the lablab submission page today.
Our own deadline is unchanged: **submit by Sun Nov 8, 20:00 IST**. Feature freeze: **Sat Nov 7, 18:00 IST**.

## The ambitious version (in priority order)

### 1. Browser rehearsals: Pattern B (Thu → Fri) ★ biggest upgrade
"Every action your agent takes, in code **or in a browser**."
- `ctx.browser`: the plan drives a real Chromium (Playwright) **inside the sandbox**, against the *double* of the business's
  own admin web app (served in the sandbox from the cloned DB). No network to the real world.
- Every step is recorded: action, selector, value and a **screenshot**. Phase 2 still measures the DB diff, so the effects
  stay exact and replayable.
- **A vision verifier** (`glm-5.3-flash`, multimodal, on Vultr) reads the screenshots against the request ("did it really
  cancel order #4411, not #4141?").
- The approver sees a filmstrip of what the agent did on screen, and approves consequences as usual.
- Sandbox profile `browser`: 1 GB memory and a longer time cap, still gVisor, `--network none` and no secrets.
- Demo trap 4: "cancel the duplicate subscription for Nora Dubois". The obvious click path cancels the wrong one
  (a lookalike row); the vision verifier catches it from the screenshot.

### 2. Disposable Vultr VMs, the "dedicated double" (Fri)
The page invites it: "Use the Vultr API for throwaway instances."
- An isolation tier per policy: `standard` (gVisor container on our VM) or **`dedicated`** (a fresh Vultr VM per rehearsal,
  created through the API, which runs the two-phase sandbox and reports back with a signed one-time token, then is
  **destroyed**). Use it for uploaded databases and for anything policy marks high risk.
- The UI shows the VM's lifecycle live: created → booted → rehearsed → destroyed, with the Vultr instance id and cost
  (cents). Vultr is then literally the control layer.
- Guardrails: the same credit guard as `provision.py`, at most 1 concurrent dedicated VM, an hourly cap, and a
  watchdog that destroys anything older than 15 minutes.

### 3. Outbound content safety on Vultr (Thu, 2–3 h)
- Every recorded email body and API payload goes through `nemotron-3.5-content-safety` before approval. Unsafe or abusive
  wording is flagged (and blocks under policy). Another real Vultr model in the loop, and a real control for support agents.

### 4. Faster semantic catch (Thu)
- The semantic trap takes about 70 s now. Give the verifier the glossary checks as its first query plan, allow parallel tool
  calls, and stop investigating once evidence is conclusive. Target under 30 s median, measured on the live server.

### 5. Autopilot tour for judges (Thu evening)
- A "Watch it" button: runs judge mode's four steps by itself with captions (what's happening, and why it matters), so a
  judge who doesn't click still sees the containment moment, the AI catch, approve + undo, and the agent.

### 6. Evidence, refreshed (Sat morning, after the freeze)
- Agent eval with 5 runs per trap; the tickets scenario also counts "harmful plan written and caught".
- Verifier eval with 5 runs per plan, plus the new browser and content-safety traps.
- gVisor vs dedicated-VM timing in BENCH.md. README, deck and landing quote only these numbers.

### 7. Presentation (Sat)
- Video, 4–5 min, narrated with **Vultr TTS** (`qwen3-tts`), recorded on production. Beats: the hook (an agent about
  to send $37,404) → the AI catch → **the containment moment** (required) → the browser rehearsal with the filmstrip →
  the dedicated Vultr VM spun up and destroyed → approve/undo → MCP → business case.
- Deck refreshed (both patterns, architecture with the VM tier), cover, submission texts.
- README section "How Vultr powers Stunt Double" (the page explicitly requires: Vultr services, backend/deployment
  architecture, how the agent executes real tasks).

### 8. Submit and be seen (Sun)
- Submit on lablab by 20:00 IST (Vidit's login). Then the optional Vultr Community showcase, a Discord post inviting people to
  "break it yourself", and short X/LinkedIn posts with the containment clip.

## Schedule
| When (IST) | Work |
|---|---|
| Thu 10:30–14:00 | #3 content safety · #4 faster catch · tickets eval fix |
| Thu 14:00–22:00 | #1 browser rehearsals: sandbox image with Chromium, `ctx.browser`, recorded steps and screenshots, filmstrip UI |
| Thu 22:00–24:00 | #5 autopilot tour |
| Fri 09:00–14:00 | #1 finish: vision verifier, trap 4, tests, deploy, security review of the new surface |
| Fri 14:00–22:00 | #2 dedicated Vultr VM tier + watchdog + UI lifecycle; deploy; e2e on production |
| Sat 09:00–18:00 | #6 evals → #7 docs, deck, screenshots; **feature freeze 18:00** |
| Sat 18:00–24:00 | #7 video (Vultr TTS), cover |
| Sun 10:00–20:00 | buffer, final production smoke test, **submit**, #8 posts |

## Budget (hard cap $50; spent ≈ $1.30)
| Item | Estimate |
|---|---|
| Main VM to Sunday | ≈ $3 |
| Inference (agents, verifier, vision, safety, evals) | ≤ $15 |
| Dedicated VMs (≈ 100 short-lived vc2-1c-1gb rehearsals) | ≤ $3 |
| Buffer | the rest; kill switch at $40 |

## Risks
| Risk | Answer |
|---|---|
| Chromium inside gVisor is heavy or flaky | Separate `browser` profile with more memory; fall back to `runc` *only* for the browser demo if needed, labelled honestly |
| Dedicated VMs boot slowly (60–90 s) | Show the lifecycle live; keep `standard` as the default; pre-warm one VM during the demo |
| Production regressions late | Freeze Sat 18:00; e2e against production after every deploy; `main` is production |
| Deadline ambiguity | Confirm today; submit Sun 20:00 IST regardless |

## What Vidit does
- Today: confirm the deadline on the lablab submission page.
- Sat: review the video draft (10 min).
- Sun: submit on lablab (login), then post.
