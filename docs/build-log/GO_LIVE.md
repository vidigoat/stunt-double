# Go-live runbook (the day the Vultr keys arrive)

Everything below is scripted; the order matters because each step de-risks the next.

**Spending rules (the owner's card is linked; it must never be charged):**
- Only the $200 hackathon credit may be used. Check it first: `GET /v2/account` (balance is negative when it's credit) or Billing in the console.
- One VM, `vc2-2c-4gb` (about $20/month). `infra/provision.py` refuses anything over `--max-monthly` (default $30) or more than the remaining credit.
- No Object Storage, backups, extra IPs, load balancers or snapshots unless the owner says yes.
- After judging, and before the credit expires (30 days after signup): destroy the VM and cancel Serverless Inference.

| # | Step | Command | Done when |
|---|---|---|---|
| 1 | Keys in the cloud environment | `VULTR_API_KEY`, `VULTR_INFERENCE_KEY` in environment settings (never in chat) | `env \| grep -c VULTR` → 2 |
| 2 | Check the models are reachable | `curl -s https://api.vultrinference.com/v1/chat/completions -H "Authorization: Bearer $VULTR_INFERENCE_KEY" -H 'content-type: application/json' -d '{"model":"glm-5.3-flash","messages":[{"role":"user","content":"ok"}],"max_tokens":5}'` | a completion comes back |
| 3 | Real agent locally first | run the API with the key, Console → Ask the agent → double-charge request | a plan is rehearsed and a verdict appears |
| 4 | Create the VM | `python3 infra/provision.py --region sjc --plan vc2-2c-4gb` | prints `https://<ip>.sslip.io` |
| 5 | Wait for health | `bash infra/wait-for-site.sh https://<ip>.sslip.io` | `HEALTHY` (gVisor ready + inference configured) |
| 6 | Browser e2e against production | `cd e2e && BASE_URL=https://<host> node golden-path.js` | `E2E OK` |
| 7 | MCP against production | `claude mcp add --transport http stunt-double https://<host>/mcp` then call `rehearse` | consequences + approval_url |
| 8 | Evaluate the real models | `python api/eval/run_eval.py --api https://<host> --runs 10` | `docs/EVAL.md` written; commit it |
| 9 | Benchmark with gVisor | on the VM: `docker compose exec api python eval/bench.py --runs 30` (or locally with `SD_SANDBOX_RUNTIME=runsc`) | update `docs/BENCH.md` |
| 10 | Tune if needed | if the verifier misses the trap in EVAL.md: improve `VERIFIER_SYSTEM`, re-run step 8 | catch rate ≥ 9/10 |
| 11 | Re-verify every claim | `docs/RUBRIC.md` → "claims to re-verify" checklist; landing hero + deck slide 4 use a REAL verifier headline | all boxes ticked |
| 12 | Media | `node e2e/readme-shots.js docs/assets` · `node e2e/deck-shots.js presentation/assets` · `node presentation/export.js` | README + deck show production |
| 13 | Video | add the agent-catch scene to `record-live.js`, `python presentation/video/voice.py`, `bash presentation/video/build.sh` | `stunt-double-demo-voiced.mp4` < 5 min |
| 14 | Submit | lablab form with `docs/SUBMISSION.md`, deck PDF, cover, video, repo, demo URL | before Sun 20:00 IST |

If something breaks on the VM: `ssh` is not needed. The VM pulls `main` every 2 minutes, so a fix is a push.
Logs: add a temporary `/api/health` detail or use the Vultr console's web terminal.
