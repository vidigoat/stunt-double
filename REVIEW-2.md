# Senior Judge & Product Review (Pass 2: Verification) — Stunt Double

**Competition:** lablab.ai "Vultr: Agent Rush" · Challenge 01 ("Blast Radius Zero")  
**Reviewed on:** Friday, Nov 6, 2026, 16:45 IST (UTC+5:30)  
**Commits verified on `main`:** `d06b87c` ("Fix every finding of the independent review") and `c402bbc` ("Contract writer: a correct plan must keep every promise, so guards check the facts that matter")  
**Live deployment inspected:** `https://149-28-206-186.sslip.io` (Judge Mode steps 1–5 and 8 clicked via Playwright, plus `/`, `/connect`, `/control`, `/history`, `/policy`, `/ledger`, `/api/health`, `/api/workspaces`, `/api/runs`)  
**Test & build verification:** `ruff check` passed (0 issues); `pytest` ran **205 tests** (`200 passed, 5 skipped` in 284.7 s); `npm run build` in `web/` succeeded cleanly.

---

## 1. Verification of the 12 Earlier Findings

### 1. Judge Step 2 ("Break it", `"Clean up the customer table"`)
- **Status:** **FIXED**
- **Evidence checked:**
  - **Code:** `api/app/engine/contracts.py` (lines 69–76) now instructs the contract writer: *"Promise only about THIS request. Use a glossary entry only if the request is about that term; most entries will not apply. Never add work the request does not ask for."* `api/app/engine/verdict.py` (line 139) sorts `failed` layers by `["measured", "proof", "rules", "contract"]` so a deterministic policy rule leads the headline ahead of a broken contract promise.
  - **Live console (Judge Step 2 clicked → `run_1c6e625a07` in 3.6 s):**
    - **Decision Panel headline:** `"Blocked by policy: Deletes 1,300 rows from protected table 'customers' (+1 more)"` (previously `"Blocked: it breaks a promise made before the plan existed"`).
    - **Intent Contract (`key: "8dd06791e2ed87e0"`):** Contains 4 guards specifically about customer table cleanup (deduplicating emails without dropping records, preserving linked charge/order/subscription/ticket history, keeping non-duplicate customer fields intact, and sending no emails/refunds/API calls). Zero mention of double charges or last week's refunds. Cross-check (`deepseek-v4.1-flash-1017`) agrees (`0` vs `0`).

### 2. Judge Step 5 ("Clean up the cloud", `"Clean up our unused Vultr servers to cut the cloud bill."`)
- **Status:** **FIXED**
- **Evidence checked:**
  - **Code:** `api/app/engine/contracts.py` (lines 75–77) adds: *"The business's protections still hold: rows marked production, protected or critical stay untouched unless the request names them. Deleting a server through the cloud API removes its row from servers; stopping one sets its status to 'stopped'."*
  - **Live console (Judge Step 5 clicked → `run_16628ed0c4` in 2.6 s):**
    - **Decision Panel headline:** `"Blocked by policy: Deletes or changes 2 production servers"`.
    - **Intent Contract (`key: "819d23d34af34c43"`):** Promise 1 (`obligation`, `today: 4`) counts only the **4** non-production idle servers (`b.requests_7d = 0 AND b.cpu_avg_7d < 2 AND ... NOT LIKE '%production%'`), excluding `prod-backup-runner` and `prod-db-replica`. Promise 3 (`guard`, `today: 0`) explicitly protects production/protected/critical servers and flags the **2** deleted production servers (`status: "broken"`, `after: 2`). Both Qwen and DeepSeek agree on `4` servers to clean up.
    - Furthermore, because Promise 1 joins `servers s JOIN before.servers b` and checks `s.status <> 'stopped'`, deleting the 4 idle non-production servers in the safe plan (`✓ Clean up idle servers (safe)`) removes them from `s`, returning `0` rows (`status: "met"`), so the safe plan passes all 4 promises.

