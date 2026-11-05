# The Consequence Engine

Today Stunt Double can say **no**. The Consequence Engine lets it say **"here is exactly why, here is exactly the
part that is right, and here is the promise every plan must keep."** Three mechanisms, each one new, each one
demonstrable in a single click, all built on what already exists (two-phase sandbox, row-level effects, learned rules,
the AI jury).

The challenge asks entries to *plan, dispatch, verify* and rewards the *ability to demonstrate behaviors*. Every
competitor will verify. Nobody else will **verify the verification**, **repair a wrong plan without the agent**, or
**make the agent sign a contract before it writes a line**.

---

## 1. Surgical approval: the wrong plan becomes the right outcome

**The moment.** The agent's refund plan is 86% wrong: 744 refunds, 640 of them to people never double-charged. Today
the only answers are reject, or ask the agent to try again. With the engine, the approval card says:

> **104 of these 744 changes are right.** Approve just those?

One click, and the right 104 refunds and 104 apology emails go out. The 640 never happen. No new plan, no second
AI round trip, no waiting.

**How it works.**
1. The jury's catch (and every learned rule) is a SQL query that returns the *offending rows*.
2. The engine walks the effect graph from those rows: a charge row → its refund (by `charge_id`) → its customer's
   email. That gives the **minimal set to drop** and the **maximal safe subset to keep**.
3. The subset is not trusted either: it is replayed onto a fresh copy **in a new sandbox**, measured by phase 2 like
   any rehearsal, and checked again by every rule (and the jury, cached). Only then is it offered.
4. Approving it binds the approval to the subset's own SHA-256. The original plan is recorded as "partially approved".

**Why it's new.** Agent safety tools are binary: allow or block. This is the first that can **cut the harm out of a
plan and keep the work**, with the cut itself rehearsed and verified.

## 2. Proof of Effect: every number has a reason

**The moment.** The approver clicks "640 wrong refunds" and sees the exact line of the plan that caused them:
`... GROUP BY customer_id, amount_cents, date(created_at) HAVING COUNT(*) > 1`, highlighted, with "this statement changed
640 rows". Every changed row in the explorer gets a **"why"**: the statement that touched it.

**How it works.**
1. In phase 1, the harness records every SQL statement the plan runs (a trace callback on the copy). This log is a
   **claim**, made by untrusted code, and is treated as one.
2. In phase 2, trusted code **replays only those statements**, one by one, on a fresh copy of the "before" data, with
   an authorizer that refuses anything but data changes. After each statement it diffs, so every changed row is
   attributed to the statement that changed it.
3. If the replayed result equals the measured result, the provenance is **proven**. If not, the plan changed something
   it didn't declare (a second connection, a file swap, a disabled trace) and the run is flagged:
   **"N changes the plan can't explain"**. That locks approval.

**Why it's new.** "The plan can't lie" today means we measure what changed. Proof of Effect goes one level deeper:
**we also prove why it changed**, and an agent that hides its tracks is caught by arithmetic, not by trust. Git blame,
for consequences.

## 3. Intent Contracts: the agent signs before it writes

**The moment.** You type "Refund everyone who was double-charged last week." Before any agent writes a plan, Stunt
Double shows three promises in plain English:

> ✓ Only orders with two charges are refunded.
> ✓ Exactly one refund per such order, for the extra charge.
> ✓ Only refunded customers get an apology email.

You approve the contract once (three lines, not code). Then *any* plan, from any agent, any number of retries, is
checked against it deterministically in phase 2, in milliseconds, without asking the AI again.

**How it works.**
1. The jury compiles the request (plus the business glossary) into 2–4 promises, each a plain sentence and an
   after-state SQL check, the same shape as learned rules.
2. Each promise is classified by running it on today's data: 0 rows means a **guard** (must stay 0), some rows means
   an **obligation** (the work to be done, shown as "104 orders need a refund").
3. The human approves the contract. It travels with the run: the agent sees it, phase 2 enforces it, the evidence
   bundle records it.

**Why it's new.** Today's verifiers judge *after* the fact and can be talked into anything. Intent Contracts move the
specification **before the plan exists**, so the agent is measured against what the person meant, written down
before anyone had a reason to bend it. Learned rules are contracts discovered *after* a mistake. Intent contracts are
promises made *before* one.

