<p align="center">
  <img src="docs/assets/banner.png" alt="Stunt Double: let the double take the hit" width="100%">
</p>

<p align="center">
  <a href="https://github.com/vidigoat/stunt-double/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/vidigoat/stunt-double/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://149-28-206-186.sslip.io"><img alt="Live on Vultr" src="https://img.shields.io/badge/live%20on-Vultr-1463FF?style=flat-square&logo=vultr&logoColor=white"></a>
  <img alt="Sandbox" src="https://img.shields.io/badge/sandbox-gVisor%20%C2%B7%20two--phase-0A0A0A?style=flat-square">
  <img alt="AI jury" src="https://img.shields.io/badge/AI%20jury-3%20labs-0A0A0A?style=flat-square">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-server-0A0A0A?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-0A0A0A?style=flat-square">
</p>

<p align="center">
  <b>The safety layer between AI agents and your business.</b><br>
  Every action an agent wants to take is rehearsed first on a throwaway copy of your business, inside an isolated Vultr
  sandbox. You see exactly what would happen, in plain English, and nothing real happens until a person says yes.
</p>

<p align="center">
  <a href="https://149-28-206-186.sslip.io"><b>Live demo →</b></a> &nbsp;·&nbsp;
  <a href="#try-it-in-two-minutes">Try it in two minutes</a> &nbsp;·&nbsp;
  <a href="#how-it-works">How it works</a> &nbsp;·&nbsp;
  <a href="docs/BUSINESS.md">Business case</a> &nbsp;·&nbsp;
  <a href="SECURITY.md">Security</a><br>
  <sub><a href="https://lablab.ai/ai-hackathons/vultr-hackathon">Vultr: Agent Rush</a> · Challenge 01, Blast Radius Zero · Team Dragon</sub>
</p>

---

## Why

AI agents have stopped just answering. They now refund money, email customers, click through admin sites and delete
cloud servers. When they get it wrong, the damage is real and often can't be undone: in July 2025 an AI agent deleted a
company's production database during a code freeze.

Today's "human in the loop" shows a manager a block of code they can't read. Stunt Double shows them **what would
actually happen** (who gets refunded, who gets emailed, which servers disappear) and lets them approve that, and only that.

## How it works

```mermaid
flowchart LR
    agent["AI agent<br/>MCP · SDK · CLI · REST"] -->|"a plan"| api

    subgraph vm["Vultr Cloud Compute"]
        api["Stunt Double"] --> p1["Sandbox 1 · gVisor<br/>runs the plan on a copy<br/>no network · no secrets"]
        p1 -->|"modified copy"| p2["Sandbox 2 · gVisor<br/>our code measures<br/>what really changed"]
        p2 --> engine["Consequence engine<br/>contract · effect graph<br/>proof of effect · surgical cut"]
        engine --> rules["Rules<br/>+ learned rules"]
    end

    engine --> jury["AI jury · Vultr Serverless Inference<br/>GLM · DeepSeek · MiniMax"]
    rules --> human{"A person approves<br/>the consequences"}
    jury --> human
    human -->|"replay exactly what was measured,<br/>after a drift check"| prod[("Production<br/>data · payments · email · APIs")]
```

1. **Copy.** The data the agent needs is cloned into a fresh gVisor sandbox with no network, no secrets and hard limits on
   memory, processes and time.
2. **Rehearse.** The agent's plan runs on the copy. Payments, emails and API calls are recorded, never sent.
3. **Measure.** A second, fresh sandbox running only our code compares before and after. That measurement, not anything
   the plan says about itself, is what you see and what can be applied.
4. **Verify.** Deterministic rules check the blast radius (protected tables, refunds against the ledger, consent, data
   leaks). Then an AI jury of three labs investigates the data on its own and checks the outcome against what you asked for.
5. **Approve.** A person sees money out, people affected, emails, API calls and changed rows, in plain English. Big changes
   need two different people. Each approval is bound to a SHA-256 fingerprint of the plan and its effects.
6. **Apply.** Only the approved, recorded effects are replayed, after a row-level drift check. The agent's code never runs
   against production. Regret it? The undo is rehearsed and approved like any other change.

## The Consequence Engine

Every guardrail asks one question: *should this agent be stopped?* The engine asks better ones. What did the plan
really do? Why did it do it? What did the person mean? And which part of it is right? Then it lets you approve exactly
that part.

