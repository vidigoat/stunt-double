# Rehearsal latency

`python api/eval/bench.py --runs 15`: a full rehearsal = clone the business DB → phase 1 container runs the plan →
copy out safely → phase 2 container measures the diff and audits side effects → destroy. No AI involved.

| Plan | p50 | p95 | phase 1 (plan) p50 |
|---|---|---|---|
| correct refund plan (104 refunds + emails) | 0.80 s | 1.16 s | 0.36 s |
| destructive plan (`DELETE FROM customers`) | 0.78 s | 0.82 s | 0.35 s |
| empty plan | 0.77 s | 0.81 s | 0.34 s |

Measured Nov 4 in the development container (Docker `runc`, 1,300 customers / 5,290 charges).
To re-measure on the Vultr VM with gVisor: `SD_SANDBOX_RUNTIME=runsc python api/eval/bench.py --runs 30`. The gVisor
numbers from the live VM are below; later eval runs, with Proof of Effect replay added, measured medians of 1.8–3.1 s.

## On the live Vultr VM with gVisor (Wed Nov 4, 18:55 UTC)

Measured from 12 real rehearsals on the production server (vc2-2c-4gb, San Jose, `runsc`), recorded by
`api/eval/verifier_eval.py`: **median 1,810 ms, p90 3,020 ms** per rehearsal, covering both sandbox phases from container
start to destroy. That's the price of a user-space kernel plus a fresh, trusted measuring container per run. In the
end-to-end time an approver waits, the AI verifier's investigation dominates (median 8–70 s depending on the plan; see
`docs/VERIFIER_EVAL.md`).

