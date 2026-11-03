# Stunt Double: business case

## One line
Stunt Double lets companies give AI agents write access to money, customers and data, because every risky action is rehearsed on a throwaway copy first and a human approves the **consequences**, not the code.

## Buyer
- **Who signs:** Head of Operations / VP Support / Finance Ops at mid-market SaaS and e-commerce companies (50–2,000 employees) rolling out AI agents with write access to billing, CRM and customer messaging.
- **Who uses it daily:** ops managers and support leads, the people who approve refunds, credits, bulk emails and data cleanups. They aren't engineers.
- **Who champions it:** platform and AI-infrastructure engineers who are asked to "let the agent do it" and are held responsible when it goes wrong.

## The pain
- Agents are moving from answering questions to **taking actions**. Gartner predicts that by 2028, **15% of day-to-day work decisions** will be made autonomously by agentic AI (up from ~0% in 2024).
- The failures are expensive and public. In July 2025 an AI coding agent deleted a company's production database during a code freeze.
- Gartner also expects **over 40% of agentic AI projects to be cancelled by 2027**, citing cost, unclear value and **inadequate risk controls**. Trust is the bottleneck.
- Today's guardrails don't help the approver. Allow-lists and "are you sure?" prompts show code or tool calls. The approver can't tell whether `refund same customer + amount + day` means 104 people or 744.

## Why AI is essential (and why rules alone fail)
- **Rules catch the obvious** ("deletes 100% of customers"), and we have those as hard policy.
- **The expensive mistakes are semantic.** The plan does *what it says* but not *what you meant*. Only a model that reads the request, inspects the real measured outcome and investigates the data can say "640 of these people placed two separate orders; they were not double-charged".
- **The agent fixes itself** in the sandbox using that feedback, so the human sees a corrected plan, not just a warning.

## Market
- AI agents market: about **$7.6–7.8B in 2025**, growing to **about $50B by 2030** (Grand View Research, MarketsandMarkets; ~45% CAGR).
- Our wedge is **agent action safety for business systems**: the control layer every agent with write access needs. Bottom-up illustration: 50,000 mid-market companies × 1 deployment × ~$6k/year ≈ **$300M serviceable market** today, growing with agent adoption. This is an assumption to validate, not a sourced figure.

## Revenue model
| Plan | Price | For |
|---|---|---|
| **Free** | $0: 100 rehearsals / month, 1 approver | trying it with one agent |
| **Team** | $49 per approver / month + $0.02 per rehearsal over 2,000 | ops teams with agents in production |
| **Enterprise** | annual contract | SSO, audit export, on-prem/VPC sandboxes on Vultr, custom policies |

Usage-based pricing (per rehearsal) scales with agent adoption. Seats follow the approvers who get value every day.

## Competition and our angle
| | What it does | Gap |
|---|---|---|
| Staging environments | copy of the app with fake or stale data | consequences depend on **your** data; can't un-send email or un-refund money |
| Dry-run proxies (Foreguard, agent-preflight) | intercept tool calls, show the call | shows the *call*, not the *outcome* across your data |
| Clone-based dev environments (Upsun) | full prod clone for developers | built for engineers, no plain-English consequence review |
| Agent sandboxes (E2B etc.) | isolated code execution | isolation only; no approval, verification or apply |
| **Stunt Double** | rehearse on a clone, measure, verify against intent, approve, replay exact effects with a drift check | approvals for non-engineers, grounded in real numbers |

## Why now, and why Vultr
Cheap, fast, isolated compute (Vultr Cloud Compute + gVisor) makes a full rehearsal per action affordable: ~0.5 s per rehearsal on the demo business. Serverless inference makes a second, independent verifier model practical on every action.

## Roadmap
1. Connectors: Postgres/MySQL (copy-on-write branches), Stripe, HubSpot/Salesforce, Zendesk, SMTP providers.
2. **MCP server**: any agent (Claude Code, Cursor, custom) calls `rehearse()` before acting.
3. Policy packs per department (finance limits, PII rules).
4. Production clones via Vultr Managed Database **forks** for large datasets.

## Sources
- Gartner, agentic AI predictions (15% of daily work decisions by 2028; >40% of agentic AI projects cancelled by 2027): https://www.gartner.com/en/articles/ai-agents-pc1 · https://sdtimes.com/agentic-ai/gartner-more-than-40-of-agentic-ai-projects-will-be-canceled-in-next-few-years/
- AI agents market size (Grand View Research / MarketsandMarkets, via roundup): https://www.raftlabs.com/blog/ai-agents-statistics
- Replit / SaaStr production database incident (July 2025): https://oecd.ai/en/incidents/2025-07-19-1eb1
