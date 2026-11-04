# Contributing

Thanks for helping make AI agents safer to say yes to.

## Dev setup
```bash
docker build -t stunt-double-sandbox:latest -f sandbox/Dockerfile .
cd api && python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest -q tests            # engine, adversarial, policy, agent loop
cd ../web && npm install && npm run dev
```

## Ground rules
- **Containment first.** Any change that touches `api/app/harness/`, `api/app/sandbox.py` or `api/app/apply.py`
  needs a test in `api/tests/test_adversarial.py` or `test_engine.py` showing the guarantee still holds.
- **Nothing fake.** Numbers shown in the UI come from real rehearsals. If something isn't wired up, say so in the UI.
- **Phase 2 is trusted code.** It must treat everything from phase 1 as untrusted data.
- Keep the design black and white; red is reserved for damage.

## Commit style
Short imperative subject, then a body explaining *why*. Commits land on `main` through pull requests once the
hackathon is over.