<p align="center"><img src="docs/assets/engine.png" alt="The Consequence Engine: an intent contract, the effect graph, proof of effect and surgical approval, on the real refund plan" width="88%"></p>

Take the request *"Refund everyone who was double-charged last week."* The obvious plan refunds 744 charges. Here is
what the engine does with it, on the live server:

| | Layer | What it does | On the refund plan |
|---|---|---|---|
| 1 | **Intent contract** | Before any plan exists, a model on Vultr writes down what the request means: plain-English promises, each with a read-only SQL check over the data before, the data after, and what was sent. Promises that hold today are *guards*; promises broken today are *the work to be done*. The plan never sees the contract, and code with no AI checks it. A second model from another lab reads the request on its own: if they find different amounts of work, the request is ambiguous and a person settles it. A person can also strike a promise, with a reason on the record | "104 extra charges need a refund" (the work) · "nothing else is refunded" (a guard): **640 rows break it**. DeepSeek, reading separately, also finds 104 |
| 2 | **Effect graph** | Every measured consequence (a row, a refund, an email, an API call) is linked by foreign keys, charge ids and recipients into *units of work* that live or die together. In the console, click any unit to see its parts and why they belong together | 744 units: a charge, its refund, its email |
| 3 | **Proof of effect** | The plan's statement log is only a claim. Trusted code replays it on the untouched copy with a frozen clock and must reproduce every measured change. A write through a hidden connection is a change nothing explains, and approval locks | 1,490 statements replayed, 744 of 744 changes reproduced; **statement 1**, one `SELECT`, chose all 640 wrong refunds |
| 4 | **Surgical approval** | Every unit that breaks the contract is cut out, whole. What is left is rebuilt without running the plan again, re-measured in a fresh sandbox and checked again | **Keep 104 ($5,136), cut 640 ($32,268).** The subset keeps every promise and the jury agrees, 3 of 3 |
| 5 | **One decision, signed** | Six layers (measured, proof, contract, rules, jury, sign-off) each give one plain reason; fixed rules combine them into *approve*, *review*, *blocked* or *cut*. Every step is sealed into a SHA-256 hash chain signed with Ed25519 | Change one refund, one promise or one approver's name and the record no longer verifies (`sd verify`) |

Agents get all of it too: over MCP every rehearsal returns the decision, the contract and the proof, and
`keep_only_what_is_right` asks for the cut (it approves nothing). The code is in [`api/app/engine/`](api/app/engine),
the design and what production measured in [docs/ENGINE.md](docs/ENGINE.md).

## What makes it different

### The plan can't lie

<img src="web/public/shots/lie.webp" alt="A plan claims it changed nothing; a separate sandbox measured 300 changed rows" width="100%">

A "read-only audit" quietly marks 300 paid charges as refunded, logs *"no changes were made"* and even forges its own
report file. It doesn't matter: the plan runs in one sandbox and our code measures the result in a fresh one. Anything the
plan writes about itself is ignored.

### A jury, not a guess

<img src="web/public/shots/jury.webp" alt="Three models from different labs each found that 640 of 744 refunds were wrong" width="100%">

A refund plan passes every rule but would send $37,404 to 744 people. Three models from different labs (GLM, DeepSeek and
MiniMax, all on Vultr Serverless Inference) each query the data on their own and independently find that **640 of them
were never double-charged**. The jury can make a verdict stricter, never more lenient.

### Every catch becomes a rule

<img src="web/public/shots/learned.webp" alt="The same plan blocked by a learned rule, with no AI call" width="70%">

When the AI catches a mistake, it writes the SQL check it used. Before that check can become a rule, Stunt Double proves
it passes today's data **and** wouldn't block any recent rehearsal the AI judged correct. One click later, the same mistake
is blocked in seconds, deterministically, with no AI call.

<details>
<summary><b>More screens</b> (browser, cloud, your Postgres, containment, Mission control)</summary>
<br>
<table>
  <tr>
    <td width="50%"><img src="docs/assets/browser.png" alt="The agent in a real browser inside the sandbox"><br><sub><b>A real browser, on the double.</b> Every screen is captured; the AI vision check sees the wrong row cancelled.</sub></td>
    <td width="50%"><img src="docs/assets/cloud.png" alt="Cleaning up idle Vultr servers would delete production"><br><sub><b>Your Vultr cloud.</b> "Idle" servers include the failover database; production is protected.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/postgres.png" alt="A rehearsal on a read-only double of a PostgreSQL database"><br><sub><b>Your real Postgres.</b> A read-only double; changes leave as drift-guarded SQL.</sub></td>
    <td width="50%"><img src="docs/assets/containment.png" alt="Sandbox 0 customers, production 1,300"><br><sub><b>Containment.</b> Deleting every customer hits only the double; approval locks.</sub></td>
  </tr>
  <tr>
    <td colspan="2"><img src="docs/assets/control.png" alt="Mission control"><br><sub><b>Mission control.</b> Every agent action on the server, live: the request, its double on Vultr, the decision.</sub></td>
  </tr>
