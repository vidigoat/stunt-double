"""Builds the README's diagrams as animated SVG (GitHub plays CSS animations inside SVG images).

    python3 docs/diagrams/build.py      # writes docs/diagrams/*.svg

One palette and type scale, shared with the landing page and the deck.
"""
import base64
import random
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).parent
ROOT = HERE.parent.parent

PAPER, INK, CARD, LINE = "#FAFAF8", "#0A0A0A", "#FFFFFF", "#E6E6E1"
MUTED, FAINT = "#6B6B66", "#A3A39B"
BLUE, BLUE_SOFT = "#1463FF", "#EAF1FF"
RED, RED_SOFT = "#E5484D", "#FDECEC"
GREEN, GREEN_SOFT = "#12924F", "#E7F6EE"
SERIF = "Georgia, 'Times New Roman', serif"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
VULTR = ("M8.36 2.172A1.194 1.194 0 007.348 1.6H1.2A1.2 1.2 0 000 2.8a1.211 1.211 0 00.182.64l11.6 18.4a1.206 1.206 0 002.035 "
         "0l3.075-4.874a1.229 1.229 0 00.182-.64 1.211 1.211 0 00-.182-.642zm10.349 8.68a1.206 1.206 0 002.035 0L21.8 "
         "9.178l2.017-3.2a1.211 1.211 0 00.183-.64 1.229 1.229 0 00-.183-.64l-1.6-2.526a1.206 1.206 0 00-1.016-.571h-6.148a1.2 "
         "1.2 0 00-1.201 1.2 1.143 1.143 0 00.188.64z")


def _logo_uri() -> str:
    from PIL import Image  # only to shrink the logo once
    import io
    im = Image.open(ROOT / "presentation/img/logo-light.png").convert("RGBA")
    im.thumbnail((96, 96))
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


BASE_CSS = f"""
.flow {{ stroke-dasharray: 6 9; animation: flow 1.2s linear infinite; }}
@keyframes flow {{ to {{ stroke-dashoffset: -30; }} }}
text {{ font-family: {SANS}; }}
"""


def svg(w, h, body, css="", title=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{escape(title)}">
<title>{escape(title)}</title>
<defs>
  <filter id="sh" x="-10%" y="-10%" width="120%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="9" flood-color="#141e50" flood-opacity="0.07"/></filter>
  <marker id="ah" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{BLUE}"/></marker>
  <marker id="ahi" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{INK}"/></marker>
  <marker id="ahr" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{RED}"/></marker>
  <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#EEEEE9" stroke-width="1"/></pattern>
  <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PAPER}" stop-opacity="0"/><stop offset="1" stop-color="{PAPER}" stop-opacity="1"/></linearGradient>
