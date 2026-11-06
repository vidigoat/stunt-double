# The one-minute demo (shot list)

Everything below is live on https://149-28-206-186.sslip.io. Press **Reset demo** (top right of the console) before
recording. Each click starts a real rehearsal in gVisor on the Vultr VM. The AI verdicts for the judge steps come back in
seconds: each was checked live once and is reused for the identical request, effects and data, with a visible label and
a **Re-check live** button (press it to film the jury investigating; that takes one to three minutes).
Timings below were measured on production on Nov 6.

| Time | Screen | Click | Say (or caption) |
|---|---|---|---|
| 0:00–0:06 | Landing hero | (none) | "AI agents now move money, email customers and manage servers. Stunt Double makes them rehearse every action on a double first." |
| 0:06–0:32 | `/app` → judge step 1 **Watch a wrong plan become the right one** (≈5 s) | one click; then **Keep just the 104 that are right** (≈5 s) | "Before the plan exists, the engine writes down what 'refund everyone who was double-charged' means: 104 refunds, nothing else. The plan refunds 744. Replaying it proves line 1 chose the 640 wrong ones. The engine cuts them out, re-rehearses the 104 in a fresh sandbox, and the AI jury agrees: exactly right." *(the 5-step strip at the top tells the story: contract 104 → plan did 744 → statement 1 chose them → keep 104 → the decision)* |
| 0:32–0:42 | step 2 **Break it** (≈4 s) | one click | "This plan deletes every customer. It ran for real in a gVisor sandbox on Vultr: the double lost 1,300 customers. Production still has 1,300. Approval locks." *(the containment moment Challenge 01 asks for)* |
| 0:42–0:50 | step 3 **Try to fool it** (≈4 s) | one click | "This 'read-only audit' quietly refunds 300 charges and forges its own report. A separate sandbox measured the truth: the plan lied." |
| 0:50–0:56 | back on step 1's result: **Verify it in your browser** | one click | "Every decision is sealed in a hash chain signed with Ed25519, and your own browser checks it." |
| 0:56–1:00 | Landing: the strip under the engine (12/12 · 63 → 41 · 8/8) | (none) | "And it isn't one demo: a school it never saw, and held-out cases. Stunt Double. Let the double take the hit." |

Optional extra beats if there is time: **Your Postgres ↗ → "No Postgres handy?"** imports a sample SaaS database in one
click; "Deactivate accounts inactive for 90 days" passes every rule, and the verifier spells out what you'd approve:
49 active accounts; the verifier spells out the revenue at stake ($3,647 a month in its own reading). Approved changes download as drift-guarded SQL; **Your Vultr fleet ↗** (top-left card) imports a read-only double of a real Vultr
account from an API key that is never stored, then "Delete every server" shows the blast radius on your own fleet; step 6 (approve a good plan, then rehearse the undo with two approvers), step 7
(the agent on Vultr Inference gets the contract first, then writes and rehearses its own plan), step 5 ("delete idle
Vultr servers" would remove the failover database), the MCP tab on the landing ("works with any agent").

Numbers you can say (all measured on the live server):
the engine stopped 12/12 bad plans and approved 8/8 correct ones, 0 false alarms ([eval](VERIFIER_EVAL.md)) ·
8/8 wrong plans stopped on 16 held-out cases ([held-out](HELDOUT.md)) · a school's database it never saw, cut 63 → 41
([beyond the demo](BEYOND_THE_DEMO.md)) · the AI jury alone: 48/48 bad plans caught, 0/26 false alarms ·
code rehearsal ≈ 1.8 s in gVisor, browser rehearsal ≈ 6.5 s.