---

## How the three fit

```mermaid
flowchart LR
    ask["Request"] --> contract["Intent Contract<br/>promises, approved by a person"]
    contract --> plan["Agent writes a plan"]
    plan --> p1["Sandbox 1: run<br/>+ statement log (a claim)"]
    p1 --> p2["Sandbox 2: measure<br/>+ replay the log = Proof of Effect"]
    p2 --> check["Contract + rules + AI jury"]
    check -->|"some rows wrong"| cut["Surgical approval<br/>keep the right subset,<br/>re-rehearse it"]
    check --> human{"A person approves"}
    cut --> human
```

## Checked against the real demo data (before writing a line)

The bad refund plan selects 744 charges; the correct plan selects 104. **All 104 correct charges are inside the 744,
and the other 640 are exactly the wrong ones.** So surgical approval of the bad plan yields precisely the correct
outcome: 104 refunds, $5,136, 104 emails. The demo moment is real, not staged.

**Prototype of Proof of Effect (passed):** SQLite's trace hook records each statement with its bound values expanded;
replaying the log on a fresh copy with the same frozen clock reproduced the measured result exactly; and a write made
after the plan switched the trace off showed up as an unexplained row. The mechanism works before we build it.

**Email linkage on the demo data:** each of the 744 customers has exactly one refund, so every email maps to exactly one
keep-or-drop decision. In general, if one person has both a kept and a dropped change, the email is held back and named
in the card ("1 email needs a person to decide"), never guessed.

**Prototype of an Intent Contract (passed, live on Vultr Serverless Inference).** Given only the request, the glossary
and the schema, `deepseek-v4.1-flash-1017` wrote promises before any plan existed. Each was run on today's data, on
the correct plan's result and on the bad plan's result:

| Promise (the model's own words) | today | correct plan | bad plan |
|---|---|---|---|
| "No charge is refunded unless it belongs to an order that had exactly two charges…" | 0 | 0 | **640** |
| "Every order that had exactly two charges… has exactly one of those charges refunded…" | **104** | 0 | 0 |

The discovery: contracts contain two kinds of promise. **Guards** must hold before and after (the first row: it
catches the exact 640 wrong refunds, deterministically, with no AI at check time). **Obligations** are broken before
and kept after (the second row): they are the work itself. So the contract can say, **before the agent writes a line,
"104 orders need a refund"**, and the approval card can show "obligation met: 104 of 104". Stunt Double knows the
right answer before the agent starts. (`glm-5.3-flash` ran out of tokens on this prompt; the production loop's forced
decision and model fallback already handle that.)

## The hard parts, and the answers

| Risk | Answer |
|---|---|
| The plan disables the statement log, or writes through a second connection | the replay won't match the measurement: **"N changes the plan can't explain"**, approval locks. Tested adversarially |
| Statements that depend on the clock or randomness (`datetime('now')`, `random()`) replay differently | both phases install the same frozen clock and seeded random functions on the copy, so replays are exact |
| Large plans (10,000 statements) | per-statement diffing is capped; above the cap, provenance is proven in batches and attributed per batch |
| Linking a bad row to its refund and its email | refunds carry `charge_id`; emails link through the customer of that charge. Anything that can't be linked is kept out of the subset (fail closed) |
| The subset is itself wrong | it is re-rehearsed in a new sandbox and re-checked by every rule and the jury before it is offered |
| A contract the AI writes is too loose or too strict | it must pass today's data, the human approves it in plain English, and it is shown beside every verdict |

## Build order (1.5 days, then freeze)

| # | What | Why first | Est. |
|---|---|---|---|
| 1 | **Surgical approval** | the most visible demo moment; turns a "no" into a "yes, this much" | ~0.5 day |
| 2 | **Proof of Effect** | deepens the core claim; makes every number clickable | ~0.5 day |
| 3 | **Intent Contracts** | reuses the rules engine; completes the story (before, during, after) | ~0.5 day |

Each ships only with tests (including adversarial ones: a plan that disables the trace, opens a second connection, or
hides a write in a trigger), the full suite green, and the production end-to-end test passing. Then the freeze.