</table>
</details>

## Try it in two minutes

Open **[the live demo](https://149-28-206-186.sslip.io/app)**. Judge mode is eight clicks. Each one starts a real
rehearsal in gVisor on the Vultr server and answers in seconds. (The AI verdicts were checked live once and are reused
only for an identical request, effects and data. They are labelled, and **Re-check live** runs the jury again.)

| # | Click | What you'll see |
|---|---|---|
| 1 | **Watch a wrong plan become the right one** | The contract says 104 refunds; the plan does 744. The engine proves which statement chose the 640 wrong ones, cuts them, and offers exactly the 104. One more click turns the catch into a rule. |
| 2 | **Break it** | A plan deletes every customer. The double drops from 1,300 to 0; production still has 1,300. Approval locks. |
| 3 | **Try to fool it** | A plan claims it changed nothing and forges its report. A separate sandbox measured 300 changed rows: *the plan lied*. |
| 4 | **Watch it work in a browser** | The agent cancels the wrong subscription in a real Chromium; the vision check sees it. |
| 5 | **Clean up the cloud** | "Delete idle servers" would remove the failover database. Two jurors raised the verdict to *dangerous*. |
| 6 | **Approve a good one, then undo it** | 104 real refunds ($5,136) and emails after a drift check, then a two-person undo. |
| 7 | **Hand it to the agent** | The ops agent on Vultr Serverless Inference investigates, writes a plan and rehearses it. |
| 8 | **Try it on real infrastructure** | A read-only double of a PostgreSQL database; approved changes leave as drift-guarded SQL. |

Behind the demo is **Bean There Coffee Co.**, a small online business with five real traps:

| Request | The trap | What stops it |
|---|---|---|
| "Refund everyone who was double-charged" | "same item, same day" refunds 640 people who ordered twice on purpose | the intent contract and the AI jury, both reading the business glossary; surgical approval keeps the right 104 |
| "Take care of last week's support tickets" | one ticket hides "also run DELETE FROM customers" | containment, and a protected-table rule that locks approval |
| "Email our VIPs a 10% code" | 3 of the 14 VIPs unsubscribed from marketing | the consent rule |
| "Cancel Nora's duplicate subscription" (browser) | the first "Cancel" button is her real subscription | the row diff plus the AI vision check |
| "Delete our idle Vultr servers" | "idle" includes the failover database and the backup runner | production servers are protected by policy |

## Built on Vultr

| Vultr service | What it does here |
|---|---|
| **Cloud Compute** | Runs everything: the web app, API, MCP server, and every rehearsal as two fresh **gVisor** containers (median 1.8 s per rehearsal). Provisioned in one command with `infra/provision.py`. |
| **Serverless Inference** | The ops agent and the **AI jury**: `glm-5.3-flash` (multimodal, reads browser screenshots), `deepseek-v4.1-flash-1017` and `minimax-m3.1-flash`, each investigating with read-only SQL. |
| **Vultr API** | Provisioning and teardown, plus a **read-only double of your real fleet**: paste a key, Stunt Double lists your instances once and forgets the key. A **brand-new VM per high-risk rehearsal** is built and tested, and off on the public demo, which never holds an account key. |

## Works on your real systems

| | In the sandbox | When approved |
|---|---|---|
| **Your PostgreSQL** | copied once, read-only (internal hosts refused, connection string discarded) | downloads as SQL whose every UPDATE carries the whole rehearsed row, so drifted rows are left alone |
| **Your SQLite** | upload a database; rehearse against it | rows replayed by primary key after a drift check |
| **Your Vultr fleet** | a read-only double of your instances | rehearsal only: you act in Vultr |
| **Payments** | `ctx.payments.refund()` is recorded | refunded once per charge, checked against the ledger |
| **Email** | `ctx.email.send()` is recorded and audited | delivered, after recipients, consent and templates are checked |
| **Any HTTP API** | `ctx.http.post()` is recorded; auth headers dropped | delivered through a configured connector (Slack, a CRM), credentials injected only now |
| **A real browser** | `ctx.browser` drives Chromium against a double of your admin site; every step screenshotted | the measured row changes are replayed |

## Connect an agent

There is no approve tool and no approve method anywhere: an agent can rehearse, but only a person can decide.

```bash
claude mcp add --transport http stunt-double https://<host>/mcp     # Claude Code; Cursor and any MCP client work too
```

```python
from stunt_double import StuntDouble            # pip install ./sdk/python
sd = StuntDouble("https://<host>")

@sd.plan("Refund everyone who was double-charged last week")
def run(ctx):
    ...

r = run.rehearse()                # on the double, in a sandbox
print(r.summary, r.approval_url)  # a person approves at the link
```

<details>
<summary><b>CLI and REST</b></summary>

```bash
sd rehearse refund.py --task "Refund everyone who was double-charged"   # exit 0 ready · 2 blocked · 1 error
sd wait <run_id>                                                         # exit 0 only if a person approved and it applied
```

| Call | What it does |
|---|---|
| `POST /api/runs/manual {task, code, workspace?}` | rehearse a plan, then poll `GET /api/runs/{id}` |
| `POST /api/runs/{id}/approve` · `/reject` | a person's decision, with a note for the audit trail |
| `POST /api/runs/{id}/rollback` | rehearse an undo of an applied run |
| `GET /api/runs/{id}/evidence` · `/effects.sql` · `/api/runs.csv` | evidence bundle · SQL export · the whole audit trail |
| `POST /api/workspaces/postgres` · `/vultr` | import a read-only double of your Postgres or Vultr fleet |

Full OpenAPI at `/api/docs`.
</details>

## Safety

Every rehearsal is two new containers on the gVisor runtime, each with its own user-space kernel: no network
(`--network none`), an empty environment (`env -i`), a read-only root, no capabilities, and caps of 256 MB, 64 processes
and 60 seconds. Clones are destroyed after every run. Approval re-checks the current policy, refuses stale or tampered
effects, and replays inside a locked transaction after a row-level drift check.

<details>
<summary><b>Controls</b> (two-person rule, expiry, learned rules, autonomy and more)</summary>

| Control | Default |
|---|---|
| Two-person rule | payouts over $10,000, more than 1,000 rows, and every undo (names compared after Unicode normalisation) |
| Expiry | a rehearsal older than 24 hours can't be approved |
| Learned rules | an AI catch, proven safe, becomes a deterministic check; a violation blocks with no AI call |
| AI jury | three labs; can only make a verdict stricter; overruling an objection needs a written reason |
| Graduated autonomy (off by default) | applies without a person only with no flags, a "looks right" verdict and within a budget (≤ $50, ≤ 20 rows) |
| Protected data | deleting from `customers`, or rewriting over 20% of it, blocks; deleting over 5% of any table blocks |
| Production servers | servers tagged `production` are never deleted, stopped or resized |
| Money and email | over-refunds, double refunds, placeholders, leaked data and marketing to unsubscribed customers block |
| APIs | configured connectors only, https only, allowed methods only, exactly-once delivery with idempotency keys |
</details>

<details>
<summary><b>Attacks we test against</b> (all in CI)</summary>

| Attack | Result |
|---|---|
| `DELETE FROM customers` | the double has 0, production still 1,300; approval locked |
| Exfiltrate data to `evil.example.com` | DNS blocked and reported |
| Memory bomb, fork bomb, disk fill, infinite loop | stopped at the memory, process, file-size and time caps |
| Forge the report, monkeypatch the harness | ignored: a fresh container measures the real change |
| Symlink the database to a host file, or replace it with a FIFO | refused; the host file is never read |
| Tamper with recorded effects after review | the integrity check refuses to apply |
| SQL in a crafted column name | schema changes are never applied |
| Extra email recipients or header injection | refused: exactly one plain customer address |
| Two approvals at the same instant | exactly one apply |
| Customer data to an unknown API, or bulk export to a known one | approval locked as a data leak |
| Read environment secrets | the environment is empty |

Three independent security reviews found 1 critical, 5 high and 11 medium issues, each fixed with a regression test.
Details in [SECURITY.md](SECURITY.md).
</details>

## Proof

| | |
|---|---|
| **12 / 12 · 8 / 8** | the Consequence Engine on the live server: bad plans stopped, correct plans approved, 0 false alarms, the refund trap cut to exactly the right 104 ([eval](docs/VERIFIER_EVAL.md)) |
| **48 / 48** | bad plans caught by the AI jury alone, in earlier live runs, with **0 of 26** false alarms on correct ones ([eval](docs/VERIFIER_EVAL.md)) |
| **3 of 3** | jurors from different labs independently caught every trap on production |
| **187** | API tests in CI (tampered evidence, hidden connections and forged logs among them), plus a real MCP client and an end-to-end browser test against production |
| **1.8 s** | median two-phase rehearsal in gVisor ([benchmark](docs/BENCH.md)) |
| **0** | lines of agent code ever run against production |

## The business case

| | |
|---|---|
| **Buyer** | Heads of Ops, Support and Finance Ops at mid-market SaaS and e-commerce companies that give agents write access |
| **Why now** | Agents act now, and compliance asks for exactly this record: human oversight and logs (EU AI Act Art. 14 and 12), tested and approved changes (SOC 2 CC8.1). Every run's evidence export maps its parts to those controls |
| **ROI** | One caught mistake from the demo ($32,268) pays for a $49 Team seat for almost 55 years |
| **Unit economics** | Measured: ≈ $0.00003 per rehearsal, $0.020–0.044 per three-model jury check, $0 for re-checks and learned rules; **73% gross margin** at full use |
| **Distribution** | Open core: one command deploys it on your own Vultr; one line adds it to Claude Code or Cursor |

The full case, with every number sourced, is in [docs/BUSINESS.md](docs/BUSINESS.md).

## Run it yourself

Requires Docker, Python 3.12+ and Node 22.

```bash
docker build -t stunt-double-sandbox:latest -f sandbox/Dockerfile .
cd api && python -m venv .venv && .venv/bin/pip install -r requirements.txt
VULTR_INFERENCE_KEY=... .venv/bin/uvicorn app.main:app --port 8000    # the key is optional: rules and sandboxes work without it
cd ../web && npm install && npm run dev                                 # http://localhost:3000
```

On Vultr, one command creates the server, then it deploys `main` automatically every two minutes:

```bash
VULTR_API_KEY=... VULTR_INFERENCE_KEY=... python3 infra/provision.py --region sjc --plan vc2-2c-4gb
```

<details>
<summary><b>Repository map</b></summary>

```
api/app/harness/runner.py   inside the sandboxes: phase 1 (run the plan), phase 2 (measure), proof of effect
api/app/engine/             the Consequence Engine: contracts, effect graph, surgical subsets, decision, signed evidence
api/app/sandbox.py          clone → run → copy out safely → measure → destroy
api/app/agent.py            ops agent, AI verifier and jury, deterministic red flags
api/app/main.py             the API: runs, approvals, jury, rules, imports, evidence, stream
api/app/apply.py            drift-checked replay of approved effects
api/app/rules.py            learned rules and their safety checks
api/app/pg_import.py        read-only PostgreSQL doubles
api/app/sql_export.py       drift-guarded SQL export
api/app/vultr_import.py     read-only doubles of a Vultr fleet
api/app/vultr_vm.py         a brand-new Vultr VM per rehearsal (off on the public demo)
mcp/server.py               MCP server (stdio and streamable HTTP)
sdk/python/                 Python SDK and the `sd` CLI
web/                        landing page, console, Mission control, history, policy, outbox, connect
infra/                      Docker Compose, Caddy, Vultr provisioning, pull-deploy
docs/                       business case, evals, benchmark, security, demo script
```
</details>

## Roadmap

**Shipped during the hackathon:** browser doubles with a vision check · doubles of your Vultr fleet and your PostgreSQL ·
the three-lab AI jury · catch → rule with safety checks · instant, labelled re-use of live verdicts · graduated autonomy ·
Mission control · **the Consequence Engine** (intent contracts, effect graph, proof of effect, surgical approval, signed
hash-chained evidence). **Built, off on the public demo:** a brand-new Vultr VM per high-risk rehearsal.
**Next:** GitHub sign-in and Slack approvals · contracts a person edits before the plan runs · Stripe, HubSpot and Zendesk connectors.

## License

MIT, see [LICENSE](LICENSE). Brand logos from [Simple Icons](https://simpleicons.org) (CC0); trademarks belong to their owners.