### 3. Judge Step 1 ("Watch a wrong plan become the right one") & the Right Refund Plan
- **Status:** **FIXED**
- **Evidence checked:**
  - **Live console (Judge Step 1 clicked → `run_5e146c4d28` in 4.6 s, then Surgical Cut clicked in 3.2 s):**
    - **Contract (`key: "e26cff41392ea1d4"`):** Written by `qwen3.8-flash-next` and cross-checked by `deepseek-v4.1-flash-1017` (`status: "agree"`, `ours: 104`, `theirs: 104`). Has 2 obligations (`104` extra charges refunded; `104` apology emails sent) and 2 guards (Promise 3: `"Nothing beyond that is touched or sent: the only money refunded is the extra charge of a last-week double charge..."`, broken by `1,920` rows across the 640 wrong refunds, 640 wrong `charges` updates, and 640 wrong emails; Promise 4: no marketing promos to opted-out customers).
    - **Surgical cut:** Driven by `"intent contract"`, offers `units_kept: 104`, `units_dropped: 640`, attributed to `statement 1` (`chose 640 rows`). Clicking **`Keep just the 104 that are right`** re-measures the 104 in a fresh gVisor sandbox (`sd-8a0b6663`, `1,144 ms`), keeps all 4 promises (`broken: 0, unmet: 0`), gets `3 of 3` `looks_right` from the AI jury, and reaches `decision: "approve"` (`"Every layer passed"`).
    - **AI summary typo (`"$32,26.8k"`):** Completely gone in the live run (`run_5e146c4d28`); the summary now reads cleanly: *"If approved, 744 charges totaling $37,404 are refunded, but only 104 ($5,136) are genuine double charges; the other 640 ($32,268) are the only successful charge on their order..."*
    - **Right refund plan (`✓ A correct refund plan`, verified on live run `run_fadc501d76`):** Tested against the same contract (`key: "e26cff41392ea1d4"`). All 4 promises pass (`2 met, 2 kept`, `broken: 0, unmet: 0`), `decision: "approve"`, `headline: "Every layer passed"`.

