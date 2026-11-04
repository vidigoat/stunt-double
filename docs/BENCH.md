# Rehearsal latency

`python api/eval/bench.py --runs 15`: a full rehearsal = clone the business DB → phase 1 container runs the plan →
copy out safely → phase 2 container measures the diff and audits side effects → destroy. No AI involved.

| Plan | p50 | p95 | phase 1 (plan) p50 |
|---|---|---|---|
| correct refund plan (104 refunds + emails) | 0.80 s | 1.16 s | 0.36 s |
| destructive plan (`DELETE FROM customers`) | 0.78 s | 0.82 s | 0.35 s |
| empty plan | 0.77 s | 0.81 s | 0.34 s |

Measured Nov 4 in the development container (Docker `runc`, 1,300 customers / 5,290 charges).
To re-measure on the Vultr VM with gVisor: `SD_SANDBOX_RUNTIME=runsc python api/eval/bench.py --runs 30`
(gVisor adds some start-up overhead; update this table with those numbers before submitting).
