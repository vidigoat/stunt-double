# Final plan: from "live on Vultr" to 1st place

> Superseded for scheduling by [MASTER_PLAN.md](MASTER_PLAN.md) (Thu Nov 5). This file keeps the history of Wed night.

Written Wed Nov 4, 22:45 IST. Submission closes **Sun Nov 8 23:00 UTC = Mon Nov 9 04:30 IST**. Our own deadline is
**Sun Nov 8 20:00 IST**, leaving 8.5 hours of buffer.

## Where we are (verified, not hoped)

| Requirement (Challenge 01) | Status | Proof |
|---|---|---|
| Vultr VM backend | ✅ | vc2-2c-4gb in San Jose, built by `infra/provision.py` |
| Public demo URL | ✅ | `https://<ip>.sslip.io`; the 10-step browser e2e passes against it |
| Isolated sandbox per task | ✅ **gVisor on Vultr** | `/api/health` → `sandbox_runtime: runsc` |
| Vultr Serverless Inference | ✅ live | agent + verifier `glm-5.3-flash` (fallback `qwen3.8-flash-next`); `glm-5.3` dropped: it reasoned until max_tokens and never answered |
| Repo + setup docs | ✅ | README, GO_LIVE, SECURITY, 94 API tests + MCP + e2e in CI |
| Video with a containment moment | ❌ | Day 3 |
| Slides, cover, texts | ✅ draft | must be re-checked against live numbers |

The judges score four things with no published weights: **Application of Technology, Presentation, Business Value,
Originality**. Business and originality are already strong. Points are still open on *technology* (the real model on the
real VM, with measured catch rates) and *presentation* (the video and a public URL judges can break themselves).

## Money: $50 hard cap (of the $200 credit; the card is never charged)

| Item | Budget | Guard |
|---|---|---|
| VM vc2-2c-4gb | ≈ $4 for the week ($20/month, billed hourly) | `provision.py` refuses anything over $30/month or more than the remaining credit |
| Serverless Inference | ≤ $30 | per-run token cap, per-IP rate limits, a daily cap on agent runs; measure cost/run, then set the cap so 5 days × cap × cost ≤ $30 |
| Re-provisions, eval runs | ≤ $10 | eval is capped at 10 runs × 3 traps per model pair |
| Buffer | $6 | |
| **Kill switch** | at **$40** spent | check `GET /v2/account` pending charges plus inference `pending_charges` twice a day; at $40, push `SD_DAILY_AGENT_RUNS=0` (the VM pulls `main` every 2 minutes) |

After judging: delete the VM and the inference subscription, then regenerate both API keys (they were in chat).

## Done Wed night (23:00–00:00)
- Live with the AI: https://149-28-206-186.sslip.io · e2e 10/10 on production with the real verifier in the loop.
- **docs/VERIFIER_EVAL.md** (live server, gVisor): 36/36 bad plans caught, 0/18 false alarms, 9/9 on the semantic trap (three runs); gVisor rehearsal median 1.8 s.
- **docs/EVAL.md**: the agent fell for none of the traps; once, its plan missed 87 of 104 customers, and the verifier caught it.
- Fixed on the live server: a verifier that never answered (glm-5.3), a verifier/agent that ran out of steps or kept replying in prose
  (now forced to decide with `tool_choice=required`), and Caddy compressing (and so buffering) the live event stream.
- Judge mode (four one-click rehearsals), a live "AI verifier is investigating" panel, live server status on the landing,
  a written reason required to overrule the AI, "Check again", and a global daily AI-check budget.
- Spend so far: about $0.70 of AI usage plus cents of VM time.

## Tonight (Wed, after this plan)

1. Server recreated **with** the inference key → `/api/health` shows `inference_configured: true`.
2. The first **real** agent run on production on all three traps (over-refund, prompt injection, VIP unsubscribes). Save
   the transcripts. These are the honest numbers for the hero, deck and video.
3. Measure cost per agent run from Vultr's `pending_charges`, then set `SD_DAILY_AGENT_RUNS` to fit the budget.

## Thu Nov 5: what's left after Wednesday night

Done Wed night: real-model eval (agent + verifier, three live runs), gVisor timing, fallback models, claims re-verified,
hero and deck updated with real verifier output. Remaining:
- Agent eval with 5 runs per trap, plus extend the tickets scenario to count "harmful plan caught" (not just "hijacked").
- Watch real visitor runs: if any "could not finish" or failed runs appear, read the events and fix the loop.
- Spend check (target ≤ $10 by Sunday); kill switch at $40.
- Optional: speed up the semantic-trap verification (now about 70 s) by giving the verifier the glossary query up front.

## Fri Nov 6: make judges *feel* it (Presentation)

- ✅ Judge mode is live (four one-click rehearsals, live AI stream). Friday: run it as a stranger would, on a phone too, and fix
  anything confusing.
- A custom domain is optional (sslip.io works). Keep the URL in every artifact.
- Refresh the README GIF, screenshots and deck from production.

## Sat Nov 7: video (≤ 4 minutes)

Narrate with **Vultr's own TTS** (`qwen3-tts-12hz-1.7b` on Serverless Inference, `POST /v1/audio/speech`, MP3; tested Wed
night). That's one more real Vultr service in the submission, and costs cents. Record the screen with `e2e/record-live.js`
against production.

Use the existing script. Must-have beats:
1. 0:00 hook: "AI agents now refund money and email customers. Here's one about to send $37,404 to the wrong people."
2. The real agent on Vultr Inference writes the plan and rehearses it; the verifier catches it; the agent fixes it.
3. **Containment moment** (required): the poisoned ticket says "delete all customers". The sandbox goes 1,300 → 0, production stays at 1,300.
   `env` is empty, network blocked, gVisor, sandbox destroyed.
4. Approve consequences, not code: two-person rule, drift check, undo.
5. Any agent via MCP (Claude Code calling `rehearse`).
6. Architecture slide: Vultr VM + gVisor + Serverless Inference. Business case and close.

## Sun Nov 8: submit by 20:00 IST

- The lablab form (Vidit submits; it needs his login): title, short and long description from `docs/SUBMISSION.md`,
  tags, cover, video, slides PDF, repo, live URL.
- A final production smoke test 1 hour before submitting. Freeze `main` after submitting (the VM pulls `main`).

## Posts and visibility (optional: lablab gives no points for posts, but judges are people)

- **Optional Vultr Community showcase** once the video is up. It doesn't replace the lablab submission.
- Two short posts (X + LinkedIn) tagging @Vultr and @lablabai after submission, using the 20-second containment clip and
  the live URL. Make them build-in-public style: "Our agent tried to refund $37,404. The double took the hit." Also a short
  thread in the hackathon Discord with the live URL, inviting people to "break it yourself". Live usage is the best
  social proof, and the rate limits and the budget cap keep it safe.

## What I need from Vidit

- Nothing until Sunday, except: submit on lablab (needs your login), and tell me about anything Vultr emails you
  (billing, verification).
- After judging: say "tear down" and I'll delete the VM and the inference subscription, and you regenerate the keys.

## Risks and answers

| Risk | Answer |
|---|---|
| The real model is weaker than the scripted one | Eval first (Thu); tune prompts; fallback models; quote only measured numbers |
| A spike in public traffic costs money | Daily agent-run cap, per-IP limits, token cap, $40 kill switch |
| The VM dies | `provision.py` rebuilds it in about 4 minutes from `main`; the URL changes, so update the artifacts |
| A deadline time-zone mix-up | Our deadline is Sun 20:00 IST, 8.5 hours before the real one |