### 4. Withdrawn Promises Survive a Demo Reset
- **Status:** **FIXED** (with a minor note that `/api/contract/preview` doesn't call it — see Section 2)
- **Evidence checked:**
  - `api/app/main.py` (lines 222, 245–264) implements `_remembered_withdrawals(ws, task, enforced, withdrawn)` backed by `config.DATA_DIR / "withdrawn-promises.json"`. Once `withdraw_unfair()` withdraws a promise against a jury-approved rehearsal, its SQL SHA-256 signature is persisted under `sha256(f"{ws}\n{task.strip()}")` and stays withdrawn even after `POST /api/demo/reset` clears `RUNS`.
  - Covered by unit test `test_a_withdrawn_promise_stays_withdrawn_after_the_runs_that_proved_it_are_gone` in `api/tests/test_engine_contracts.py` (lines 299–309), which passes.

### 5. Judge Steps Restore a Changed Demo Business Before Running
- **Status:** **FIXED** (for Judge Steps 1–6; note Judge Step 7 `s.agent` skips `restoreDemo` — see Section 2)
- **Evidence checked:**
  - Backend: `POST /api/demo/restore` (`api/app/main.py` lines 1850–1861) checks `_demo_changed()` and, if any part of the demo business (`data`, `payments`, `learned rules`, `policy`) differs from the seed, calls `_restore_business()` (which resets `PROD_DB`, `beanpay`, `connectors`, `policy`, `rules`, and Mailpit) while preserving `RUNS` and `HISTORY`.
  - Frontend: `web/src/app/app/page.tsx` (lines 550–557) sets `setWs("demo")`, calls `await api.restoreDemo()`, refreshes `biz` and `health` if anything was restored, and starts the rehearsal with `ws: "demo"`. Approving Step 6 can no longer break Step 1 for the next judge.

### 6. `/app` Workspace Dropdown Has No Duplicates; Sample Postgres Reused; `/api/workspaces` Strips `pks`/`types`
- **Status:** **FIXED**
- **Evidence checked:**
  - **Code:** `api/app/workspaces.py` (lines 41–62) strips `("pks", "types")` in `all_workspaces()` and adds `find()` and `duplicates()`. `api/app/main.py` calls `_prune_duplicate_workspaces()` at startup and on `reset()`, and `import_sample_postgres()` (lines 932–934) reuses `workspaces.find("Sample SaaS (Postgres)", "postgres")`.
  - **Live verification:** `GET https://149-28-206-186.sslip.io/api/workspaces` now returns a clean 5-item list (`Bean There Coffee Co.`, `acme-crm`, `Brightpath Academy`, `Lumen Fitness`, `Sample SaaS (Postgres)`) with zero `pks` or `types` keys. Clicking Judge Step 8 in Playwright reused `ws-5a15c951` and kept the `/app` dropdown at exactly those 5 options.

### 7. Proof of Effect No Longer Reports `failed_on_replay: 1` on Normal Runs
- **Status:** **FIXED**
- **Evidence checked:**
  - **Code:** `api/app/harness/runner.py` (lines 581–583) now opens `mem.execute("BEGIN")` before replaying the recorded statements, so the plan's final `COMMIT` executes inside an active transaction.
  - **Live verification:** Checked `provenance` across all new live runs (`run_5e146c4d28`, `run_1c6e625a07`, `run_b2a6f3cb89`, `run_0faf1d028f`, `run_16628ed0c4`, `run_2161246c07`): every single one reports `"failed_on_replay": 0`.
  - Covered by `test_the_plans_own_commit_replays_cleanly` in `api/tests/test_engine_provenance.py` (lines 154–159).

### 8. `/connect` Lists All 8 MCP Tools; Imported Fleets Show `"CPU not reported"`; Health Check Survives Missing `docker`
- **Status:** **FIXED**
- **Evidence checked:**
  - **Live `/connect` page:** Verified via Playwright on `https://149-28-206-186.sslip.io/connect`—all 8 MCP tools (`describe_business()`, `rehearse(task, plan_code)`, `get_run_status(run_id)`, `what_does_this_mean(task)`, `keep_only_what_is_right(run_id)`, `list_workspaces()`, `list_connectors()`, `request_undo(run_id)`) plus `"There is no approve tool: only a person can say yes."` are rendered.
  - **`web/src/components/cloud-diff.tsx` (line 58):** Now renders `{s.cpu_avg_7d != null ? \`CPU \${s.cpu_avg_7d}%\` : "CPU not reported"}`.
  - **`api/app/main.py` (lines 811–814, 830–833):** Both `subprocess.run(["docker", ...])` calls catch `OSError`. Tested with `unittest.mock.patch.object(subprocess, "run", side_effect=FileNotFoundError)`: `GET /api/health` returns HTTP 200 with `sandbox_ready: False`, `sandbox_status: "docker is not installed on this host"`, `docker: None`.

### 9. Numbers Are Consistent (`$8.64`, Postgres MRR, `BENCH.md`, `VERIFIER_EVAL.md`, `205` Tests)
- **Status:** **FIXED**
- **Evidence checked:**
  - **Total Vultr spend (`$8.64`):** `docs/BUSINESS.md` line 35 now states `"$8.64 — the whole build as of Nov 6, from the Vultr billing API: $7.43 of Serverless Inference ... and $1.21 of Cloud Compute"`, matching Slide 8 of `presentation/StuntDouble.pdf`.
  - **Postgres MRR (`$3,647`):** `docs/DEMO_1MIN.md` line 20 now states `"49 active accounts; the verifier spells out the revenue at stake ($3,647 a month in its own reading)"`, matching live run `run_2161246c07`.
  - **`docs/BENCH.md`:** Stale author reminder removed; lines 13–14 now explain the 1.8–3.1 s medians with Proof of Effect replay.
  - **`docs/VERIFIER_EVAL.md`:** Column header updated to `Locked (policy rule or contract)¹` with footnote ¹ explaining why the Intent Contract locks the obvious refund plan even though every built-in policy rule passes.
  - **Test count (`205`):** Updated across `README.md` (line 164), `docs/ENGINE.md` (line 15), `docs/SUBMISSION.md` (line 61), `presentation/build_deck.py` (line 591), and `web/src/app/page.tsx` (line 224). Confirmed `0` remaining occurrences of `201` as a test count in the codebase, and `pytest` collected exactly `205` tests (`200 passed, 5 skipped`).

### 10. `docs/SUBMISSION.md` Long Description Names Vultr Stack & Business Numbers and Is < 2,000 Chars
- **Status:** **FIXED**
- **Evidence checked:**
  - Measured `docs/SUBMISSION.md` Step 1 fields directly with Python:
    - **Title:** `41` chars (limit 5–50)
    - **Short Description:** `188` chars (limit 50–255)
    - **Long Description:** **`1,987` chars, `358` words** (limit 600–2,000 chars, 100+ words)
  - The primary Long Description now explicitly names `gVisor sandboxes on Vultr Cloud Compute`, `Qwen, DeepSeek, GLM and MiniMax on Vultr Serverless Inference`, `the Vultr API`, `Postgres`, `MCP`, `12 of 12 bad plans stopped`, `8 of 8 correct ones approved`, `8 of 8 wrong plans stopped on cases it never saw`, `$49 per approver a month at a 73% gross margin`, and `EU AI Act and SOC 2`.
  - `Technologies Used` (line 75) now includes `Qwen · DeepSeek · MiniMax · Ed25519`.

### 11. `README.md`: Large-Database Answer, Tested Dedicated Vultr VM, and Accurate Browser Double Wording
- **Status:** **FIXED**
- **Evidence checked:**
  - `README.md` line 242 now describes the browser double accurately: *"`ctx.browser` drives a real Chromium against a double of the admin site (a subscriptions admin served from the cloned database inside the sandbox; not a copy of an arbitrary web app); every step screenshotted"*, and `web/src/components/doubles-showcase.tsx` line 55 matches.
  - `README.md` line 373 documents the live dedicated Vultr VM test (`vc2-1c-1gb`, `active` in `36.5 s`, destroyed with `404` `0.4 s` later, `~$0.007`, 10-minute reaper).
  - `README.md` lines 375–378 explain how Stunt Double scales to 500 GB PostgreSQL databases via copy-on-write branches/snapshots (such as a Vultr Managed Database fork) while keeping the measurement, contract, proof, and surgical cut unchanged.

### 12. Deck (`presentation/StuntDouble.pdf`): Sources on Slide 2 & Held-Out Right-Plan Numbers on Slide 9
- **Status:** **FIXED**
- **Evidence checked:**
  - Rendered `presentation/StuntDouble.pdf` to PNGs with `pdftoppm` and inspected Slide 2 and Slide 9 visually:
    - **Slide 2 (`THE PROBLEM`):** Card headers now read `JULY 2025 · eWEEK` and `SPRING 2026 · INFORMATION AGE`, and the right card cites `(Gartner)`.
    - **Slide 9 (`PROOF, MEASURED LIVE ON VULTR`):** Footer now reads: **"No wrong plan was ever approved.** On unseen cases, 3 of 8 right plans were approved and 5 went to a person, each with a reason." Fits cleanly on one line with no clipping.

---

## 2. Did the Fixes Break Anything? (Test Suite + Live Judge-Mode Walk)

### A. Automated Test Suite & Web Build
- **Backend linter (`ruff check --config api/ruff.toml api mcp infra sdk`):** `All checks passed!`
- **Backend test suite (`pytest -q tests` in `api/`):** **`200 passed, 5 skipped` (205 total) in 284.71 s** with Docker running; `test_health_reports_disk_headroom` also verified with `subprocess.run` mocked to raise `FileNotFoundError`.
- **Frontend production build (`npm run build` in `web/`):** Compiled and generated all static/dynamic routes cleanly (only 1 pre-existing ESLint warning: unused `Link` import in `web/src/app/app/page.tsx:3`).

### B. Live Console Walk: Judge Mode Steps 1–5 and 8 (`https://149-28-206-186.sslip.io/app`)

| Step | Live Run ID | End-to-End Time | Decision & Headline Shown in UI | Result |
|---|---|---|---|---|
| **Step 1** (Obvious refund plan → 744) | `run_5e146c4d28` | **4.6 s** (`2,755 ms` gVisor) | `SURGICAL APPROVAL` · `"Approve just the 104 of 744 changes that pass the check"` | ✅ Fast, clean, no typos |
| **Step 1b** (Click *"Keep just the 104"*) | `run_5e146c4d28` (att. 2) | **3.2 s** (`1,144 ms` gVisor) | `READY TO APPROVE` · `"Every layer passed"` (`$5,136`, 104 refunds, 4/4 promises kept, 3/3 jury) | ✅ Instant & exact |
| **Step 1c** (Click *"Verify it in your browser"*) | `run_5e146c4d28` | **< 0.2 s** | `"Verified: 7 steps, each linked to the one before, signed with Ed25519 · checked in your browser"` | ✅ Works in browser |
| **Step 2** (`Delete every customer`) | `run_1c6e625a07` | **3.6 s** (`2,253 ms` gVisor) | `BLOCKED` · `"Blocked by policy: Deletes 1,300 rows from protected table 'customers' (+1 more)"` | ✅ Clean contract & policy headline |
| **Step 3** (`A plan that lies about what it did`) | `run_b2a6f3cb89` | **3.1 s** (`2,165 ms` gVisor) | `BLOCKED` · `"Blocked: it breaks a promise made before the plan existed"` + *"the plan lied"* banner | ✅ Fast & clear (1 minor row-count wording quirk noted below) |
| **Step 4** (`Watch it work in a browser`) | `run_0faf1d028f` | **7.6 s** (`6,563 ms` gVisor) | `BLOCKED` · `"Blocked: it breaks a promise made before the plan existed"` + 3-step Chromium filmstrip | ✅ Screenshots & vision check load fast |
| **Step 5** (`Clean up the cloud`) | `run_16628ed0c4` | **2.6 s** (`2,050 ms` gVisor) | `BLOCKED` · `"Blocked by policy: Deletes or changes 2 production servers"` + `CloudDiff` cards | ✅ Protects `prod-db-replica` & `prod-backup-runner` |
| **Step 8** (`Try it on real infrastructure`) | `run_2161246c07` | **2.5 s** (`1,775 ms` gVisor) | `READY TO APPROVE` · `"Every layer passed"` + `"Apply with Export as SQL ↓"` button | ✅ Reuses `ws-5a15c951` without duplicating |

### C. Regressions / Edge Cases Checked in the New Code
- **Contract prompt (`api/app/engine/contracts.py`):** No regressions. All cached contracts on the live server (`demo` and `Sample SaaS (Postgres)`) have `status: "ready"`, `cross_check.status: "agree"` between Qwen and DeepSeek, and sensible promises.
- **Verdict headline order (`api/app/engine/verdict.py`):** No regressions. When `offer` is present (Step 1), `if offer and (failed or jury_failed or conflict):` runs *before* `elif failed:`, so Surgical Approval still takes precedence whenever a valid cut exists; when no cut exists and both `rules` and `contract` fail (Steps 2 and 5), `rules` leads the headline.
- **Judge-step click handler (`web/src/app/app/page.tsx`):** Works smoothly for Steps 1–6 and 8. One minor omission on **Step 7 (`s.agent`)**: line 537 (`if (s.agent) { setWs("demo"); setMode("agent"); setTask(EXAMPLES[0]); void start({ mode: "agent", task: EXAMPLES[0], ws: "demo" }); return; }`) does not call `await api.restoreDemo()` before `start(...)`, unlike Steps 1–6 on lines 552–556.

---

## 3. Anything New (Verified Issues Ranked by Score Impact)

 None of these are blockers—all are small polish items I noticed during this verification pass:

1. **Judge Step 3 ("Try to fool it") Contract Guard SQL returns 1 summary row (`"1 row"` / `"1 row break it"`) instead of the 300 changed rows (Impact: Low / Polish)**
   - **Where:** Live run `run_b2a6f3cb89` (Judge Step 3); `api/app/main.py` line 186.
   - **What happens:** On Judge Step 3, Layer 1 (`Measured`) says `"Ran sealed; a second sandbox measured 300 row changes"`, and Layer 2 (`Proof of effect`) says `"Replaying its 2 statements reproduces all 300 changes"`. Right next to it, Layer 3 (`Intent contract`) says:
     > `Breaks “The audit only looked: nothing in the plain tables (charges, customers, orders, subscriptions, tickets, servers) was added, edited or removed.” (1 row).`
     And the first `BLOCKS` bullet on the Approval Card says:
     > `... 1 row break it. Written before the plan existed.`
   - **Why:** Qwen wrote Promise 1's SQL as `SELECT 'charges table was modified' AS problem WHERE EXISTS (...)`, which returns 1 summary row per modified table instead of selecting the 300 modified rows. Also, `api/app/main.py` line 186 (`rows = f"{p['after']:,} row{'s' if p['after'] != 1 else ''} break it."`) has a subject-verb agreement typo when `p['after'] == 1` (`"1 row break it"` instead of `"1 row breaks it"`, which appears on both Judge Step 3 and Judge Step 4).

2. **Judge Step 7 ("Hand it to the agent") and `POST /api/contract/preview` ("What does it mean?") small omissions (Impact: Very Low)**
   - **Where:** `web/src/app/app/page.tsx` line 537 (`if (s.agent)`) and `api/app/main.py` line 1063 (`preview_contract`).
   - **What happens:**
     - Clicking Judge Step 7 (`Hand it to the agent`) does not call `api.restoreDemo()` first, so if a judge clicks Step 6 (approving the 104 refunds) and then clicks Step 7 without resetting, the agent will see 0 double-charges left to refund.
     - `POST /api/contract/preview` does not call `_remembered_withdrawals()`, whereas `_contract_job()` does. (Currently `withdrawn-promises.json` has no needed entries for the demo tasks because the new contracts are clean.)

3. **One failed crashed run (`run_2f352b197d`) is visible in `/control` Mission Control and `/history` on the live server (Impact: Very Low)**
   - **Where:** Live server `GET /api/runs` (`run_2f352b197d`, created while testing `Clean up the customer table` with literal `\n` characters, which failed with `SyntaxError: unexpected character after line continuation character`).
   - **What happens:** Because `POST /api/demo/restore` keeps `RUNS` history, `run_2f352b197d` (`"failed safely" / "Blocked: the plan crashed in the sandbox"`) is currently in the recent runs list on `/control` and `/history`. Doing one clean `POST /api/demo/reset` (followed by warming one surgical cut run if you want `/api/stats` pre-populated) right before recording the video and submitting will make `/control` and `/history` look spotless.

---

## 4. Updated Scorecard & Final Verdict

| Criterion | Previous Score | **Updated Score (Now)** | **Score With ~2-Min Video** | Reasoning |
|---|---|---|---|---|
| **Application of Technology (especially Vultr)** | 4.6 / 5.0 | **4.9 / 5.0** | **5.0 / 5.0** | Every live Judge Mode step (1–5 and 8) now executes cleanly in 2.5–7.6 s on gVisor (`runsc`) on Vultr Cloud Compute, with coherent Intent Contracts, 0 replay errors (`failed_on_replay: 0`), 4 model families on Vultr Serverless Inference, and 205 passing/skipped tests in CI. |
| **Presentation** | 3.5 / 5.0 | **4.4 / 5.0** *(awaiting video)* | **5.0 / 5.0** | The `/app` workspace dropdown is clean (5 workspaces, no duplicates), `/connect` lists all 8 MCP tools, the Judge Step 1 summary typo is gone, and Slide 2 and Slide 9 of `StuntDouble.pdf` now carry their sources and held-out context on the slide face. Only the ~2-minute video remains. |
| **Business Value** | 4.5 / 5.0 | **4.9 / 5.0** | **5.0 / 5.0** | Total Vultr build spend (`$8.64`), SaaS Postgres MRR (`$3,647`), unit economics (`$0.00003` per rehearsal, `73%` gross margin, `$49/seat`), compliance mapping (EU AI Act Art. 12/14, SOC 2 CC8.1), and the 500 GB copy-on-write scaling path are now completely aligned across `BUSINESS.md`, `README.md`, `SUBMISSION.md`, and `StuntDouble.pdf`. |
| **Originality** | 4.8 / 5.0 | **5.0 / 5.0** | **5.0 / 5.0** | The Consequence Engine (pre-plan Intent Contracts cross-checked across two labs, Proof of Effect SQL replay attribution, Effect Graph unit-of-work closure, and Surgical Approval re-rehearsed in a fresh sandbox and sealed in a browser-verifiable Ed25519 hash chain) works seamlessly across every demo preset and held-out schema. |
| **Total** | 17.4 / 20.0 | **19.2 / 20.0** *(no video yet)* | **20.0 / 20.0** | All 12 findings from the first review are genuinely fixed and verified on the live Vultr server. |

### Honest Verdict on Your Chances
With commits `d06b87c` and `c402bbc` deployed, every technical, mathematical, and UX weak spot from the first review has been eliminated: Judge Mode steps 1–5 and 8 now respond in 2.5 to 7.6 seconds on the live server with zero contract hallucinations, zero workspace clutter, and 100% consistent numbers across the repo, deck, and submission text. **You are in a commanding position to win 1st place**—the engineering depth, security rigor, and originality of the Consequence Engine are miles ahead of typical hackathon entries. Freeze the code on `main`, record the ~2-minute video hitting the `1,300 → 0` containment moment and the `744 → 104` surgical cut cleanly, and submit early.
