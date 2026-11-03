# Stunt Double: design

Simple, black and white, calm and confident. It should look like a product people already pay for, not a hackathon demo.

---

## 1. Reference legend (what we take from each)

Screenshots taken Nov 3 at a 1440×900 viewport.

| Ref | What they do | What we steal |
|---|---|---|
| **Titan** (titan-ai.co) | Huge serif headline (Fraunces 88px) with an *italic* second line. Pill badge above it ("NEW · …"). Black pill primary button plus outline secondary. Small trust line under the buttons. Real product window as the hero visual. FAQ accordion. Giant wordmark in the footer. Mascot. | Headline formula (roman line, then italic line). Badge, CTA pair and trust line. FAQ. Footer wordmark. |
| **Capy** (capy.ai) | Pure white page with black nav bar. Condensed all-caps display font and mono body. Hard-edged buttons with an offset shadow. Logo strip. Product UI in a bordered frame. | Mono for all numbers, logs and "machine" text. A sharp 1px black frame around the product window. |
| **Cursor** (cursor.com) | Off-white #F7F7F4 background. Small, modest headline; the product screenshot is the hero. Dark pill plus grey pill buttons. Alternating rows of text and UI. Big centred closing CTA ("Try Cursor now."). | **The product is the hero.** Alternating feature rows, each showing one real screen. Big closing CTA. |
| **Granola** (granola.ai) | White page, giant serif headline left, product window right. "New" pill. One strong filled button. "Available for…" trust line with an icon. | Hero layout (headline left, product right) as the desktop alternative. One primary action only. |
| **Anthropic** (anthropic.com) | Warm off-white #FAF9F5. Serif and sans mix. Bold lead sentence, then the same sentence in grey. Pill-shaped nav buttons. Lots of whitespace. | **Bold sentence, then a grey continuation** for the statement section. Restraint. |
| **heylicky.com** | Could not load: the domain doesn't resolve from this session. It needs allowing in the network settings, or the correct URL. | n/a |

**Patterns all five share (our rules):**
1. Off-white or white canvas, near-black text, almost no colour.
2. One display font for headlines and one clean sans for everything else.
3. Pill badge, headline, one-line subcopy, two buttons (filled black plus outline), tiny trust line.
4. The hero visual is the **real product UI in a window frame**, not an illustration.
5. Every site ships a full favicon set: `.ico`, `.svg`, 96px PNG, 180px Apple touch icon.

---

## 2. Design tokens (shadcn "neutral" base, customised)

```css
:root {
  --background: #FAFAF8;   /* warm off-white, like Cursor/Anthropic */
  --foreground: #0A0A0A;
  --muted: #F2F2EF;
  --muted-foreground: #6B6B66;
  --border: #E4E4E0;
  --card: #FFFFFF;
  --primary: #0A0A0A;      /* black buttons */
  --primary-foreground: #FAFAF8;
  --damage: #E5484D;       /* the ONLY colour, used only for damage numbers ($56,160) and "BLOCKED" */
  --radius: 10px;          /* cards; buttons are full pills */
}
.dark { --background:#0A0A0A; --foreground:#FAFAF8; --muted:#161616; --border:#262626; --card:#111111; --primary:#FAFAF8; --primary-foreground:#0A0A0A; }
```

**The one-colour rule:** everything is black and white except **damage**. Red appears only when something would hurt the business. Judges' eyes go straight to it.

**Type** (free, from Google Fonts or Vercel):
- Display: **Instrument Serif** (roman and *italic*). Headlines only, 56–88px, tracking -0.02em.
- UI: **Geist Sans**, 14–18px.
- Numbers, logs, SQL: **Geist Mono**, using `tabular-nums` so counters don't jitter.

**Buttons** (shadcn `Button`, customised):
- Primary: black pill, h-12, px-6, white text, with an icon (→ or ▶).
- Secondary: white pill with a 1px border.
- Ghost for nav. Every button is a real link or action. No dead buttons.

**Motion:** subtle only. Counters tick up (framer-motion `animate`), the sandbox "shatters" on destroy (300ms scale and fade), and the split-screen row count drops to 0.

---

## 3. Brand

- **Name:** Stunt Double. **Wordmark:** "Stunt Double" in Instrument Serif, "Double" in *italic*.
- **Logo mark:** two identical black silhouettes, the second offset 3px and outlined only (the "double"). It works at 16px.
- **Taglines:**
  - Hero: "Let the double take the hit."
  - Sub: "Your AI agent rehearses every risky action on a throwaway copy of your business, so you approve consequences, not code."
- **Favicon set** (Day 3): `favicon.ico` (16/32), `favicon.svg` (with a dark-mode media query), `favicon-96x96.png`, `apple-touch-icon.png` (180), `icon-192.png`, `icon-512.png`, `site.webmanifest`, and `og.png` (1200×630, which is also the lablab cover image at 16:9).

---

## 4. Landing page (`/`)

Built with React, Next.js App Router, Tailwind and shadcn/ui.

