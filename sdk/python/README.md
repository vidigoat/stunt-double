# stunt-double (Python SDK)

```python
from stunt_double import StuntDouble

sd = StuntDouble("https://<your-host>")

@sd.plan("Refund everyone who was double-charged last week")
def run(ctx):
    for charge_id, amount in ctx.db.execute("SELECT id, amount_cents FROM charges WHERE ...").fetchall():
        ctx.payments.refund(charge_id, amount, "duplicate charge")

r = run.rehearse()                 # runs on a throwaway copy in an isolated sandbox
print(r.summary)                   # "If approved: $5,136.00 across 104 refunds, 104 emails, 104 rows changed."
if r.blocked:                      # policy said no: fix the plan
    print(r.blocked_by_policy)
else:
    print("Ask a human:", r.approval_url)
    final = sd.wait_for_decision(r.run_id)   # 'applied', 'rejected', 'drifted' or 'failed'
```

There is no `approve()` on purpose: an agent can never approve its own plan.
