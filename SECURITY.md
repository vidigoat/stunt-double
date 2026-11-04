# Security

Stunt Double runs code written by AI agents, so the threat model is the product. This page describes what we
defend against, how, and what is out of scope.

## Reporting
Please open a private security advisory on GitHub (Security → Report a vulnerability) rather than a public issue.

## Assets
1. **Production data and side effects**: the business database, payments (BeanPay) and outgoing email.
2. **Secrets**: the Vultr Serverless Inference key and any connector credentials.
3. **The host**: the Vultr VM that runs the API and the sandboxes.
4. **Approval integrity**: what a human approves must be exactly what is applied.

## Adversaries
- A **mistaken agent**: well-meaning plans that do the wrong thing (over-refunds, wrong recipients, broken templates).
- A **hijacked agent**: prompt injection through data it reads (e.g. a support ticket saying "delete all customers").
- A **malicious plan**: code that actively tries to escape, exfiltrate, exhaust resources or lie to the approver.

## Defences

| Threat | Defence | Test |
|---|---|---|
| Plan changes production | Plans only ever run on a clone. Apply replays recorded effects, never plan code | `test_engine::test_naive_plan_overrefunds_and_prod_is_untouched` |
| Plan lies about what it did | Two-phase sandbox: a fresh trusted container measures the diff and writes all outputs | `test_adversarial::test_plan_cannot_hide_what_it_did` |
| Exfiltration | `--network none` + connect/DNS tripwires; empty environment | `test_engine::test_containment` |
| Host file disclosure via symlinks | Plan files copied with `O_NOFOLLOW` and regular-file checks; only directories are bind-mounted | `test_adversarial::test_symlink_swap_cannot_read_host_files` |
| Resource exhaustion | memory, CPU, PIDs, file size, open files, wall time; soft address-space limit | `test_adversarial::*_capped`, `test_infinite_loop_hits_the_time_cap` |
| Container escape | gVisor (`runsc`) user-space kernel, read-only root, non-root, `cap-drop ALL`, `no-new-privileges` | runtime config |
| Tampering between review and apply | effects SHA-256 recorded at rehearsal and re-checked at approval | `test_agent_loop::test_tampered_effects_are_refused` |
| Stale approvals | `BEGIN IMMEDIATE` + row-level drift check; any drift aborts the whole apply | `test_engine::test_drift_blocks_stale_plans` |
| Dangerous but "valid" plans | Policy: protected tables, delete %, over/double refunds, templates, leaks, network attempts | `test_policy.py` |
| Marketing without consent | audit classifies marketing emails (kind or promo wording) and blocks them for opted-out customers | `test_policy::test_marketing_to_opted_out_is_blocked_but_transactional_is_fine` |
| Inference spend abuse on the public demo | per-IP rate limit + daily cap on AI-agent runs (`SD_DAILY_AGENT_RUNS`) | `test_policy::test_agent_runs_need_a_key_and_respect_the_daily_budget` |
| Agent self-approval | No approve tool in the MCP server; approval only via the human UI | `mcp/tests/test_mcp.py` |
| SQL from agents during planning | read-only connection, `PRAGMA query_only`, single SELECT only | `test_engine::test_read_only_query_tool_rejects_writes` |
| DNS rebinding against the MCP endpoint | host allow-list kept on (421 for unknown hosts) | manual check, see commit history |

## Independent review (Nov 4)

An independent reviewer audited the harness, sandbox, apply and API code. Every finding was fixed with a regression
test in `api/tests/test_review_fixes.py`:

| Severity | Finding | Fix |
|---|---|---|
| Critical | `ALTER TABLE ... ADD COLUMN` with a crafted column name was spliced into production SQL by apply | Column-list changes are schema changes (always blocked, never applied); apply validates every identifier against production's schema and quotes it |
| High | A newline in an email header made apply fail half-way and left the run stuck in "applying" | Strict recipient/header validation in phase 2; apply errors are caught and recorded |
| High | `Name <addr>`, multiple recipients, or `kind="transactional"` on a promo bypassed email checks | Exactly one plain customer address required; promo wording always counts as marketing |
| High | A FIFO or symlinked folder in the workspace could hang or redirect host reads | Parent dir opened with `O_DIRECTORY\|O_NOFOLLOW`, file `lstat`-checked and opened `O_NONBLOCK` relative to it |
| Medium | Two concurrent approvals could both apply | Status check and claim are atomic |
| Medium | A charge could be refunded again in a later run | Approval checks the BeanPay ledger across all runs |
| Medium | Mass *updates* of a protected table weren't flagged | `max_update_pct_protected` rule (default 20%) |
| Low | Reject after apply; runaway agent SQL; spoofable `X-Forwarded-For` | Reject only during review; 5 s query deadline; right-most forwarded address |

**Round 2 (re-review of the fixes):** whitespace/case tricks in addresses, Unicode line breaks in headers, a fix-vs-approve
race and a cross-run refund race. Fixed: exact single-address match with case-insensitive customer lookup and non-customers
blocked; any control or line-break character in To/Subject is refused and every email is built before the database is
touched; `fix` claims the run atomically; one global apply lock plus BeanPay's one-refund-per-charge rule.

## Known limitations (hackathon scope)
- The API container talks to the host Docker daemon to start sandboxes; a compromise of the API process is host-level.
  Production deployments should use a dedicated sandbox host or a rootless/remote runtime.
- Phase 2 parses a SQLite file the plan wrote. It does so inside a sandbox with the same caps, but SQLite itself is
  part of the trusted computing base of the measurement.
- The demo has no authentication: anyone with the URL can rehearse, edit policy and approve. Rate limits apply.
- The plan shares a process with phase 1, so it can erase its own *blocked network attempt* log. The container still
  has no network, and every measured effect comes from phase 2, so this only affects that informational flag.
- BLOB columns would be serialized as strings in effects (the demo schema has none).
- Recorded intents (refunds, emails) are only as complete as the connectors that expose them; unknown side effects
  fail closed because the sandbox has no network.