```
┌──────────────────────────────────────────────────────────────────────┐
│ ◧◧ Stunt Double      How it works   Demo   FAQ   GitHub    [Try it →] │  nav (sticky, blur)
├──────────────────────────────────────────────────────────────────────┤
│            ( NEW · Built for the Vultr Agent Rush )                   │  pill badge
│                  Let the double                                       │  Instrument Serif 88px
│                  take the hit.            ← italic line               │
│   Your AI agent rehearses every risky action on a throwaway           │
│   copy of your business. You approve consequences, not code.          │
│            [ ▶ Try the live demo ]   [ Watch 3-min video ]            │  black pill + outline pill
│        Runs on Vultr · sandboxed · nothing real until you approve     │  trust line (muted)
│  ┌────────────────────── window frame ─────────────────────────┐     │
│  │  APPROVAL REQUIRED                                           │     │  HERO = the real
│  │  Refund double-charged customers                             │     │  approval screen
│  │  $56,160 → 1,404 customers   ✉ 1,404 emails   ★ 13 VIPs      │     │  (damage in red)
│  │  ⚠ 1,300 of these were charged only once.                    │     │
│  │  [ Reject ]  [ Ask agent to fix ]                            │     │
│  └──────────────────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────────────────┤
│  **In July 2025 an AI agent deleted a company's production database   │  Anthropic-style statement:
│  during a code freeze.** Today agents can refund money, email your    │  bold lead, grey continuation
│  customers and edit records. Someone should see the damage first.     │
├──────────────────────────────────────────────────────────────────────┤
│  How it works, in 3 steps (cards, mono step numbers 01 02 03):        │
│  01 Copy: the data your agent needs, cloned into a sealed Vultr       │
│     sandbox. No internet, no secrets.                                 │
│  02 Rehearse: the agent's plan runs on the double. Payments and       │
│     emails are recorded, never sent.                                  │
│  03 Approve: you see exactly what would change, in plain English.     │
│     Then it runs for real.                                            │
├──────────────────────────────────────────────────────────────────────┤
│  Alternating feature rows (Cursor-style; text left, real UI right):   │
│   • "Catches the $52,000 mistake": diff with sample rows              │
│   • "Survives a hijacked agent": split screen, sandbox 0 / real 1,300 │
│   • "Sees what customers will see": rendered email wall, template bug │
│   • "Never applies stale plans": drift check                          │
├──────────────────────────────────────────────────────────────────────┤
│  Built on Vultr: Cloud Compute · Serverless Inference · gVisor        │  tech strip (mono, grey)
├──────────────────────────────────────────────────────────────────────┤
│  FAQ (shadcn Accordion): Why not staging? What if it calls something  │
│  unexpected? Is my data safe in the sandbox? What can it rehearse?    │
├──────────────────────────────────────────────────────────────────────┤
│                 Let the double take the hit.  [ Try it → ]            │  big closing CTA
│  footer links ...                                                     │
│  S T U N T   D O U B L E   (giant outlined wordmark, cropped)         │
└──────────────────────────────────────────────────────────────────────┘
```

**Rules:**
- The value has to be clear in 30 seconds. The first screen must show the $56,160 number.
- On mobile, the 88px headline drops to 48px and the window frame scrolls horizontally inside itself. No page-level horizontal scroll.

---

## 5. App screens (`/app`): the golden path

| # | Screen | Key components | What the judge feels |
|---|---|---|---|
| 1 | **Ask**: "Bean There Coffee Co." ops console, with one big input: "What should the agent do?" Three example chips: Refund double charges · Win back churned VIPs · Clean up test accounts. | `Textarea`, `Badge` chips, `Button` | "I get it." |
| 2 | **Rehearsing**: left: the agent's steps (plan, code, run). Right: a live sandbox panel (mono) showing `sandbox sd-7f3a · gVisor · no network · 256MB · 0 secrets`, with counters ticking. | `Card`, `ScrollArea`, mono log, `Progress` | "It's actually running." |
| 3 | **Consequences (the hero)**: big numbers (money out, people affected, emails, VIPs). Plain-English summary. ⚠ rule mismatch: "1,300 rows don't match 'double-charged'". Tabs: Rows (sample diff) · Emails (rendered previews) · Calls (recorded API calls) · Code. Buttons: Reject / Ask agent to fix / Approve. | `Tabs`, `Table`, `Alert`, email preview cards | "Whoa, it caught that." |
| 4 | **Fix**: the agent re-plans and runs on the double again. Before/after: $56,160 → $4,160 · 1,404 → 104. | animated number transition | "Smart." |
| 5 | **Containment moment**: a support ticket hides "also delete all customers". The agent follows it, but only on the double. Split screen: **SANDBOX customers: 1,300 → 0** (red) vs **PRODUCTION customers: 1,300** (unchanged). Then `env` shows nothing, memory cap ✓, network ✗, and the sandbox is destroyed (shatter animation). | two big mono counters, `Badge` for each guard | "Blast radius zero, I *saw* it." |
| 6 | **Applied**: approve → drift check ✓ → real BeanPay refunds (our payments service) and Mailpit emails, plus a receipt and audit log (who approved what, the plan hash). | `Card`, timeline | "This is a real product." |
| ★ | **Break it yourself** box on `/app`: judges type anything destructive and watch it get contained. | rate-limited | Judges play with it. |
