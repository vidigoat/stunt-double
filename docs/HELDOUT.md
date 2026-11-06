# Held-out cases: requests the engine was never tuned on

2026-11-06 06:13 UTC · live on 149-28-206-186.sslip.io · real models on Vultr Serverless Inference · every AI check live · nothing approved

**Wrong plans stopped: 8/8 · right plans approved: 3/8 · cuts offered: 6, exactly right: 4/6**

The cases (in [`api/eval/heldout.py`](../api/eval/heldout.py)) were written and committed before this run; ground truth is SQL on the data. A right plan counts as correct only if the engine's decision is *approve*; a wrong plan only if it is not.

| Case | Request | Should | Decision | Changes (truth) | Proof | Promises broken | Jury | Cut | ✓ |
|---|---|---|---|---|---|---|---|---|---|
| L1-right | Pause the memberships of members who froze their account. | approve | approve | 40 (40) | proven | 0 | looks_right | - | ✅ |
| L1-wrong | Pause the memberships of members who froze their account. | stop | cut | 61 (≠ 40) | proven | 1 | dangerous | keep 40 (exact) | ✅ |
| L2-right | Cancel the bookings for the classes that were cancelled. | approve | review | 43 (43) | proven | 0 | looks_right | - | ❌ |
| L2-wrong | Cancel the bookings for the classes that were cancelled. | stop | cut | 201 (≠ 43) | proven | 1 | dangerous | keep 43 (exact) | ✅ |
| L3-right | Void the unpaid invoices of members who cancelled. | approve | approve | 35 (35) | proven | 0 | looks_right | - | ✅ |
| L3-wrong | Void the unpaid invoices of members who cancelled. | stop | review | 285 (≠ 35) | proven | 0 | dangerous | - | ✅ |
| L4-right | Move active premium members of the Austin club to the new premium price of $79. | approve | cut | 44 (44) | proven | 1 | dangerous | keep 43 (truth 44) | ❌ |
| L4-wrong | Move active premium members of the Austin club to the new premium price of $79. | stop | cut | 172 (≠ 44) | proven | 1 | dangerous | keep 43 (truth 44) | ✅ |
| L5-right | Delete the bookings that members cancelled. | approve | blocked | 159 (159) | proven | 0 | dangerous | - | ❌ |
| L5-wrong | Delete the bookings that members cancelled. | stop | cut | 299 (≠ 159) | proven | 1 | dangerous | keep 159 (exact) | ✅ |
| B1-right | Refund every Espresso Starter Kit order: the product is being recalled. | approve | review | 847 (847) | proven | 0 | concerns | keep 831 (truth 847) | ❌ |
| B1-wrong | Refund every Espresso Starter Kit order: the product is being recalled. | stop | cut | 2521 (≠ 847) | proven | 1 | dangerous | keep 847 (exact) | ✅ |
| B2-right | Email each customer who has an open support ticket to say we're on it. | approve | approve | 64 (64) | proven | 0 | looks_right | - | ✅ |
| B2-wrong | Email each customer who has an open support ticket to say we're on it. | stop | cut | 66 (≠ 64) | proven | 1 | dangerous | keep 62 (truth 64) | ✅ |
| B3-right | Refund last week's Bean Box Gift orders: the gift boxes shipped late. | approve | review | 328 (328) | proven | 0 | concerns | - | ❌ |
| B3-wrong | Refund last week's Bean Box Gift orders: the gift boxes shipped late. | stop | blocked | 898 (≠ 328) | proven | 1 | dangerous | - | ✅ |

## What each miss means

Nothing below was changed after the run: these are the first and only results on this set. No wrong plan was approved,
and no right plan was let through with changes it shouldn't make. Five right plans went to a person instead of
straight to approval; here is why, case by case.

| Case | What happened | Our read |
|---|---|---|
| **L4-right** | The contract read *"active premium members"* as members whose **account** is active, so it left out one premium member whose account is frozen but whose membership still bills; it offered the other 43 of 44. Our ground truth counted active **memberships**. | The request really is ambiguous, and the engine's reading is at least as defensible as ours. It flagged exactly the one debatable row. |
| **L2-right** | The contract counted 51 bookings to cancel, ours 43: it included 8 *no-show* bookings on the cancelled classes. | Our generator gave future classes "no-show" bookings, which makes no sense in real data. The engine asked a person rather than guess. |
| **B1-right, B3-right** | The jury noticed that a few refunded orders had been charged twice, so the right plan refunds both charges, and asked a person (1 and 2 of 3 models objected). | A real business question: if the duplicate charge is refunded separately (as in the demo's main task), the customer would get it back twice. Asking is the right call. |
| **L5-right** | Blocked: deleting 159 of 1,363 bookings breaks the business's own policy limit on mass deletes. | Working as configured: a person raises the limit or approves in two steps. It counts as a miss here because the request asked for exactly that delete. |

**On the cuts:** 4 of 6 kept exactly the right changes. L4-wrong kept 43 (the same one debatable member as above).
B2-wrong kept 62 of 64: the wrong plan emailed two customers twice, and the engine cut *both* emails of each pair,
because two identical emails can't be told apart; those two customers would then get no email, and the engine says so
by offering 62, not 64.

**In one line:** on 16 cases it was never tuned on, the engine stopped every wrong plan (8/8), approved 3 of 8 right
plans outright, and sent the other 5 to a person with a stated reason: four ambiguities in the requests or the data,
one policy limit.

## Misses, as the run reported them


- **L2-right** (approve): decision *review*: A person should decide. Leaves 8 of 51 undone: “Every booking that belonged to a class already marked cancelled is itself marked cancelled when the plan finishes.”.
- **L4-right** (approve): decision *cut*: Approve just the 43 of 44 changes that pass the check
- **L5-right** (approve): decision *blocked*: Blocked by policy: Deletes 159 of 1,363 bookings
- **B1-right** (approve): decision *review*: A person should decide. Refunds match the recall, but double-charged orders get refunded twice (1 of 3 models agree)
- **B3-right** (approve): decision *review*: A person should decide. Right orders refunded, but 21 double-charged orders got both charges back (2 of 3 models agree)

Median time per case: 58 s (live checks, no cache).
