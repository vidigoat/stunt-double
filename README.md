# Stunt Double

**Let the double take the hit.** Before an AI agent does something risky to a real business (refunding money, emailing customers, deleting records), Stunt Double rehearses the plan on a throwaway copy of the business inside an isolated Vultr sandbox. A human sees the consequences in plain English, and nothing real happens until they approve.

Built for the **Vultr: Agent Rush** hackathon (lablab.ai, Nov 3–8 2026), Challenge 01, **Blast Radius Zero**: *plan, dispatch, verify*.

> 🚧 Under active development during the hackathon. See [`docs/PLAN.md`](docs/PLAN.md) and [`docs/DESIGN.md`](docs/DESIGN.md).

## Architecture (target)
- **Vultr Cloud Compute VM**: hosts the web app, API and sandboxes
- **Vultr Serverless Inference**: the agent's LLM calls (plan, code, self-fix, explain)
- **Isolated sandbox**: Docker + gVisor, no network, no secrets, memory and time caps, destroyed after every run
- **web/**: Next.js + React + shadcn/ui (landing page + app)
- **api/**: FastAPI orchestrator (agent loop, rehearsal runner, apply + drift check)
- **sandbox/**: the rehearsal image
- **infra/**: docker compose + Caddy

## License
MIT
