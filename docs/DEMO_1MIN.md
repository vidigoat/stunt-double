# The one-minute demo (shot list)

Everything below is live on https://149-28-206-186.sslip.io. Press **Reset demo** (top right of the console) before
recording. Each click starts a real rehearsal in gVisor on the Vultr VM. The AI catches for the judge steps come back in
about 4 seconds: each was checked live once and the verdict is reused for the identical request, effects and data, with a
visible label and a **Re-check live** button (press it if you want to film the AI investigating; that takes 60–120 s).

| Time | Screen | Click | Say (or caption) |
|---|---|---|---|
| 0:00–0:06 | Landing hero | (none) | "AI agents now move money, email customers and manage servers. Stunt Double makes them rehearse every action on a double first." |
| 0:06–0:13 | `/app` → judge step 1 **Break it** | one click | "This plan deletes every customer. It ran for real, in a gVisor sandbox on Vultr: the double lost 1,300 customers. Production still has 1,300. Approval locks." *(the containment moment)* |
| 0:13–0:22 | step 2 **Try to fool it** | one click, scroll to the claim panel | "This 'read-only audit' quietly refunds 300 charges and says it changed nothing. It even forges its own report. A separate sandbox measured the truth: the plan lied." |
| 0:22–0:38 | step 3 **Watch the AI catch what rules can't, then teach it** | one click; **Learn this rule**; **Try the same plan again** | "This refund plan passes every rule. A jury of three AI labs on Vultr Inference investigates the data on its own: 640 of these people were never double-charged. One click turns the catch into a rule, and the same plan is now blocked in seconds, without AI." |
| 0:38–0:46 | step 5 **Clean up the cloud** | one click | "'Delete idle Vultr servers' would delete the failover database. Two jurors overruled the first verdict and made it stricter." |
| 0:46–0:56 | step 8 **Try it on real infrastructure**, then `/control` | one click | "It works on your own Postgres and your own Vultr fleet, read-only, and every action shows up live in Mission control." |
| 0:56–1:00 | Landing closing card | (none) | "Stunt Double. Let the double take the hit." |

Optional extra beats if there is time: **Your Postgres ↗ → "No Postgres handy?"** imports a sample SaaS database in one
click; "Deactivate accounts inactive for 90 days" passes every rule, and the verifier spells out what you'd approve:
49 paying accounts worth $3,451/month. Approved changes download as drift-guarded SQL; **Your Vultr fleet ↗** (top-left card) imports a read-only double of a real Vultr
account from an API key that is never stored, then "Delete every server" shows the blast radius on your own fleet; step 5 (approve a good plan, then rehearse the undo with two approvers), step 6
(the agent on Vultr Inference doing the task itself), the MCP tab on the landing ("works with any agent").

Numbers you can say (all measured on the live server, see docs/VERIFIER_EVAL.md):
48/48 bad plans caught · 0/26 false alarms · browser rehearsal ≈ 6 s, code rehearsal ≈ 1.8 s in gVisor.
