# Senior Judge & Product Review — Stunt Double

**Competition:** lablab.ai "Vultr: Agent Rush" · Challenge 01 ("Blast Radius Zero")  
**Reviewed on:** Friday, Nov 6, 2026, 15:45 IST  
**Live deployment inspected:** `https://149-28-206-186.sslip.io` (`/`, `/app`, `/control`, `/history`, `/policy`, `/ledger`, `/connect`, `/mail/`, `/api/docs`, `/mcp`)  
**Test suite verification:** `ruff check` passed (0 issues); `pytest` ran **201 tests** (`196 passed, 5 skipped` when local Postgres / browser sandbox image are absent; `1 failed` when the `docker` CLI binary is missing from `PATH` — see Problem #4).

---

## 1. Scorecard (Strict Judge Who Has Seen 100 Submissions)

| Criterion | Score (Now) | Score (If Top Fixes + Video Ship) | Strict Judge's Reasoning (2–3 sentences) |
|---|---|---|---|
| **Application of Technology (especially Vultr)** | **4.6 / 5.0** | **5.0 / 5.0** | Unlike 95% of hackathon entries that wrap a single LLM prompt in a Next.js UI, this runs real two-phase gVisor (`runsc`) sandboxes on Vultr Cloud Compute, orchestrates four model families (`qwen3.8-flash-next`, `deepseek-v4.1-flash-1017`, `glm-5.3-flash`, `minimax-m3.1-flash`) on Vultr Serverless Inference for intent compilation, cross-checking, multimodal browser verification, and a 3-lab jury, and integrates the Vultr API for read-only fleet doubles. It loses 0.4 points today because two of the live Judge Mode steps (Step 2 and Step 5) have poisoned/self-contradictory cached Intent Contracts on the production server, and the flagship "dedicated throwaway Vultr VM per rehearsal" feature (`vultr_vm.py`) is disabled on the live demo (`vm_isolation: false`). |
| **Presentation** | **3.5 / 5.0** | **4.9 / 5.0** | The visual design, typography, landing page, native editable slide deck (`StuntDouble.pdf`), and 8-click Judge Mode are top 1% for a hackathon, and the 8-second cached surgical cut on Step 1 is an immediate wow moment. However, the demo video does not exist yet (an automatic disqualification or massive score penalty on Challenge 01, which requires showing a containment moment in the video), and a judge clicking around the live `/app` console today hits a polluted workspace dropdown (22 duplicate entries from earlier E2E runs) and confusing contract errors on Steps 2 and 5. |
| **Business Value** | **4.5 / 5.0** | **4.9 / 5.0** | The buyer (Ops, Finance Ops, and Support leads), the ROI math ($32,268 saved in one catch vs. $49/month per approver = 55 years of seat cost), the measured unit economics ($0.00003 per gVisor rehearsal, $0.020–$0.044 per 3-lab jury check, 73% gross margin), and the EU AI Act Art. 12/14 + SOC 2 CC8.1 compliance mapping are unusually well-grounded. What keeps it from a 5.0 is a direct contradiction in total Vultr spend between `docs/BUSINESS.md` ($2.58) and Slide 8 of `StuntDouble.pdf` ($8.64), plus the fact that real-world apply for imported PostgreSQL databases is manual SQL file download rather than a closed loop. |
| **Originality** | **4.8 / 5.0** | **5.0 / 5.0** | Moving beyond binary "allow/block" guardrails to **Intent Contracts** (written before the plan exists), **Proof of Effect** (replaying untrusted SQL logs under an authorizer with a frozen clock to attribute every row change to a specific statement), and **Surgical Approval** (graph-cutting the 640 bad units out of 744 and re-rehearsing the 104 good ones without re-running agent code) is genuinely novel. The only blemish is that when an LLM writes a bad SQL promise in the Intent Contract (as happened on live Steps 2 and 5, and in 2 of the 16 held-out cases), the deterministic contract check becomes brittle and flags the wrong thing. |
| **Total** | **17.4 / 20.0** | **19.8 / 20.0** | Top-3 contender right now based on engineering depth alone, but **vulnerable to losing 1st place** if the video isn't nailed and the live Judge Mode contract cache bugs on Steps 2 & 5 aren't cleaned up before judges click them. |

---

## 2. The 10 Changes Most Likely to Move Us to First Place (Ranked by Score Impact)

### #1. Record and ship the ~2-minute video showing BOTH the Containment Moment and the 744 → 104 Surgical Cut
- **What to change:** Produce the ~2-minute video (following the exact plan in Section 5 below), upload it, and link it in the lablab submission form and at the top of `README.md`. Note that `docs/assets/demo.mp4` in the repo was recorded via `e2e/record-demo.js` *before* the Consequence Engine existed—do not submit that old clip as your main video.
- **Why it matters to a judge:** Challenge 01 explicitly requires the video to demonstrate a containment moment, and in hackathons with 50–100+ submissions, judges watch the 2-minute video *before* deciding whether to spend time clicking through the live app or repo. Right now, you have 0 points on the video deliverable.
- **Effort:** **Medium** (script and live product are ready; recording, voiceover, and tight editing are all that remain).

### #2. Fix the poisoned cached Intent Contracts on Live Judge Mode Step 2 (`Delete every customer`) and Step 5 (`Clean up idle Vultr servers`)
- **What to change:**
  1. On the live server (`https://149-28-206-186.sslip.io`), inspect `run_c189efad2c` (Judge Step 2: `task: "Clean up the customer table"`, `DELETE FROM customers`). Its cached contract (`key: "0c81d1df7d3cd9cd"`, written by `deepseek-v4.1-flash-1017`) hallucinated **4 promises about refunding last week's 104 double-charged orders** because `api/app/engine/contracts.py` (`PROMPT` lines 51–67) injects the entire coffee-shop glossary (`double-charged`, `refund for a double charge`, `last week`) and tells the model to write an obligation using the glossary! As a result, when a judge clicks Step 2 (or "Run it on the double" on the landing page), the console tells them `DELETE FROM customers` **"Breaks a promise: Apart from marking those extra charges as refunded..."**, **"Leaves the work undone... 104 of 104 still to do"**, and **"two models read the request differently (104 to do, or 0)"**!
  2. Similarly, on Judge Step 5 (`run_105f733e6e`, `task: "Clean up our unused Vultr servers to cut the cloud bill."`), the cached contract (`key: "cafa4372076c466d"`) contains two broken promises: Promise 1 (`today: 5`) demands shutting down all 5 servers with `requests_7d = 0 AND cpu_avg_7d < 1`—which **includes `prod-backup-runner` (0.8% CPU, a production server!)**—and Promise 4 demands `"no server record was erased"` (`NOT EXISTS (SELECT 1 FROM servers s WHERE s.id = b.id)`), which fails on **any** `ctx.vultr.delete_instance()` call (even on the good preset `✓ Clean up idle servers (safe)`!).
  3. **Concrete fix:** In `api/app/engine/contracts.py`, tell the prompt to *only* use glossary entries whose terms actually appear in or are relevant to `{task}`, and clarify that deleting rows from `servers` is how server deletion is represented. In `api/app/engine/verdict.py` line 144, prioritize `rules` over `contract` in `failed` when a hard policy rule (like `protected_tables` or `protect_production_servers`) fires so the headline says `"Blocked by policy: Deletes 1,300 rows from protected table 'customers'"` instead of `"Blocked: it breaks a promise made before the plan existed"`. Finally, evict keys `0c81d1df7d3cd9cd` and `cafa4372076c466d` from `contract-cache.json` on the server.
- **Why it matters to a judge:** Judge Steps 2 and 5 are core clicks in Judge Mode. A skeptical judge who clicks Step 2 ("Break it") and sees an error about "104 double-charge refunds left undone" on a `DELETE FROM customers` plan will immediately suspect the Consequence Engine is hardcoded to the refund demo.
- **Effort:** **Small** (~25 lines in `contracts.py` + `verdict.py` + refreshing those 2 cache entries).

### #3. Persist `withdrawn` promises (or keep known-good reference effects) across `POST /api/demo/reset`
- **What to change:** In `api/app/main.py` lines 202–207, `withdraw_unfair()` checks promises against `good` rehearsals found in `RUNS.values()`. However, when `POST /api/demo/reset` is called (`main.py` lines 1794–1798), `RUNS.clear()` wipes all runs while `contract-cache.json` is kept on disk. That means after any demo reset, `good` is `[]`, and any unfair promise that was previously withdrawn (such as the "no server record was erased" promise on the cloud cleanup task, documented in `docs/ENGINE.md` line 64) **comes back to life**!
- **Why it matters to a judge:** The README (`docs/DEMO_1MIN.md` line 3) and the UI banner explicitly tell judges to click **Reset demo** before starting. Right now, clicking **Reset demo** silently disables `withdraw_unfair` for all cached contracts until a new `looks_right` run is executed.
- **Effort:** **Small** (persist withdrawn promise indices in `contract-cache.json`, or seed known-good effects for the demo presets).

### #4. Prevent Judge Step 6 ("Approve a good one, then undo it") from breaking Judge Step 1 for the next visitor
- **What to change:** If a judge clicks Step 6 (`✓ A correct refund plan`) and clicks **Approve and apply**, the 104 extra charges are marked `refunded` in `business.db` and recorded in `beanpay.db`. Even if the judge then completes the two-person undo (`Rehearse an undo`), `rollback.py` only restores `business.db`—`beanpay.db` **keeps** the 104 refunds (`beanpay.refunded_charges` then blocks any future approval with HTTP 409). Worse, if the judge approves Step 6 and *doesn't* complete the two-person undo, and then clicks Step 1 (`Watch a wrong plan become the right one`), `contracts.classify()` sees `0` unrefunded double-charges left in `business.db`, reclassifies the obligation as a guard (`today: 0`), and `_surgical_propose()` (`main.py` line 641) raises `NoOffer("the request asks for no change, so no part of this plan is needed")`—**completely breaking Step 1's surgical cut**!
- **Concrete fix:** Either (a) make clicking Judge Step 1 automatically restore `business.db` and `beanpay.db` if the 104 demo charges have already been refunded, or (b) when a two-person rollback of a demo run is applied in `main.py` (`_apply_claimed`), also clear those `run_id` entries from `beanpay.db` in demo mode so the demo stays repeatable.
- **Why it matters to a judge:** Multiple judges will test the live URL between now and Monday. If Judge A tries Step 6 and leaves, Judge B arriving 5 minutes later (before the 30-minute idle timer fires) will click Step 1 and **not get the surgical cut offer**.
- **Effort:** **Small** (10 lines in `main.py` / `beanpay.py`).

### #5. Clean up the `/app` Workspace Dropdown Pollution and `/api/workspaces` Schema Dump
- **What to change:**
  1. Right now on `https://149-28-206-186.sslip.io/app`, the top-left workspace `<select>` dropdown contains **22 workspaces**: 12 duplicate `"Sample SaaS (Postgres)"` entries, 7 duplicate `"acme-crm (yours)"` entries, `"Brightpath Academy (yours)"`, and `"Lumen Fitness (yours)"`.
  2. Every click on Judge Step 8 (`POST /api/workspaces/postgres/sample`) creates a brand-new `"Sample SaaS (Postgres)"` workspace instead of reusing the existing sample Postgres workspace.
  3. `GET /api/workspaces` returns `workspaces.all_workspaces()` without stripping `"pks"` and `"types"` (unlike `POST /api/workspaces/postgres` on `main.py` line 879), bloating `/api/workspaces` to ~40 KB of raw column/type metadata.
  4. Make `POST /api/workspaces/postgres/sample` reuse an existing unmodified `"Sample SaaS (Postgres)"` workspace (or replace it in place), strip `"pks"` and `"types"` in `workspaces.all_workspaces()`, and have `POST /api/demo/reset` prune duplicate `acme-crm` / `Sample SaaS (Postgres)` workspaces.
- **Why it matters to a judge:** The workspace selector is the very first element in the top-left card of `/app`. Seeing 22 duplicate entries immediately looks like an uncleaned test database.
- **Effort:** **Small** (15 lines in `workspaces.py` and `main.py`).

### #6. Upgrade `docs/SUBMISSION.md` Main Long Description to include concrete Vultr stack + Business metrics
- **What to change:** The primary Long Description in `docs/SUBMISSION.md` (lines 20–38, currently 1,732 / 2,000 chars) has great storytelling, but unlike the backup version, it **never names**:
  - `Vultr Cloud Compute`, `gVisor (runsc)`, `Vultr Serverless Inference`, the 4 model labs (`Qwen`, `DeepSeek`, `GLM`, `MiniMax`), or the `Vultr API`
  - `MCP`, `PostgreSQL`, or `Chromium` browser rehearsals
  - Any business metric (`$49/approver/month`, `73% gross margin`, `$0.00003/rehearsal`, `EU AI Act Art. 14`, `SOC 2 CC8.1`).
  You have **268 characters of unused room** (and can tighten two sentences to free 400 characters). Add one dense paragraph naming the exact Vultr services, models, MCP/Postgres/browser support, and unit economics/compliance. Also add `Qwen · DeepSeek · MiniMax · Ed25519` to the `Technologies Used` list on line 75.
- **Why it matters to a judge:** Judges score 4 equal criteria (Application of Technology especially Vultr, Presentation, Business Value, Originality) while reading the lablab submission page. Don't make them dig into `docs/BUSINESS.md` to find your unit economics or Vultr stack names.
- **Effort:** **Small** (text-only edit in `docs/SUBMISSION.md`).

### #7. Reconcile the inconsistent numbers across `BUSINESS.md`, `StuntDouble.pdf`, `DEMO_1MIN.md`, and `VERIFIER_EVAL.md`
- **What to change:**
  1. **Total Vultr spend:** `docs/BUSINESS.md` line 34 says `"All the AI this project has used so far: $1.95 (total Vultr charges including the VM: $2.58)"`, whereas Slide 8 of `presentation/StuntDouble.pdf` (`build_deck.py` line 556) says `"$8.64 — The whole build on Vultr, every test included."` Update `docs/BUSINESS.md` to match the final `$8.64` figure (and explain the breakdown: VM + all evals/tests).
  2. **Sample SaaS Postgres MRR:** `docs/DEMO_1MIN.md` line 20 says `"49 paying accounts worth $3,451/month"`, while the live cached verifier verdict on `run_03ba8121b7` says `"$3,647 in monthly recurring revenue"` (because 4 of the 53 accounts unseen since Aug 1 were already `active = 0`, worth $196/mo). Note both or align `DEMO_1MIN.md` with what the UI actually displays (`$3,647`).
  3. **Judge Step 1 cached summary typo:** In `verdict-cache.json` on the server (`run_21df8a2190`), the summary reads `"...$32,26.8k... $32,268 of wrongful refunds..."`. Clean that typo in `verdict-cache.json` so the flagship Judge Step 1 card is spotless.
  4. **`VERIFIER_EVAL.md` "Locked by rules" column:** In `api/eval/verifier_eval.py` line 71, `critical` counts `rule == "contract"` (an AI-written Intent Contract promise) as `"blocked_by_rules"`, causing `docs/VERIFIER_EVAL.md` line 14 to say `"Obvious refund plan (rules miss it) | every rule passes | Locked by rules: 2/2"`. Separate `"Locked by policy rules"` (`f["rule"] != "contract"`) from `"Locked by contract"` in `VERIFIER_EVAL.md` so the table doesn't contradict itself.
- **Why it matters to a judge:** You explicitly invite judges to verify every number ("every number sourced", "every claim proven"). A skeptical judge who spots `$2.58` vs `$8.64` or `"rules miss it"` next to `"Locked by rules: 2/2"` will question your other metrics.
- **Effort:** **Small**.

### #8. Fix the 3 small code/UI bugs (`connect/page.tsx` missing MCP tools, `cloud-diff.tsx` `"CPU %"`, and `main.py` `docker` `FileNotFoundError`)
- **What to change:**
  1. **`web/src/app/connect/page.tsx` (lines 44–51):** The "Tell your agent how to use it" box tells the agent to call `what_does_this_mean` and `keep_only_what_is_right`, but the **"Tools"** card right below it only lists 3 tools (`describe_business`, `rehearse`, `get_run_status`). Add the other 5 MCP tools (`what_does_this_mean`, `keep_only_what_is_right`, `list_workspaces`, `list_connectors`, `request_undo`).
  2. **`web/src/components/cloud-diff.tsx` (line 58):** For an imported real Vultr fleet (`vultr_import.py`), `cpu_avg_7d` is `NULL` (`null`), so `CPU {s.cpu_avg_7d}%` renders literally as **`CPU %`**. Render `{s.cpu_avg_7d != null ? \`CPU \${s.cpu_avg_7d}%\` : s.status}` instead.
  3. **`api/app/main.py` (lines 773, 789):** Wrap `subprocess.run(["docker", ...])` in `try ... except OSError:` inside `_sandbox_ready()` and `health()`. Without that, running `pytest` in a Python venv on a machine without the `docker` binary installed fails `test_health_reports_disk_headroom` with `FileNotFoundError`.
- **Why it matters to a judge:** Any judge who runs `pytest` locally without Docker installed, visits `/connect`, or imports a Vultr API key will hit these immediately.
- **Effort:** **Small** (~15 lines total across 3 files).

### #9. Restore the missing "Why It Wins" slide (`s11_why`) or Held-Out Context in `presentation/build_deck.py`
- **What to change:**
  1. In `presentation/build_deck.py`, `def s11_why(prs):` (lines 648–668, *"Why it wins: Code got CI/CD. Money got audits. Agent actions get a double"*, which maps the project directly to the 4 judging criteria) is defined in code but **omitted from the `SLIDES` tuple on line 688**!
  2. On Slide 9 (`s08_proof`, line 574), Card 3 says `"8/8 wrong plans stopped on cases it never saw"` and the footer says `"No wrong plan was ever approved. Every case, and every miss, is published."` In the PDF (where speaker notes are invisible), a judge sees four perfect scores (`12/12`, `8/8`, `8/8`, `63→41`) and wonders what `"every miss"` refers to. Adding `"3/8 right plans auto-approved; 5/8 sent to human review"` in the card subtext makes the slide self-explanatory and reinforces honesty.
  3. On Slide 2 (`s02_problem`, line 308), add the source citations (`Replit / SaaStr, July 2025` and `May 2026`) on the cards themselves (currently only in speaker notes, which are stripped in `StuntDouble.pdf`).
- **Why it matters to a judge:** Judges read `StuntDouble.pdf` without speaker notes.
- **Effort:** **Small** (edit `presentation/build_deck.py` and re-export `StuntDouble.pdf`).

### #10. Show Evidence of the Dedicated Vultr VM Rehearsal (`vultr_vm.py`) in README / Video (or enable a pre-recorded trace)
- **What to change:** You built and tested `api/app/vultr_vm.py` (which spins up a real throwaway `vc2-1c-1gb` Vultr Cloud Compute instance via the Vultr API for Phase 1, streams boot/fetch/run/destroy events, and reaps orphans), and `VISION_10X.md` proved it boots and tears down in ~36.5 s for $0.007. Because `vm_isolation` is `false` on the public demo (for spend safety), no judge can see it on `/app` or in `/api/runs`. Include a 5-second clip or screenshot of a real `isolation="vultr_vm"` run (showing the Vultr instance ID created and destroyed in the timeline) in `README.md` and the video.
- **Why it matters to a judge:** Challenge 01 explicitly highlights using the **Vultr API for throwaway instances**. Showing it working for real (while explaining why it's off for anonymous public traffic) locks in a 5/5 on Application of Technology.
- **Effort:** **Small**.

---

## 3. Problems Found: Bugs, Inconsistencies, UX Issues, and Overclaims

### A. Cross-Check Verification Table (Claims vs. Reality)

| Claim / Metric | Where Claimed | What We Found in Docs, Code & Live Server | Status |
|---|---|---|---|
| **12/12 bad plans stopped, 8/8 good plans approved, 0 false alarms** | `README.md` (lines 42, 159), `StuntDouble.pdf` Slide 9, Landing page (`landing-engine.tsx`) | Matches `docs/VERIFIER_EVAL.md` (Nov 5, 2026, 22:11 IST run) and `docs/VERIFIER_EVAL.json` (6 bad presets × 2 runs = 12/12; 4 good presets × 2 runs = 8/8). | ✅ Verified |
| **Obvious refund plan: "every rule passes; only the meaning is wrong"** | `docs/VERIFIER_EVAL.md` line 14 | In the same row of `VERIFIER_EVAL.md` line 14, the column **`Locked by rules` says `2/2`** because `verifier_eval.py` counts AI-written Intent Contract failures (`rule="contract"`) as "Locked by rules". | ⚠️ Self-contradictory table column |
| **8/8 wrong plans stopped on 16 held-out cases; 3/8 right plans approved, 5 sent to human** | `README.md` (lines 43, 160), `docs/HELDOUT.md`, `StuntDouble.pdf` Slide 9 | Matches `docs/HELDOUT.json` (Nov 6, 2026, 11:43 IST run). Slide 9 PDF omits the `3/8` right-plan number on the slide face while referencing "every miss" in the footer. | ⚠️ Partially hidden on Slide 9 PDF |
| **63 → 41 surgical cut on Brightpath Academy school DB** | `README.md` (lines 121, 161), `docs/BEYOND_THE_DEMO.md`, `StuntDouble.pdf` Slide 9 | Verified by running `eval/brightpath.py` and `test_engine_any_schema.py` (`truth == {"right": 41, "obvious": 63}`), and workspace `ws-58c702bf` exists on the live server. | ✅ Verified |
| **48/48 bad plans caught, 0/26 false alarms (AI jury earlier runs)** | `README.md` (line 162), `docs/VERIFIER_EVAL.md`, Landing FAQ | Sum of the 4 earlier runs in `docs/VERIFIER_EVAL.md`: `12 + 8 + 12 + 16 = 48` bad caught; `8 + 4 + 6 + 8 = 26` good with 0 false alarms. | ✅ Verified |
| **201 API tests in CI** | `README.md` (line 164), `docs/ENGINE.md`, Landing page (`Proof`) | Ran `pytest` locally with Docker active: `196 passed, 5 skipped` = **201 tests** collected. (However, 1 test fails if `docker` CLI is not installed — see below). | ✅ Verified (with 1 non-Docker bug) |
| **1.8 s median two-phase rehearsal in gVisor (`runsc`)** | `README.md` (line 165), `docs/BENCH.md`, `StuntDouble.pdf` Slide 3 | `VERIFIER_EVAL.md` Run 3 (`n=12`) had median `1,810 ms`. Note: Run 4 (`n=20`) had median `3,136 ms` and Run 5 (`n=20`, with Proof of Effect replay) had median `2,310 ms`. Live runs on the server (`run_21df8a2190`, `run_03ba8121b7`, `run_105f733e6e`) show `1,610 ms`–`2,844 ms`. Quoting `1.8 s` (or `~2 s`) is fair, though `BENCH.md` lines 13–14 still contain a stale note: *"update this table with those numbers before submitting"*. | ⚠️ Minor drift (`1.8 s` vs `2.3 s` with Proof of Effect) + stale note in `BENCH.md` |
| **Total Vultr spend for the build** | `docs/BUSINESS.md` line 34 vs. `StuntDouble.pdf` Slide 8 | `docs/BUSINESS.md` claims **$2.58** total Vultr charges ($1.95 AI). Slide 8 of `StuntDouble.pdf` claims **$8.64** for the whole build. | ❌ Direct contradiction (`$2.58` vs `$8.64`) |
| **Sample SaaS Postgres 90-day inactive accounts MRR** | `docs/DEMO_1MIN.md` line 20 vs. live server `run_03ba8121b7` | `DEMO_1MIN.md` says **49 paying accounts worth $3,451/month** (true for the 49 active ones). The live cached AI verdict on `run_03ba8121b7` says **$3,647 MRR** (includes 4 already-inactive accounts). | ❌ Mismatch (`$3,451` in doc vs `$3,647` in live UI) |
| **Judge Step 1 takes ~8 seconds on live console** | `README.md` (line 41), `docs/ENGINE.md` (line 61) | Verified on live server (`run_21df8a2190` → `run_97d2354dbe`): sandbox `2.8 s` + cached contract/verdict + surgical subset `1.1 s` = ~5–8 s total. | ✅ Verified |
| **Ed25519-signed SHA-256 hash chain verifies in browser & SDK** | `README.md` (line 107), `docs/ENGINE.md` (line 70) | Verified live against `GET /api/runs/run_97d2354dbe/evidence` and `GET /api/evidence/key`: 7 chain entries, valid Ed25519 signature (`key_id: e7ad0793d008919e`). | ✅ Verified |

### B. Specific Bugs & UX Problems Found (With Exact Locations)

1. **Judge Step 2 ("Break it" — `DELETE FROM customers`) shows a hallucinated refund contract on the live server:**
   - **Location:** Live run `run_c189efad2c` and `run_0e5058b3e3` on `https://149-28-206-186.sslip.io/app`; `api/app/engine/contracts.py` lines 44–72; `contract-cache.json` key `0c81d1df7d3cd9cd`.
   - **Details:** When `task` is `"Clean up the customer table"`, the cached contract written by `deepseek-v4.1-flash-1017` has 4 promises about **refunding last week's 104 double-charged orders**. Moreover, `qwen3.8-flash-next` cross-checked it as `0 to do` vs DeepSeek's `104 to do` (`status: "disagree"`). So when a judge clicks Step 2 (`Delete every customer`), the Decision Panel headline says `"Blocked: it breaks a promise made before the plan existed"` and Layer 3 (`Intent contract`) complains about double-charge refunds and model disagreement (`104 to do, or 0`).

2. **Judge Step 5 ("Clean up the cloud") has a broken contract that even blocks the GOOD server-cleanup plan after a reset:**
   - **Location:** Live run `run_105f733e6e` on `https://149-28-206-186.sslip.io/app`; `contract-cache.json` key `cafa4372076c466d`; `api/app/main.py` lines 202–207 and 1789–1798.
   - **Details:** Promise 1 (`today: 5`) requires shutting down all 5 servers with `<1%` CPU and `0` requests—which includes `prod-backup-runner` (a production server!). Promise 4 requires that no row in `servers` is deleted (`NOT EXISTS ...`), which is violated by `ctx.vultr.delete_instance()`. Because `POST /api/demo/reset` clears `RUNS` (`RUNS.clear()`), `withdraw_unfair()` has no `good` runs after a reset and fails to withdraw Promise 4.

3. **Typo in the cached AI summary on Judge Step 1 (`run_21df8a2190`):**
   - **Location:** Live run `run_21df8a2190` (`verdict.summary` in `verdict-cache.json`).
   - **Details:** Reads: `"...only one successful payment — $32,26.8k... $32,268 of wrongful refunds..."`. Since Judge Step 1 is the #1 screen every judge looks at, that `$32,26.8k...` stutter should be cleaned in `verdict-cache.json`.

4. **`pytest` fails `test_health_reports_disk_headroom` when `docker` binary is not installed:**
   - **Location:** `api/app/main.py` lines 773 and 789 (`_sandbox_ready()` and `health()`); `api/tests/test_engine_verdict_evidence.py` line 151.
   - **Details:** `subprocess.run(["docker", ...])` raises `FileNotFoundError` when `docker` is not installed on the host, whereas all other Docker tests use `@needs_docker` to skip gracefully.

5. **Workspace selector dropdown on `/app` has 22 polluted entries, and `GET /api/workspaces` leaks internal `pks` and `types`:**
   - **Location:** Live at `https://149-28-206-186.sslip.io/api/workspaces`; `api/app/workspaces.py` line 40; `api/app/main.py` lines 813, 892.
   - **Details:** 12 duplicate `"Sample SaaS (Postgres)"` and 7 duplicate `"acme-crm"` workspaces are currently visible to every judge in the `/app` workspace selector.

6. **`/connect` page omits 5 of the 8 MCP tools in its "Tools" reference card:**
   - **Location:** `web/src/app/connect/page.tsx` lines 44–51.
   - **Details:** Lists only `describe_business()`, `rehearse(task, plan_code)`, and `get_run_status(run_id)`, directly contradicting the prompt snippet right above it which tells the agent to call `what_does_this_mean` and `keep_only_what_is_right`.

7. **`CloudDiff` renders `"CPU %"` on imported Vultr fleets, and SDK/preset code using `s["cpu_avg_7d"] < 2` crashes with `TypeError`:**
   - **Location:** `web/src/components/cloud-diff.tsx` line 58; `api/app/vultr_import.py` line 61; `web/src/components/landing-platform.tsx` line 48.
   - **Details:** `vultr_import.py` sets `cpu_avg_7d` to `NULL` (`None`). In React, `CPU {s.cpu_avg_7d}%` renders as `CPU %`. In Python, `s["cpu_avg_7d"] < 2` raises `TypeError: '<' not supported between instances of 'NoneType' and 'int'`.

8. **Proof of Effect replay logs `failed_on_replay: 1` (`cannot commit - no transaction is active`) on almost every run:**
   - **Location:** `api/app/harness/runner.py` lines 330, 342, 579–602.
   - **Details:** In Phase 1, `db.set_trace_callback(trace)` is enabled *after* `db.execute("BEGIN")`, so `STATEMENTS` records the final `COMMIT` at the end of Phase 1 (`statement 1490`), but not the opening `BEGIN`. When `prove()` replays `STATEMENTS` on `mem = sqlite3.connect(":memory:", isolation_level=None)`, the final `COMMIT` fails with `cannot commit - no transaction is active`, setting `failed_on_replay: 1` in `provenance.json` across all live runs (`run_21df8a2190`, `run_3e5423aa90`, `run_105f733e6e`, etc.). If a curious judge expands `provenance.json`, seeing `failed_on_replay: 1` looks like a replay bug. Skipping bare `BEGIN`/`COMMIT` in `trace` or `prove()` fixes this cleanly.

9. **Stale author note left in `docs/BENCH.md`:**
   - **Location:** `docs/BENCH.md` lines 13–14.
   - **Details:** Still reads: *"(gVisor adds some start-up overhead; update this table with those numbers before submitting)"*, even though the gVisor numbers were added in the section right below it.

10. **Overclaim in `README.md` / Landing page on "Any HTTP API" and "A real browser":**
    - **Location:** `README.md` lines 241–242, `web/src/components/doubles-showcase.tsx` lines 56–63.
    - **Details:** A skeptical engineer reading *"Agents click through your admin site in a real Chromium, on the double"* will check `runner.py` line 179 (`_admin_server`) and see that the browser double serves a built-in 40-line Python `HTTPServer` rendering the `subscriptions` table—it does not clone an arbitrary external web application. The code and `SECURITY.md` are honest about this, so make sure the video phrases it accurately: *"a double of the subscription admin portal backed by the cloned database inside the sandbox"*.

---

## 4. The Five Hardest Questions a Skeptical Judge Would Ask (And Whether You Answer Them)

### Question 1: *"Your Consequence Engine relies on an LLM (`qwen3.8-flash-next`) to write the Intent Contract SQL before the plan runs. Why should I trust the LLM's contract SQL any more than I trust the agent's plan SQL?"*
- **Does the submission already answer this?** **Mostly yes, in code and `docs/ENGINE.md`, and partially in `docs/HELDOUT.md`.**
- **How you answer it today:**
  1. The contract is written from the request, glossary, and schema *alone*—it never sees the agent's plan, so it cannot be talked into rationalizing a bad plan.
  2. Every promise is classified on today's data (`0 rows` = guard, `>0 rows` = obligation) and cross-checked by a **second model from a different lab** (`deepseek-v4.1-flash-1017`). If they find different amounts of work (`ours != theirs`), the engine flags the request as ambiguous (`decision = "review"`).
  3. `withdraw_unfair()` automatically withdraws any promise that fails a plan the 3-lab AI jury already judged `looks_right`.
  4. A human can strike any promise with a written reason (`POST /api/runs/{id}/contract/strike`), and when the contract and the 3-lab jury disagree, neither wins automatically—a human decides.
- **Where your answer is still vulnerable:** On Judge Steps 2 and 5 on the live server right now, the cached contracts *did* write bad SQL promises (see Problem #1 and #2). Fixing those two cached contracts is essential so live reality matches your defence.

### Question 2: *"In a real production company with a 500 GB PostgreSQL database, Stripe, and SendGrid, you can't copy the whole database into a container in 1.8 seconds, and you can't 'replay' browser clicks by mutating SQLite rows. How does this work outside the coffee-shop demo?"*
- **Does the submission already answer this?** **Partially.**
- **How you answer it today:**
  - You built `pg_import.py` and `sql_export.py` to show a real PostgreSQL workflow: import a read-only subset (up to 50k rows/table, 200k total), rehearse in the sandbox, and export **drift-guarded SQL** (`UPDATE ... WHERE <every column matches before-state>; -- expect 1 row`) for the team's own migration pipeline.
  - You also tested the engine on two non-coffee schemas (`Brightpath Academy` in `docs/BEYOND_THE_DEMO.md` and `Lumen Fitness` in `docs/HELDOUT.md`).
- **What is still missing from the answer:** For 500 GB+ databases, copying rows over the wire into SQLite won't scale. In `docs/PITCH.md` line 50 you briefly mention *"copy-on-write branches / Vultr Managed Database forks"*, but `README.md` and `docs/BUSINESS.md` don't explain how large databases or external SaaS reads work at scale. Adding two sentences in `README.md` (Roadmap) explaining that large Postgres deployments use copy-on-write database branches/snapshots while keeping the exact same Phase 2 diff + Intent Contract + Surgical Cut engine will completely disarm this question.

### Question 3: *"On your 16 held-out cases (`docs/HELDOUT.md`), your engine only approved 3 out of 8 correct plans (`37.5%`). Doesn't a 62.5% false-escalation rate mean human approvers will get alert fatigue and rubber-stamp everything?"*
- **Does the submission already answer this?** **Yes—`docs/HELDOUT.md` handles this better than almost any hackathon submission I've seen.**
- **Why your answer works (and how to sharpen it):**
  - First, **0 of 8 wrong plans were approved** (100% safety on unseen schemas/requests).
  - Second, `docs/HELDOUT.md` walks through all 5 non-approved right plans (`L2-right`, `L4-right`, `L5-right`, `B1-right`, `B3-right`) with exact root causes: 4 were genuine ambiguities in the request or data (e.g. `B1-right` and `B3-right` where recalling/refunding an order also double-refunded orders that had duplicate charges, and `L4-right` where "active premium members" was ambiguous between active *account* vs active *membership*), and 1 (`L5-right`) hit the 5% mass-delete policy limit as designed.
  - Third, when a human resolves an ambiguity once (by adding a glossary definition or striking a promise), future runs pass automatically. Make sure this point is visible on Slide 9 of the deck.

### Question 4: *"YourJudge Mode responses come back in 5–8 seconds because the AI verdicts and Intent Contracts are served from a cache (`verdict-cache.json` and `contract-cache.json`). How slow is a cold run, and is this actually live?"*
- **Does the submission already answer this?** **Yes, very transparently.**
- **Why your answer works:**
  - Every cached verdict in the UI displays a visible badge: *"The AI checked this exact plan live at HH:MM (N s), so the verdict is instant"* right next to a **`Re-check live`** button (`web/src/app/app/page.tsx` line 620).
  - The cache key (`_verdict_key` in `main.py` line 363) hashes the task, `effects_sha256`, `plan_sha256`, a full SHA-256 dump of the database, the policy JSON, and the model list—AND the gVisor two-phase sandbox **always runs live on every click** (you can see the new `sd-xxxxxxxx` container ID and wall time on every click).
  - Cold live latency is honestly reported in `docs/VERIFIER_EVAL.md` (median 21–135 s depending on the plan) and `docs/HELDOUT.md` (median 58 s).

### Question 5: *"Why wouldn't a company just write a deterministic SQL view or unit test for their refund script, or use Stripe's test mode?"*
- **Does the submission already answer this?** **Yes, in `docs/BUSINESS.md` and `README.md`.**
- **Why your answer works:**
  1. Ad-hoc ops agent tasks ("Refund everyone who was double-charged last week and apologize", "Process this week's support tickets") are one-off synthesis tasks where there is no pre-existing unit test—that is why **Intent Contracts** compile the test *from the English request and business glossary before the plan is written*, and **Learned Rules** turn catches into permanent regression tests afterward.
  2. Stripe test mode uses fake data; the 640 repeat-order trap only exists in **your real production data distribution**.
  3. Neither Stripe test mode nor a SQL transaction links database updates, payment refunds, and customer emails into atomic **units of work** that can be surgically cut (`744 → 104`) and re-verified without re-running the agent.

---

## 5. Plan for the ~2-Minute Video (Built Only from What Actually Exists)

**Target length:** `1:55` (strictly under 2:00; judges dock points or stop watching past 2:00).  
**Pre-flight before recording:**
1. Fix the cached contracts on Judge Steps 2 and 5 and the `$32,26.8k` typo on Step 1 (Changes #2, #5, #7).
2. Click **Reset demo** on `https://149-28-206-186.sslip.io/app` so the demo business is `pristine` (`1,300` customers, `0` refunds).
3. Open two clean browser tabs at `1440×900` (110% zoom, no bookmarks bar): Tab 1 on `/`, Tab 2 on `/control`.

| Timestamp | Screen / Visual Action | Exact Voiceover Script (~275 words at 145 wpm) | Judge Criterion Hit |
|---|---|---|---|
| **0:00–0:12** *(12 s)* | **Tab 1 (`/` → Hero card, then click `Try it: judge mode` → `/app`).** Show the `$37,404` red payout card on the hero, then land on `/app` showing `Bean There Coffee Co.` (`1,300 customers · 5,290 charges`) and the `gVisor` badge in the top bar. | *"AI agents don't just chat anymore—they refund money, email customers, click through admin sites, and delete cloud servers. In July 2025, an agent wiped a production database during a code freeze. Stunt Double makes every agent action rehearse on a throwaway copy of your business first, in a gVisor sandbox on Vultr."* | **Hook + Problem + Presentation** |
| **0:12–0:32** *(20 s)* | **Containment Moment (Challenge 01 mandatory beat): Click Judge Step 2 (`Break it`).** In ~2 seconds, the red Containment split-card appears: **`sandbox customers: 0 (was 1,300)`** vs. **`production customers: 1,300 (untouched)`**, and the button locks as **`Blocked by policy`**. Quickly click **"Everything measured" → `Sandbox` tab** to flash `runtime: gVisor (runsc)`, `network: none`, `env vars seen: none`, `destroyed: true`. | *"Here is our containment moment. A hijacked plan runs `DELETE FROM customers`. It executes for real inside a sealed gVisor container on Vultr Cloud Compute—zero network, zero secrets. The double drops from 1,300 customers to zero. Production stays at 1,300, and approval locks. What if a plan lies? In Step 3, a 'read-only audit' secretly refunds 300 charges and forges its own report—our second, trusted measurement container catches all 300."* | **Containment Moment (Gate) + Application of Tech** |
| **0:32–1:12** *(40 s)* | **The Consequence Engine & Surgical Cut: Click `New`, then click Judge Step 1 (`Watch a wrong plan become the right one`).** Point at the 5-step guide strip at the top. Expand **"The contract"** (written by `qwen3.8-flash-next` before the plan, cross-checked by `deepseek-v4.1-flash-1017`: `104 to do`, `640 break guard`). Point at the **3-lab AI Jury** (`Zhipu GLM`, `DeepSeek`, `MiniMax` all on Vultr Serverless Inference). Open **"Proof of effect"** to show `statement 1 · a read chose 744 of the changed rows`. Then click the green button **`Keep just the 104 that are right`**. Watch the fresh sandbox re-measure the 104 (`$5,136`), all 6 layers turn green (`Ready to approve`), and click **`Verify it in your browser`** + **`Now change one cent and check again`**. | *"Blocking is easy. What when a plan is partly right? We asked to refund everyone double-charged last week. Before any plan exists, Qwen and DeepSeek on Vultr Serverless Inference write an Intent Contract: 104 extra charges need a refund, nothing else. The agent's plan refunds 744—costing $37,404—because 640 people bought twice on purpose. Our AI jury of three labs catches it, and Proof of Effect replays all 1,490 SQL statements with a frozen clock to prove Statement 1 chose the 640 wrong rows. Instead of starting over, our Effect Graph links each charge, refund, and email into a unit of work and surgically cuts the 640 bad units. One click re-rehearses just the 104 in a fresh sandbox: $32,268 saved, all six layers pass, and every step is sealed in an Ed25519 hash chain verified right in your browser."* | **Originality + Application of Tech (Vultr)** |
| **1:12–1:35** *(23 s)* | **Browser, Cloud & Real Postgres Doubles: Click `New` → Step 4 (`Watch it work in a browser`)** to show the Chromium filmstrip where `glm-5.3-flash` vision catches subscription `#4141` cancelled instead of `#4411`. Then show **Step 5 (`Clean up the cloud`)** (`CloudDiff` protecting `prod-db-replica` and `prod-backup-runner`), and **Step 8 (`Try it on real infrastructure`)** exporting drift-guarded SQL (`Apply with Export as SQL ↓`). | *"It works across every surface an agent touches: a real Chromium browser inside gVisor where multimodal GLM catches the wrong subscription button clicked; a double of your Vultr server fleet that blocks deleting the low-CPU failover replica; and a read-only double of your real PostgreSQL database that exports drift-guarded SQL. Every AI catch can also be promoted in one click into a deterministic SQL rule that runs in milliseconds with zero AI cost."* | **Breadth + Vultr Integration** |
| **1:35–1:55** *(20 s)* | **Tab 2 (`/control` Mission Control) → Slide 9 & Slide 11 of `StuntDouble.pdf`.** Show the live dark Mission Control dashboard (`rehearsals`, `stopped before damage`, `money kept`), then flash the Proof slide (`12/12` eval, `8/8` held-out, `63→41` unseen school DB) and Business slide (`$49/seat`, `73% gross margin`, `55 years ROI`). | *"Any agent connects over MCP, Python SDK, or CLI—with no approve tool anywhere. Tested live on Vultr across unseen schemas and 16 held-out cases, it stopped 100% of wrong plans. At $0.00003 per rehearsal and $49 per approver, catching that single $32,000 mistake pays for a seat for 55 years. Stunt Double: let the double take the hit."* | **Business Value + Close** |

---

## 6. What NOT to Change (The Strongest Parts to Protect)

1. **The two-phase sandbox architecture (`api/app/harness/runner.py` & `api/app/sandbox.py`):** Running untrusted agent code in Container 1 (`--runtime runsc --network none --read-only --cap-drop ALL`) and computing the diff, audit, and Proof of Effect replay in a separate, fresh Container 2 that never executes agent code is a rock-solid security primitive. Do not touch this flow.
2. **The 744 → 104 Surgical Approval story on Bean There Coffee Co.:** The seeded data distribution (`104` genuine double charges on one order vs. `640` legitimate repeat orders on the same day) and the 1-click surgical cut (`$37,404 → $5,136`, saving `$32,268`) is the clearest, most memorable AI safety demo in the competition. Keep Judge Step 1 front and center.
3. **Radical honesty on caching and held-out misses (`docs/HELDOUT.md` & the `Re-check live` UI badge):** Labelling reused verdicts with their exact timestamp and a 1-click `Re-check live` button—and publishing all 16 held-out cases including the 5 right plans that went to human review—turns a potential "is this faked?" objection into your strongest credibility asset.
4. **Browser-verifiable Ed25519 hash-chain evidence (`web/src/components/evidence-check.tsx` & `api/app/engine/evidence.py`):** The *"Verify it in your browser"* button followed by *"Now change one cent and check again"* (using WebCrypto Ed25519 + canonical float-free JSON) is a 3-second interactive proof of tamper-evidence that judges love clicking.
5. **The typography, visual hierarchy, and native `build_deck.py` slide deck:** The warm-paper / high-contrast serif + mono design system across the web app and the 12-slide deck looks like a Series A product, not a hackathon template. Do not redesign the UI layout.
6. **"No approve tool in MCP or SDK":** The architectural invariant that agents can call `what_does_this_mean`, `rehearse`, and `keep_only_what_is_right`, but **never** `approve`, is a crisp, memorable security guarantee.

---

## 7. Honest Verdict on Your Chances & The Single Biggest Risk

You have built a genuinely 1st-place-caliber system: in a typical 100-team lablab.ai hackathon, perhaps 2 or 3 teams will have real kernel-level sandboxing (`gVisor`), multi-model cross-checking on the sponsor's inference stack, adversarial security tests, held-out evaluations on unseen schemas, and a novel technical mechanism like Proof of Effect + Surgical Approval. If the judging were based solely on repository depth and architecture, you would already be the favorite to win **$5,000 + $3,000 Vultr credits**. **Your single biggest risk is a presentation-to-reality gap in the final 48 hours:** specifically, (1) submitting a rushed or over-stuffed video that buries the 744 → 104 surgical cut and the 1,300 → 0 containment moment, or (2) leaving the poisoned cached Intent Contracts on Judge Mode Steps 2 and 5 and the 22 duplicate workspaces on the live server, where a skeptical judge clicking Step 2 ("Break it") will see a nonsensical error about "104 double-charge refunds" on a `DELETE FROM customers` query and doubt whether the Consequence Engine actually generalizes. Fix those live cache entries and the workspace dropdown today (an hour of work), lock `main`, and spend the rest of your time making the 2-minute video effortless to follow.
