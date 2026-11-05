# The one-minute demo (shot list)

Everything below is live on https://149-28-206-186.sslip.io. Press **Reset demo** (top right of the console) before
recording. Each click starts a real rehearsal in gVisor on the Vultr VM. The AI catches for the judge steps come back in
about 4 seconds: each was checked live once and the verdict is reused for the identical request, effects and data, with a
visible label and a **Re-check live** button (press it if you want to film the AI investigating; that takes 60–120 s).

| Time | Screen | Click | Say (or caption) |
|---|---|---|---|
| 0:00–0:06 | Landing hero | (none) | "AI agents now move money, email customers, click through admin sites and manage servers. Stunt Double lets them do it to a double first." |
| 0:06–0:14 | `/app` → judge step 1 **Break it** | one click | "This plan deletes every customer. It ran, for real, inside a gVisor sandbox on Vultr: the double lost 1,300 customers. Production still has 1,300. Approval is locked." *(the containment moment)* |
| 0:14–0:26 | step 2 **Watch the AI catch what rules can't** | one click, then cut to the verdict | "This refund plan passes every rule, but the AI verifier on Vultr Serverless Inference reads the data: it refunds 640 people who were never double-charged." Then click **Learn this rule**: "One click and that catch becomes a rule. Next time it's blocked instantly, without AI." |
| 0:26–0:38 | step 3 **Watch it work in a browser** | one click | "Now the agent works in a real browser, on a double of the admin site. Every screen is captured, and the AI vision check sees it cancelled the wrong subscription." |
| 0:38–0:48 | step 4 **Clean up the cloud** | one click, scroll to the fleet | "'Delete idle Vultr servers' would also delete the failover database and the backup runner. The double of the fleet shows the blast radius and the bill; production is protected." |
| 0:48–0:56 | `/control` (Mission control) | (none; start step 2 in another tab first so a live row lights its blue "verify" stage and the counters tick) | "Every agent action, live: the request, its double on Vultr, the decision. Nothing real happens until a human approves the consequences." |
| 0:56–1:00 | Landing closing card | (none) | "Stunt Double. Let the double take the hit." |

Optional extra beats if there is time: **Your Vultr fleet ↗** (top-left card) imports a read-only double of a real Vultr
account from an API key that is never stored, then "Delete every server" shows the blast radius on your own fleet; step 5 (approve a good plan, then rehearse the undo with two approvers), step 6
(the agent on Vultr Inference doing the task itself), the MCP tab on the landing ("works with any agent").

Numbers you can say (all measured on the live server, see docs/VERIFIER_EVAL.md):
48/48 bad plans caught · 0/26 false alarms · browser rehearsal ≈ 6 s, code rehearsal ≈ 1.8 s in gVisor.