</defs>
<style>{BASE_CSS}{css}</style>
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="22" fill="{PAPER}" stroke="{LINE}"/>
{body}
</svg>
"""


def t(x, y, s, size=16, color=INK, font=SANS, weight=400, anchor="start", italic=False, extra=""):
    st = ' font-style="italic"' if italic else ""
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{color}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{st} {extra}>{s}</text>')


def card(x, y, w, h, fill=CARD, stroke=LINE, r=16, shadow=True, extra=""):
    f = ' filter="url(#sh)"' if shadow else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}"{f} {extra}/>'


def vultr(x, y, size, color=BLUE):
    return f'<path transform="translate({x} {y}) scale({size / 24})" fill="{color}" d="{VULTR}"/>'


def arrow(d, color=BLUE, marker="ah", width=2, flow=True):
    base = f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-opacity="0.25" stroke-linecap="round"/>'
    top = f'<path class="{"flow" if flow else ""}" d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" marker-end="url(#{marker})"/>'
    return base + top


def kicker(x, y, label):
    return f'<circle cx="{x + 5}" cy="{y - 5}" r="4.5" fill="{BLUE}"/>' + t(x + 18, y, escape(label.upper()), 13, MUTED, MONO, 700, extra='letter-spacing="1.5"')


def pill(x, y, w, label, fill=BLUE_SOFT, color=BLUE, size=12.5, h=26):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" fill="{fill}"/>'
            + t(x + w / 2, y + h / 2 + size * 0.36, escape(label), size, color, MONO, 600, "middle"))


def num(x, y, n, fill=BLUE):
    return f'<circle cx="{x}" cy="{y}" r="13" fill="{fill}"/>' + t(x, y + 4.6, str(n), 13, "#FFFFFF", MONO, 700, "middle")


# ---------------------------------------------------------------------------------------------------------------
def hero() -> str:
    W, H = 1200, 660
    cols, rows, pitch, cell = 62, 12, 16, 12.5
    x0, y0 = (W - cols * pitch + (pitch - cell)) / 2, 352
    keep = set(random.Random(7).sample(range(cols * rows), 104))
    css = [".r { fill: %s; animation: cut 9s ease-in-out infinite; }" % RED,
           "@keyframes cut { 0%%, 30%% { fill: %s; opacity: 1; } 42%%, 88%% { fill: #D9D9D2; opacity: .35; } 97%%, 100%% { fill: %s; opacity: 1; } }" % (RED, RED),
           ".g { fill: %s; animation: pop 9s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }" % GREEN,
           "@keyframes pop { 0%, 38% { transform: scale(1); } 44% { transform: scale(1.35); } 52%, 100% { transform: scale(1); } }",
           ".ca { animation: ca 9s ease-in-out infinite; } .cb { animation: cb 9s ease-in-out infinite; }",
           "@keyframes ca { 0%, 32% { opacity: 1; } 40%, 90% { opacity: 0; } 98%, 100% { opacity: 1; } }",
           "@keyframes cb { 0%, 34% { opacity: 0; } 44%, 88% { opacity: 1; } 96%, 100% { opacity: 0; } }"]
    css += [".d%d { animation-delay: %.3fs; }" % (c, c * 0.012) for c in range(cols)]
    sq = []
    for i in range(cols * rows):
        c, r = i % cols, i // cols
        x, y = x0 + c * pitch, y0 + r * pitch
        cls = "g" if i in keep else f"r d{c}"
        sq.append(f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="2.5"/>')
    body = [f'<rect x="1" y="1" width="{W - 2}" height="330" rx="21" fill="url(#grid)"/>',
            f'<rect x="1" y="120" width="{W - 2}" height="212" fill="url(#fade)"/>',
            f'<image href="{_logo_uri()}" x="{W / 2 - 112}" y="30" width="34" height="34"/>',
            t(W / 2 - 68, 57, 'Stunt <tspan font-style="italic">Double</tspan>', 28, INK, SERIF),
            f'<rect x="{W / 2 - 205}" y="84" width="410" height="30" rx="15" fill="{CARD}" stroke="{LINE}"/>',
            vultr(W / 2 - 188, 91, 16),
            t(W / 2 + 10, 104, "Built on Vultr  ·  Agent Rush  ·  Blast Radius Zero", 13.5, MUTED, SANS, 500, "middle"),
            t(W / 2, 200, "Let the double", 78, INK, SERIF, 400, "middle"),
            f'<rect x="{W / 2 - 262}" y="218" width="524" height="100" rx="14" fill="{BLUE}"/>',
            t(W / 2, 294, "take the hit.", 78, "#FFFFFF", SERIF, 400, "middle", italic=True),
            *sq,
            f'<g class="ca">{t(W / 2, 584, "the agent&#8217;s plan: <tspan fill=\"" + RED + "\" font-weight=\"700\">744 refunds · $37,404</tspan>", 21, INK, MONO, 400, "middle")}</g>',
            f'<g class="cb">{t(W / 2, 584, "the engine keeps <tspan fill=\"" + GREEN + "\" font-weight=\"700\">the right 104 · $5,136</tspan> and cuts 640", 21, INK, MONO, 400, "middle")}</g>',
            t(W / 2, 628, "Every action your AI agent wants to take is rehearsed first on a copy of your business. You approve what would happen.",
              16.5, MUTED, SANS, 400, "middle")]
    return svg(W, H, "\n".join(body), "\n".join(css), "Stunt Double: let the double take the hit. 744 planned refunds become the right 104.")


# ---------------------------------------------------------------------------------------------------------------
def architecture() -> str:
    W, H = 1200, 790
    b = [kicker(48, 56, "Architecture · built on Vultr"),
         t(48, 100, 'One Vultr VM. Four AI labs. <tspan font-style="italic" fill="' + BLUE + '">A disposable double for every action.</tspan>', 32, INK, SERIF)]
    # the agent
    b += [card(48, 300, 200, 190),
          t(68, 334, "Your AI agent", 18, INK, SANS, 700),
          t(68, 362, "Claude Code · Cursor", 14.5, MUTED), t(68, 384, "any MCP client", 14.5, MUTED), t(68, 406, "Python SDK · CLI · REST", 14.5, MUTED),
          pill(68, 432, 160, "no approve tool", RED_SOFT, RED, 12)]
    # Cloud Compute frame
    b += [f'<rect x="290" y="140" width="560" height="470" rx="24" fill="#F5F8FF" stroke="{BLUE}" stroke-width="2"/>',
          vultr(312, 158, 22), t(344, 176, "Vultr Cloud Compute", 18, INK, SANS, 700),
          t(830, 176, "vc2-2c-4gb · sjc", 13, MUTED, MONO, 500, "end")]
    for x, w, a, s in [(312, 160, "Caddy", "HTTPS · one host"), (490, 166, "Console", "Next.js · live stream"), (674, 156, "API + MCP", "FastAPI · 8 tools")]:
        b += [card(x, 200, w, 74, shadow=False), t(x + 16, 230, a, 16, INK, SANS, 700), t(x + 16, 254, s, 13, MUTED, MONO)]
    b += [f'<rect x="312" y="296" width="518" height="186" rx="18" fill="none" stroke="{INK}" stroke-width="1.4" stroke-dasharray="7 6"/>',
          f'<rect x="330" y="285" width="178" height="22" fill="#F5F8FF"/>',
          t(340, 301, "SEALED · gVisor (runsc)", 12.5, INK, MONO, 700, extra='letter-spacing="1"'),
          card(334, 320, 220, 120), t(352, 350, "Sandbox 1", 17, INK, SANS, 700),
          t(352, 374, "runs the agent's plan", 14, MUTED), t(352, 394, "on a copy of the business", 14, MUTED), t(352, 420, "no network · no secrets", 12.5, RED, MONO, 600),
          card(590, 320, 220, 120), t(608, 350, "Sandbox 2", 17, INK, SANS, 700),
          t(608, 374, "our code measures", 14, MUTED), t(608, 394, "what really changed", 14, MUTED), t(608, 420, "the plan can't lie", 12.5, GREEN, MONO, 600),
          arrow("M556 380 L586 380"),
          t(571, 466, "256 MB · 64 processes · 60 s · destroyed after every run", 12.5, MUTED, MONO, 500, "middle")]
    b += [card(312, 500, 518, 90, fill=INK, stroke=INK),
          t(334, 532, "Consequence Engine", 18, "#FFFFFF", SANS, 700),
          t(334, 560, "intent contract · effect graph · proof of effect · surgical cut · signed decision", 13.5, "#C9C9C4", MONO)]
    # right column: the other Vultr services
    services = [(140, 190, "Serverless Inference", ["Qwen writes the intent contract", "DeepSeek reads it again to cross-check",
                                                     "AI jury: GLM · DeepSeek · MiniMax", "the ops agent itself"]),
                (350, 120, "Object Storage", ["every sealed rehearsal, archived", "Archival tier · sjc1 · SHA-256"]),
                (490, 120, "Vultr API", ["a read-only double of your fleet", "a fresh VM per risky rehearsal"])]
    for y, h, name, lines in services:
        b += [card(890, y, 262, h, stroke=BLUE), vultr(908, y + 18, 18), t(934, y + 33, name, 16.5, INK, SANS, 700)]
        b += [t(908, y + 62 + i * 24, escape(s), 13.5, MUTED) for i, s in enumerate(lines)]
    # people and production
    b += [card(290, 666, 300, 88, fill=BLUE_SOFT, stroke=BLUE),
          t(312, 700, "A person approves", 17, INK, SANS, 700), t(312, 726, "what would happen, not code", 14, MUTED),
          card(690, 666, 462, 88),
          t(712, 700, "Production", 17, INK, SANS, 700), t(712, 726, "data · payments · email · APIs · Postgres", 14, MUTED),
          t(640, 700, "replay", 12.5, BLUE, MONO, 700, "middle"), t(640, 742, "drift-checked", 12.5, MUTED, MONO, 500, "middle")]
    b += [arrow("M248 395 C 272 395 284 237 310 237"),
          arrow("M830 237 C 858 237 862 230 886 230"),
          arrow("M830 545 C 862 545 860 410 886 410"),
          arrow("M830 560 C 864 560 858 550 886 550"),
          arrow("M571 592 L571 618 C 571 640 440 640 440 662"),
          arrow("M592 710 L686 710")]
    return svg(W, H, "\n".join(b), "", "Architecture: everything runs on Vultr Cloud Compute, Serverless Inference, Object Storage and the Vultr API")


# ---------------------------------------------------------------------------------------------------------------
def rehearsal() -> str:
    W, H = 1200, 430
    steps = [("Copy", ["a fresh copy of the", "data the plan needs"], CARD),
             ("Rehearse", ["the plan runs on the", "copy, sealed, offline"], BLUE_SOFT),
             ("Measure", ["a fresh sandbox runs", "only our code"], BLUE_SOFT),
             ("Verify", ["rules, the contract", "and a 3-lab AI jury"], CARD),
             ("Approve", ["a person approves", "what would happen"], CARD),
             ("Replay", ["only those changes", "go live, drift-checked"], GREEN_SOFT)]
    w, gap, x0, y = 166, 20, 52, 180
    b = [kicker(48, 56, "How a rehearsal works"),
         t(48, 100, 'Rehearse. Measure. <tspan font-style="italic" fill="' + BLUE + '">Then approve.</tspan>', 32, INK, SERIF),
         f'<rect x="{x0 + w + gap - 12}" y="{y - 34}" width="{2 * w + gap + 24}" height="{170 + 46}" rx="20" fill="none" stroke="{INK}" stroke-width="1.4" stroke-dasharray="7 6"/>',
         f'<rect x="{x0 + w + gap + 6}" y="{y - 45}" width="178" height="22" fill="{PAPER}"/>',
         t(x0 + w + gap + 16, y - 29, "SEALED · gVisor (runsc)", 12.5, INK, MONO, 700, extra='letter-spacing="1"')]
    for i, (name, lines, fill) in enumerate(steps):
        x = x0 + i * (w + gap)
        stroke = GREEN if fill == GREEN_SOFT else (BLUE if fill == BLUE_SOFT else LINE)
        b += [card(x, y, w, 150, fill=fill, stroke=stroke, extra=f'class="st s{i}"'), num(x + 28, y + 32, i + 1, GREEN if i == 5 else BLUE),
              t(x + 50, y + 38, name, 18, INK, SANS, 700)]
        b += [t(x + 18, y + 82 + j * 22, escape(s), 14, MUTED) for j, s in enumerate(lines)]
        if i < 5:
            b.append(arrow(f"M{x + w + 2} {y + 75} L{x + w + gap - 2} {y + 75}"))
    b += [t(W / 2, 392, "median 1.8 s per rehearsal  ·  0 lines of agent code ever run on production  ·  big changes need two people",
            14, MUTED, MONO, 500, "middle")]
    css = ".st { animation: hl 7.2s ease-in-out infinite; } @keyframes hl { 0%, 14%, 100% { stroke-width: 1; } 4%, 10% { stroke-width: 3; } }"
    css += "".join(f" .s{i} {{ animation-delay: {i * 1.2:.1f}s; }}" for i in range(6))
    return svg(W, H, "\n".join(b), css, "How a rehearsal works: copy, rehearse, measure, verify, approve, replay")


# ---------------------------------------------------------------------------------------------------------------
def engine() -> str:
    W, H = 1200, 500
    cards = [("Intent contract", "104", BLUE, ["refunds to do, written", "before the plan existed"], "DeepSeek agrees: 104"),
             ("Effect graph", "744", INK, ["units of work: a charge,", "its refund, its email"], "linked by keys"),
             ("Proof of effect", "640", RED, ["wrong refunds, all", "chosen by line 1"], "1,490 statements replayed"),
             ("Surgical cut", "104", GREEN, ["kept ($5,136); 640 cut", "($32,268), re-run fresh"], "re-measured in gVisor"),
             ("Signed decision", "6/6", GREEN, ["layers pass; sealed", "with Ed25519"], "archived on Vultr")]
    w, gap, x0, y = 204, 20, 52, 196
    b = [kicker(48, 56, "The Consequence Engine"),
         t(48, 100, 'Not just a sandbox. <tspan font-style="italic" fill="' + BLUE + '">It proves which part is right.</tspan>', 32, INK, SERIF),
         t(48, 140, "On one real request: &#8220;Refund everyone who was double-charged last week.&#8221;", 17, MUTED, SANS, 400, extra='font-style="italic"')]
    for i, (name, big, color, lines, chip) in enumerate(cards):
        x = x0 + i * (w + gap)
        b += [card(x, y, w, 236, extra=f'class="ec e{i}"'), num(x + 28, y + 32, i + 1, color if color != INK else BLUE),
              t(x + 50, y + 38, name, 16.5, INK, SANS, 700),
              t(x + 20, y + 118, big, 58, color, SERIF)]
        b += [t(x + 20, y + 154 + j * 21, escape(s), 13.5, MUTED) for j, s in enumerate(lines)]
        b.append(pill(x + 18, y + 196, w - 36, chip, BLUE_SOFT if i != 2 else RED_SOFT, BLUE if i != 2 else RED, 11.5))
        if i < 4:
            b.append(arrow(f"M{x + w + 2} {y + 118} L{x + w + gap - 2} {y + 118}"))
    b.append(t(W / 2, 470, "744 planned  →  104 approved, every claim proven, live on Vultr in about 8 seconds", 15, INK, MONO, 600, "middle"))
    css = ".ec { animation: ring 7.5s ease-in-out infinite; } @keyframes ring { 0%, 16%, 100% { stroke: #E6E6E1; stroke-width: 1; } 5%, 11% { stroke: #1463FF; stroke-width: 3; } }"
    css += "".join(f" .e{i} {{ animation-delay: {i * 1.5:.1f}s; }}" for i in range(5))
    return svg(W, H, "\n".join(b), css, "The Consequence Engine: contract 104, effect graph 744, proof 640 chosen by line 1, cut to 104, signed decision")


# ---------------------------------------------------------------------------------------------------------------
def containment() -> str:
    W, H = 1200, 420
    b = [kicker(48, 56, "Containment · Challenge 01"),
         t(48, 100, 'The blast radius is <tspan font-style="italic" fill="' + BLUE + '">zero.</tspan>', 32, INK, SERIF),
         card(48, 150, 470, 210, fill=RED_SOFT, stroke=RED), t(76, 190, "THE DOUBLE", 13, RED, MONO, 700, extra='letter-spacing="1.5"'),
         f'<g class="n1">{t(76, 290, "1,300", 92, INK, SERIF)}</g>',
         f'<g class="n0">{t(76, 290, "0", 92, RED, SERIF)}</g>',
         t(76, 330, "customers, after the plan ran DELETE FROM customers", 14.5, MUTED),
         f'<rect x="562" y="140" width="16" height="230" rx="8" fill="{INK}"/>',
         t(570, 396, "gVisor wall", 13, INK, MONO, 700, "middle"),
         card(622, 150, 530, 210), t(650, 190, "PRODUCTION", 13, MUTED, MONO, 700, extra='letter-spacing="1.5"'),
         t(650, 290, "1,300", 92, INK, SERIF),
         t(650, 330, "customers, untouched. Nothing real happened.", 14.5, MUTED),
         pill(938, 172, 190, "approval locked", RED_SOFT, RED, 12.5, 28),
         f'<g class="hit">{t(384, 136, "DELETE FROM customers", 15, RED, MONO, 700, "middle")}</g>']
    css = (".n1 { animation: n1 6s infinite; } .n0 { animation: n0 6s infinite; } .hit { animation: hit 6s infinite; }"
           "@keyframes n1 { 0%, 30% { opacity: 1; } 36%, 94% { opacity: 0; } 100% { opacity: 1; } }"
           "@keyframes n0 { 0%, 30% { opacity: 0; } 36%, 94% { opacity: 1; } 100% { opacity: 0; } }"
           "@keyframes hit { 0% { opacity: 0; } 10%, 34% { opacity: 1; } 44%, 100% { opacity: 0; } }")
    return svg(W, H, "\n".join(b), css, "Containment: the double drops from 1,300 customers to 0; production keeps all 1,300")


# ---------------------------------------------------------------------------------------------------------------
def evidence() -> str:
    W, H = 1200, 420
    steps = ["request", "contract", "rehearsal", "measured", "proof", "decision", "approval"]
    w, gap, x0, y = 128, 26, 48, 160
    b = [kicker(48, 56, "Signed evidence"),
         t(48, 100, 'Every step sealed. <tspan font-style="italic" fill="' + BLUE + '">Change one cent and it breaks.</tspan>', 32, INK, SERIF)]
    for i, s in enumerate(steps):
        x = x0 + i * (w + gap)
        bad = ' class="bad"' if i >= 2 else ""
        b += [f'<g{bad}>' + card(x, y, w, 96) + "</g>",
              t(x + 16, y + 34, s, 16, INK, SANS, 700),
              t(x + 16, y + 60, "sha256", 12, FAINT, MONO), t(x + 16, y + 78, f"{(0x3f2a91 * (i + 3)) & 0xffffff:06x}…", 12, MUTED, MONO)]
        if i < 6:
            b.append(f'<g{" class=\"badl\"" if i >= 2 else ""}><path d="M{x + w + 3} {y + 48} L{x + w + gap - 3} {y + 48}" stroke="{BLUE}" stroke-width="2.5" marker-end="url(#ah)"/></g>')
    b += [pill(x0, y + 116, 240, "signed with Ed25519", BLUE_SOFT, BLUE, 12.5, 28),
          f'<g class="msg">{t(x0 + 262, y + 136, "one cent changed in the rehearsal: steps 3–7 no longer verify", 14, RED, MONO, 700)}</g>',
          card(48, 330, 1104, 62, stroke=BLUE), vultr(70, 349, 22),
          t(104, 368, "Vultr Object Storage", 16, INK, SANS, 700),
          t(286, 368, "every sealed rehearsal is archived (Archival tier, sjc1) and downloadable from the console", 14, MUTED),
          arrow("M1036 262 L1036 326", flow=False)]
    css = (".bad rect { animation: bad 7s infinite; } .badl path { animation: badl 7s infinite; } .msg { animation: msg 7s infinite; }"
           "@keyframes bad { 0%, 40% { stroke: #E6E6E1; fill: #FFFFFF; } 46%, 86% { stroke: #E5484D; fill: #FDECEC; } 92%, 100% { stroke: #E6E6E1; fill: #FFFFFF; } }"
           "@keyframes badl { 0%, 40% { stroke: #1463FF; } 46%, 86% { stroke: #E5484D; } 92%, 100% { stroke: #1463FF; } }"
           "@keyframes msg { 0%, 42% { opacity: 0; } 48%, 86% { opacity: 1; } 92%, 100% { opacity: 0; } }")
    return svg(W, H, "\n".join(b), css, "Signed evidence: a hash chain of seven steps signed with Ed25519, archived on Vultr Object Storage")


if __name__ == "__main__":
    for name, fn in [("hero", hero), ("architecture", architecture), ("rehearsal", rehearsal), ("engine", engine),
                     ("containment", containment), ("evidence", evidence)]:
        (HERE / f"{name}.svg").write_text(fn())
        print(f"docs/diagrams/{name}.svg")
