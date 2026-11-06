"""Build the Stunt Double deck as a native, editable PowerPoint file.

Every headline, number and label is a real text box; cards are shapes; the market chart is a native chart; the
744 units of work are 744 shapes. Fonts: Fraunces, DM Sans, Geist Mono (TTF copies in presentation/fonts).

    python3 presentation/build_deck.py        # writes presentation/StuntDouble.pptx
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
OUT = HERE / "StuntDouble.pptx"

# ---- design tokens (the landing page's) -----------------------------------------------------------------------
PAPER, INK, CARD = "FAFAF8", "0A0A0A", "FFFFFF"
BLUE, BLUE_SOFT, BLUE_ON_DARK = "1463FF", "EAF1FF", "6A95FF"
RED, RED_SOFT, RED_ON_DARK = "E5484D", "FDECEC", "FF6B70"
GREEN, GREEN_SOFT, GREEN_ON_DARK = "12924F", "E7F6EE", "3FCF86"
MUTED, FAINT, LINE = "6B6B65", "A3A39B", "E6E6E1"
D_CARD, D_LINE, D_MUTED = "151514", "2C2C2A", "A9A9A3"
SERIF, SANS, MONO = "Fraunces", "DM Sans", "Geist Mono"
W, H = 13.333, 7.5
MX = 0.85                                  # side margin
TOTAL = 10

# The 104 units the engine kept, out of 744 (one real rehearsal of the naive refund plan; same data as the landing page).
KEPT = {0, 11, 26, 32, 34, 40, 43, 58, 64, 66, 94, 104, 106, 108, 115, 118, 127, 134, 135, 159, 161, 169, 175, 183, 186,
        188, 192, 203, 205, 208, 213, 227, 231, 233, 271, 272, 273, 276, 280, 282, 288, 296, 298, 300, 302, 314, 315, 334,
        336, 339, 345, 353, 356, 361, 362, 364, 383, 388, 403, 409, 421, 422, 425, 432, 438, 441, 449, 459, 461, 462, 468,
        485, 501, 514, 532, 535, 539, 552, 553, 558, 573, 574, 576, 594, 610, 616, 618, 620, 623, 632, 650, 651, 654, 659,
        678, 693, 695, 697, 702, 718, 719, 733, 738, 739}


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


def flat(shape):
    """Drop the theme's shape style (it adds a drop shadow in some renderers): fill and line are set explicitly."""
    st = shape._element.find(qn("p:style"))
    if st is not None:
        shape._element.remove(st)
    return shape


# ---- primitives -----------------------------------------------------------------------------------------------
def bg(slide, color: str) -> None:
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = rgb(color)


def box(slide, x, y, w, h, fill: str | None = CARD, line: str | None = LINE, radius: float = 0.18, width: float = 0.75):
    """A rounded card. radius in inches."""
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    if radius:
        s.adjustments[0] = min(0.5, radius / min(w, h))
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(width)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    s.text_frame.text = ""
    return flat(s)


def oval(slide, x, y, d, fill: str):
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    s.line.fill.background()
    s.shadow.inherit = False
    return flat(s)


def text(slide, x, y, w, h, paras, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing: float | None = None):
    """paras: list of paragraphs; each a list of runs (text, font, size, color, {bold, italic})."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, runs in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing:
            p.line_spacing = spacing
        for r in runs:
            t, font, size, color = r[:4]
            opts = r[4] if len(r) > 4 else {}
            run = p.add_run()
            run.text = t
            run.font.name = font
            run.font.size = Pt(size)
            run.font.color.rgb = rgb(color)
            run.font.bold = opts.get("bold", False)
            run.font.italic = opts.get("italic", False)
    return tb


def R(t, font=SANS, size=16, color=INK, **o):
    return (t, font, size, color, o)


def kicker(slide, label: str, dark=False, y=0.62):
    text(slide, MX, y, 9, 0.3, [[R("●  ", MONO, 10.5, BLUE), R(label.upper(), MONO, 10.5, D_MUTED if dark else MUTED)]])


def headline(slide, parts, dark=False, y=0.98, size=40, w=11.6, h=1.5):
    """parts: list of lines; each line a list of (text, accent?) pairs."""
    ink, acc = ("FAFAF8", BLUE_ON_DARK) if dark else (INK, BLUE)
    paras = [[R(t, SERIF, size, acc if a else ink, italic=a) for t, a in line] for line in parts]
    text(slide, MX, y, w, h, paras, spacing=0.92)


def underline(slide, y):
    box(slide, MX, y, 0.58, 0.045, fill=BLUE, line=None, radius=0.02)


def footer(slide, n: int, dark=False, left="Stunt Double  ·  live on Vultr"):
    c = "5C5C58" if dark else FAINT
    text(slide, MX, H - 0.48, 8, 0.25, [[R(left, MONO, 9, c)]])
    text(slide, W - MX - 2, H - 0.48, 2, 0.25, [[R(f"{n:02d} / {TOTAL}", MONO, 9, c)]], align=PP_ALIGN.RIGHT)


def notes(slide, s: str) -> None:
    slide.notes_slide.notes_text_frame.text = s


def chip(slide, x, y, label, dark=False, color=None, w=None):
    w = w or (0.16 + 0.085 * len(label))
    box(slide, x, y, w, 0.34, fill=D_CARD if dark else CARD, line=D_LINE if dark else LINE, radius=0.17)
    text(slide, x, y + 0.075, w, 0.25, [[R(label, MONO, 9.5, color or ("DDDDDA" if dark else MUTED))]], align=PP_ALIGN.CENTER)
    return w


# ---- slides ---------------------------------------------------------------------------------------------------
def s01_cover(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    # logo mark: you (ink) and your double (blue outline), offset
    lx, ly = W / 2 - 1.45, 1.0
    oval(s, lx, ly + 0.02, 0.34, INK)
    o = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(lx + 0.17), Inches(ly - 0.06), Inches(0.34), Inches(0.34))
    o.fill.background(); o.line.color.rgb = rgb(BLUE); o.line.width = Pt(2.25); o.shadow.inherit = False; flat(o)
    text(s, lx + 0.66, ly - 0.08, 3, 0.5, [[R("Stunt ", SERIF, 26, INK), R("Double", SERIF, 26, INK, italic=True)]])
    text(s, 0.5, 2.0, W - 1, 1.3, [[R("Let the double", SERIF, 84, INK)]], align=PP_ALIGN.CENTER)
    box(s, 2.95, 3.38, 7.43, 1.5, fill=BLUE, line=None, radius=0.12)
    text(s, 2.95, 3.38, 7.43, 1.45, [[R("take the hit.", SERIF, 84, "FFFFFF", italic=True)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    box(s, 2.0, 5.35, 9.33, 0.62, fill=CARD, line=LINE, radius=0.31)
    text(s, 2.0, 5.35, 9.33, 0.62, [[R("$37,404 → 744 refunds", MONO, 14, RED), R("  caught in rehearsal  ·  ", MONO, 14, MUTED),
                                      R("$5,136 → the right 104", MONO, 14, INK)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 0.5, 6.2, W - 1, 0.35, [[R("Every action an AI agent takes, rehearsed on a copy of your business first, on Vultr. You approve consequences, not code.", SANS, 13, MUTED)]], align=PP_ALIGN.CENTER)
    footer(s, 1, left="Vultr: Agent Rush  ·  Challenge 01: Blast Radius Zero  ·  149-28-206-186.sslip.io")
    notes(s, "In the movies, the star never jumps from the burning building. The stunt double does. "
             "Stunt Double gives every AI agent a double of your business to take the hit first.")


def s02_problem(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    kicker(s, "The problem")
    headline(s, [[("Agents stopped answering.", False)], [("They started acting.", True)]], h=1.7)
    underline(s, 2.62)
    y = 3.05
    for i, (when, what, src) in enumerate([
        ("JULY 2025", "An AI agent deleted a company's production database, during a code freeze.", "eWeek, July 2025"),
        ("SPRING 2026", "Another deleted a startup's database and its backups, in nine seconds.", "Information Age, May 2026"),
    ]):
        yy = y + i * 1.88
        box(s, MX, yy, 6.9, 1.7)
        text(s, MX + 0.32, yy + 0.25, 6.3, 0.3, [[R(when, MONO, 11, RED)]])
        text(s, MX + 0.32, yy + 0.58, 6.3, 0.8, [[R(what, SERIF, 20, INK)]], spacing=1.05)
        text(s, MX + 0.32, yy + 1.32, 6.3, 0.25, [[R(src, MONO, 9, FAINT)]])
    x = MX + 7.15
    dw = W - MX - x
    box(s, x, y, dw, 3.58, fill=INK, line=None, radius=0.2)
    for i, (n, l) in enumerate([("15%", "of day-to-day work decisions made by AI agents by 2028, up from 0% in 2024"),
                                 ("40%+", "of agentic AI projects cancelled by 2027, partly for inadequate risk controls")]):
        yy = y + 0.26 + i * 1.52
        text(s, x + 0.35, yy, dw - 0.7, 0.8, [[R(n, MONO, 46, "FAFAF8")]])
        text(s, x + 0.35, yy + 0.76, dw - 0.7, 0.7, [[R(l, SANS, 12.5, "C9C9C4")]], spacing=1.08)
    text(s, x + 0.35, y + 3.25, dw - 0.7, 0.25, [[R("Gartner, Oct 2024 and Jun 2025", MONO, 9, "77776F")]])
    footer(s, 2)
    notes(s, "AI agents don't just answer any more. They refund customers, send email, delete servers. "
             "In July 2025 one deleted a company's production database during a code freeze; this spring another wiped a "
             "database and its backups in nine seconds. Gartner expects agents to make 15% of daily work decisions by 2028, "
             "and expects 40% of agent projects to be cancelled, partly for lack of risk controls.")


def s03_gap(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    kicker(s, "Today's human in the loop")
    headline(s, [[("Approval shows a manager", False)], [("code they can't read.", True)]], h=1.7)
    underline(s, 2.62)
    y, hh = 3.05, 3.55
    # left: what approvers see today
    box(s, MX, y, 5.25, hh, fill="F1F1EE", line=LINE)
    text(s, MX + 0.32, y + 0.28, 4.7, 0.3, [[R("WHAT THEY SEE TODAY", MONO, 10.5, MUTED)]])
    code = ["def run(ctx):", "  rows = ctx.db.execute(\"\"\"", "    SELECT c.id, c.amount_cents", "    FROM charges c JOIN (", "      SELECT customer_id, ...", "      HAVING COUNT(*) > 1) d", "    ON ...\"\"\")", "  for r in rows:", "    ctx.payments.refund(r)"]
    text(s, MX + 0.32, y + 0.75, 4.7, 2.6, [[R(l, MONO, 12.5, "8E8E88")] for l in code], spacing=1.12)
    text(s, MX + 0.32, y + hh - 0.5, 4.7, 0.3, [[R("“Looks fine?”  Approve.", SANS, 13, MUTED, italic=True)]])
    # arrow
    text(s, MX + 5.32, y + hh / 2 - 0.35, 0.6, 0.6, [[R("→", SANS, 30, FAINT)]], align=PP_ALIGN.CENTER)
    # right: what Stunt Double shows
    x = MX + 6.0
    ww = W - MX - x
    box(s, x, y, ww, hh, fill=CARD, line=RED, width=1.25)
    text(s, x + 0.35, y + 0.28, ww - 0.7, 0.3, [[R("●  ", MONO, 10.5, RED), R("WHAT STUNT DOUBLE SHOWS", MONO, 10.5, RED)]])
    text(s, x + 0.35, y + 0.66, ww - 0.7, 0.9, [[R("$37,404", MONO, 44, RED)]])
    text(s, x + 0.35, y + 1.45, ww - 0.7, 0.6, [[R("refunded to 744 people. ", SANS, 17, INK),
                                                   R("640 of them were never double-charged.", SANS, 17, INK, bold=True)]], spacing=1.1)
    for i, (k, v) in enumerate([("EMAILS", "744"), ("VIPS EMAILED", "8"), ("AI JURY, 3 OF 3", "Wrong")]):
        bx = x + 0.35 + i * ((ww - 0.7 - 0.3) / 3 + 0.15)
        bw = (ww - 0.7 - 0.3) / 3
        box(s, bx, y + 2.3, bw, 0.95, fill="FAFAF8", line=LINE, radius=0.12)
        text(s, bx + 0.18, y + 2.42, bw - 0.3, 0.25, [[R(k, MONO, 9, MUTED)]])
        text(s, bx + 0.18, y + 2.68, bw - 0.3, 0.5, [[R(v, MONO, 22, RED if i == 2 else INK)]])
    footer(s, 3)
    notes(s, "Today's safety step is a person reading code they can't read. Stunt Double shows what would actually "
             "happen instead: 37 thousand dollars to 744 people, 640 of whom were never double-charged.")


def s04_how(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    kicker(s, "How it works")
    headline(s, [[("Rehearse. Measure. ", False), ("Then", True), (" approve.", False)]], h=0.9)
    underline(s, 1.95)
    steps = [("01", "Copy", "A fresh copy of the data the agent needs."),
             ("02", "Rehearse", "Sandbox 1 runs the plan. gVisor, no network, no secrets."),
             ("03", "Measure", "Sandbox 2, our code only, measures what changed."),
             ("04", "Approve", "A person approves the consequences, in plain English."),
             ("05", "Replay", "Only those effects reach production, after a drift check.")]
    y, gap = 2.45, 0.22
    bw = (W - 2 * MX - gap * 4) / 5
    for i, (n, t, d) in enumerate(steps):
        x = MX + i * (bw + gap)
        hi = i == 3
        box(s, x, y, bw, 2.2, fill=INK if hi else CARD, line=None if hi else LINE)
        text(s, x + 0.25, y + 0.25, bw - 0.4, 0.3, [[R(n, MONO, 10.5, BLUE_ON_DARK if hi else BLUE)]])
        text(s, x + 0.25, y + 0.6, bw - 0.4, 0.5, [[R(t, SERIF, 24, "FAFAF8" if hi else INK)]])
        text(s, x + 0.25, y + 1.18, bw - 0.4, 0.9, [[R(d, SANS, 12.5, "C9C9C4" if hi else MUTED)]], spacing=1.1)
        if i < 4:
            text(s, x + bw - 0.02, y + 0.92, gap + 0.04, 0.4, [[R("›", SANS, 20, FAINT)]], align=PP_ALIGN.CENTER)
    y2 = 5.0
    for i, (n, l) in enumerate([("1.8 s", "median rehearsal, both sandboxes, on one $20/month Vultr VM"),
                                 ("0", "lines of the agent's code ever run against production"),
                                 ("2", "different people must approve big changes; every undo is rehearsed too")]):
        bw2 = (W - 2 * MX - 0.44) / 3
        x = MX + i * (bw2 + 0.22)
        box(s, x, y2, bw2, 1.55)
        text(s, x + 0.3, y2 + 0.2, bw2 - 0.5, 0.7, [[R(n, MONO, 38, INK)]])
        text(s, x + 0.3, y2 + 0.95, bw2 - 0.5, 0.5, [[R(l, SANS, 12.5, MUTED)]], spacing=1.1)
    footer(s, 4)
    notes(s, "Every action runs first on a copy of the business, sealed in a gVisor sandbox on Vultr. A second "
             "sandbox, running only our code, measures what really changed. A person approves that, and only those "
             "measured effects are replayed for real, after a drift check.")


def s05_containment(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    kicker(s, "Containment  ·  Challenge 01")
    headline(s, [[("The blast radius is ", False), ("zero.", True)]], h=0.9)
    underline(s, 1.95)
    y, hh = 2.4, 2.75
    half = (W - 2 * MX - 0.3) / 2
    box(s, MX, y, half, hh, fill=RED_SOFT, line="F3B9BB")
    text(s, MX, y + 0.35, half, 0.3, [[R("SANDBOX  ·  CUSTOMERS", MONO, 11, RED)]], align=PP_ALIGN.CENTER)
    text(s, MX, y + 0.62, half, 1.4, [[R("0", MONO, 84, RED)]], align=PP_ALIGN.CENTER)
    text(s, MX, y + 2.2, half, 0.35, [[R("the plan deleted all 1,300, on the double", SANS, 14, MUTED)]], align=PP_ALIGN.CENTER)
    x = MX + half + 0.3
    box(s, x, y, half, hh)
    text(s, x, y + 0.35, half, 0.3, [[R("PRODUCTION  ·  CUSTOMERS", MONO, 11, MUTED)]], align=PP_ALIGN.CENTER)
    text(s, x, y + 0.62, half, 1.4, [[R("1,300", MONO, 84, INK)]], align=PP_ALIGN.CENTER)
    text(s, x, y + 2.2, half, 0.35, [[R("untouched. Approval locked.", SANS, 14, MUTED)]], align=PP_ALIGN.CENTER)
    y2 = 5.42
    box(s, MX, y2, W - 2 * MX, 1.05)
    text(s, MX + 0.35, y2 + 0.2, 5.6, 0.7, [[R("THE PLAN SAID", MONO, 9.5, MUTED)], [R("“Audit complete. Read-only: no changes were made.”", SERIF, 16, INK)]], spacing=1.15)
    text(s, MX + 6.3, y2 + 0.2, 5.3, 0.7, [[R("A SEPARATE SANDBOX MEASURED", MONO, 9.5, MUTED)],
                                           [R("300 rows changed.  ", SANS, 16, INK, bold=True), R("The plan lied.", SANS, 16, RED, bold=True)]], spacing=1.15)
    footer(s, 5)
    notes(s, "Here's a plan that deletes every customer. It ran for real, on the double: zero customers left. "
             "Production still has 1,300, and approval locks. And when a plan lies about what it did, the separate "
             "measurement catches it: it said no changes, it changed 300 rows.")


def s06_engine(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, INK)
    kicker(s, "The Consequence Engine", dark=True)
    headline(s, [[("744 refunds planned. ", False), ("104 were right.", True)], [("It kept exactly those.", False)]], dark=True, h=1.7)
    # the 744 units of work: 93 columns x 8 rows
    cols, rows = 93, 8
    gx, gy = MX, 2.85
    cell = (W - 2 * MX) / cols
    sq = cell * 0.8
    for i in range(744):
        r, c = divmod(i, cols)
        sh = box(s, gx + c * cell, gy + r * cell, sq, sq, fill=GREEN_ON_DARK if i in KEPT else "C2474B", line=None, radius=0)
    text(s, MX, gy + rows * cell + 0.08, 8, 0.25, [[R("each square is one unit of work: a charge, its refund and its email", MONO, 9, "77776F")]])
    text(s, W - MX - 4, gy + rows * cell + 0.08, 4, 0.25, [[R("■ ", MONO, 9, GREEN_ON_DARK), R("keep 104   ", MONO, 9, "77776F"),
                                                             R("■ ", MONO, 9, "C2474B"), R("cut 640", MONO, 9, "77776F")]], align=PP_ALIGN.RIGHT)
    y = 4.42
    cw = 3.4
    cards = [("KEEP", "$5,136", "104 refunds · 104 emails", GREEN_ON_DARK, "FAFAF8"),
             ("CUT", "$32,268", "640 refunds to people never double-charged", RED_ON_DARK, RED_ON_DARK)]
    for i, (k, n, l, kc, nc) in enumerate(cards):
        x = MX + i * (cw + 0.22)
        box(s, x, y, cw, 2.15, fill=D_CARD, line=D_LINE)
        text(s, x + 0.32, y + 0.28, cw - 0.6, 0.3, [[R(k, MONO, 10.5, kc)]])
        text(s, x + 0.32, y + 0.62, cw - 0.5, 0.9, [[R(n, MONO, 42, nc)]])
        text(s, x + 0.32, y + 1.5, cw - 0.6, 0.5, [[R(l, SANS, 13, D_MUTED)]])
    x = MX + 2 * (cw + 0.22)
    cw = W - MX - x
    box(s, x, y, cw, 2.15, fill=D_CARD, line=D_LINE)
    text(s, x + 0.32, y + 0.28, cw - 0.6, 0.3, [[R("HOW", MONO, 10.5, BLUE_ON_DARK)]])
    for j, (n, t) in enumerate([("1", "Contract, before the plan: 104 to do"), ("2", "Effect graph: 744 units of work"),
                                ("3", "Replay proof: line 1 chose the 640"), ("4", "Cut, re-run fresh, checked again")]):
        text(s, x + 0.32, y + 0.64 + j * 0.34, cw - 0.5, 0.3, [[R(n + "   ", MONO, 11, BLUE_ON_DARK), R(t, SANS, 12, "DDDDDA")]])
    footer(s, 6, dark=True)
    notes(s, "Now the hard case: a plan that's only partly wrong. Ask it to refund everyone who was double-charged. "
             "Before the plan exists, the engine writes down what that means: 104 refunds. The plan does 744. Replaying "
             "it proves line 1 chose the 640 wrong ones. The engine cuts them out, re-runs just the 104 in a fresh "
             "sandbox, and every check passes. You approve exactly the right part.")


def s07_proof(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    kicker(s, "Proof, measured live on Vultr")
    headline(s, [[("Bad plans stopped. Good ones ", False), ("approved.", True)]], h=0.9)
    underline(s, 1.95)
    y, hh = 2.4, 3.85
    cw = (W - 2 * MX - 0.66) / 4
    cards = [("12/12", "bad plans stopped by the engine", [RED] * 12, 6, "live eval"),
             ("8/8", "correct plans approved, 0 false alarms", [GREEN] * 8, 6, "live eval"),
             ("8/8", "wrong plans stopped on 16 cases written before the run, never tuned on", [INK] * 8, 6, "held-out cases"),
             ("63 → 41", "a school's database it had never seen: the trap found, the cut exact", [GREEN] * 41 + [RED] * 22, 13, "beyond the demo")]
    for i, (n, l, dots, per, src) in enumerate(cards):
        x = MX + i * (cw + 0.22)
        box(s, x, y, cw, hh)
        text(s, x + 0.28, y + 0.25, cw - 0.5, 0.8, [[R(n, MONO, 40 if len(n) < 6 else 34, INK)]])
        text(s, x + 0.28, y + 1.05, cw - 0.5, 0.9, [[R(l, SANS, 12.5, MUTED)]], spacing=1.1)
        d = 0.27 if per == 6 else 0.13
        step = (cw - 0.56) / per
        rows_n = (len(dots) + per - 1) // per
        top = y + hh - 0.62 - rows_n * step
        for k, c in enumerate(dots):
            r, col = divmod(k, per)
            oval(s, x + 0.28 + col * step, top + r * step, d if per == 6 else min(d, step * 0.82), c)
        text(s, x + 0.28, y + hh - 0.38, cw - 0.5, 0.25, [[R("Source: " + src, MONO, 8.5, FAINT)]])
    text(s, MX, 6.48, W - 2 * MX, 0.3, [[R("Held-out, honestly: 3 of 8 right plans approved outright; the other 5 were sent to a person with a stated reason. "
                                           "No wrong plan was approved. Every case and miss is published in the repo.", SANS, 11, MUTED)]])
    footer(s, 7)
    notes(s, "Measured live, not on slides. Twelve of twelve bad plans stopped, eight of eight good ones approved, "
             "every wrong plan stopped on cases we wrote down before running them, and the same engine found the trap in "
             "a school's database it had never seen.")


def s08_vultr(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, INK)
    kicker(s, "Built on Vultr", dark=True)
    headline(s, [[("One VM. Four labs. ", False), ("Disposable doubles.", True)]], dark=True, h=0.9)
    y, hh = 2.25, 2.65
    box(s, MX, y, W - 2 * MX, hh + 0.5, fill=None, line=D_LINE, width=1.25)
    box(s, MX + 0.35, y - 0.17, 0.95, 0.34, fill=INK, line=None, radius=0)
    text(s, MX + 0.35, y - 0.14, 0.95, 0.3, [[R("VULTR", MONO, 11, BLUE_ON_DARK, bold=True)]], align=PP_ALIGN.CENTER)
    widths = [3.25, 4.75, 3.0]
    gap = (W - 2 * MX - 0.5 - sum(widths)) / 2
    x = MX + 0.25
    cols = [("Cloud Compute", "Web app, API and MCP server. Every rehearsal runs in two fresh gVisor sandboxes: no network, no secrets.", []),
            ("Serverless Inference", "Writes what a request means, cross-checks it, and judges the outcome.",
             ["Qwen · contract", "DeepSeek · cross-check", "GLM · jury + vision", "DeepSeek · jury", "MiniMax · jury"]),
            ("Vultr API", "A read-only double of your real server fleet. The key is used once and never kept.", [])]
    for (t, d, chips), w in zip(cols, widths):
        box(s, x, y + 0.3, w, hh, fill=D_CARD, line=D_LINE)
        text(s, x + 0.3, y + 0.55, w - 0.55, 0.45, [[R(t, SANS, 19, "FAFAF8", bold=True)]])
        text(s, x + 0.3, y + 1.02, w - 0.55, 0.9, [[R(d, SANS, 13, D_MUTED)]], spacing=1.12)
        cx, cy = x + 0.3, y + 1.72
        for c in chips:
            cw = 0.16 + 0.078 * len(c)
            if cx + cw > x + w - 0.25:
                cx, cy = x + 0.3, cy + 0.4
            chip(s, cx, cy, c, dark=True, w=cw)
            cx += cw + 0.1
        x += w + gap
    y2 = 5.72
    half = (W - 2 * MX - 0.22) / 2
    for i, (n, l, c) in enumerate([("MCP", "Any agent connects: MCP, Python SDK, CLI or REST. There is no approve tool.", "FAFAF8"),
                                    ("$8.64", "The whole build on Vultr, every eval and live judge run included.", BLUE_ON_DARK)]):
        x = MX + i * (half + 0.22)
        box(s, x, y2, half, 1.0, fill=D_CARD, line=D_LINE)
        text(s, x + 0.3, y2 + 0.16, 1.9, 0.7, [[R(n, MONO, 32, c)]], anchor=MSO_ANCHOR.MIDDLE)
        text(s, x + 2.15, y2 + 0.16, half - 2.4, 0.7, [[R(l, SANS, 13, D_MUTED)]], anchor=MSO_ANCHOR.MIDDLE, spacing=1.1)
    footer(s, 8, dark=True)
    notes(s, "All of it runs on Vultr: one Cloud Compute VM running disposable gVisor sandboxes, four labs' models on "
             "Serverless Inference writing the contract, cross-checking it and judging the result, and the Vultr API for "
             "a read-only double of your fleet. The whole build, every test included, cost under nine dollars.")


def s09_business(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    kicker(s, "Business")
    headline(s, [[("One caught mistake pays for a seat for ", False), ("55 years.", True)]], h=0.9)
    underline(s, 1.95)
    y, hh = 2.4, 3.95
    lw = 4.6
    box(s, MX, y, lw, hh)
    text(s, MX + 0.3, y + 0.25, lw - 0.5, 0.3, [[R("AI AGENTS MARKET", MONO, 10.5, MUTED)]])
    cd = CategoryChartData()
    cd.categories = ["2025", "2030"]
    cd.add_series("Market (US$ billions)", (7.84, 52.62))
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(MX + 0.25), Inches(y + 0.6), Inches(lw - 0.5), Inches(hh - 1.1), cd)
    ch = gf.chart
    ch.has_legend = False
    ch.has_title = False
    ch.font.name, ch.font.size = MONO, Pt(11)
    plot = ch.plots[0]
    plot.gap_width = 45
    plot.vary_by_categories = False
    ser = plot.series[0]
    for k, c in enumerate([BLUE_SOFT, BLUE]):
        pt = ser.points[k]
        pt.format.fill.solid(); pt.format.fill.fore_color.rgb = rgb(c)
        pt.format.line.fill.background()
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = '"$"0.0"B"', False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.name, dl.font.color.rgb = Pt(16), MONO, rgb(INK)
    va = ch.value_axis
    va.visible = False
    va.has_major_gridlines = False
    va.maximum_scale = 62
    ca = ch.category_axis
    ca.tick_labels.font.size, ca.tick_labels.font.color.rgb = Pt(11), rgb(MUTED)
    ca.format.line.color.rgb = rgb(LINE)
    text(s, MX + 0.3, y + hh - 0.42, lw - 0.5, 0.25, [[R("Source: MarketsandMarkets, 2025", MONO, 8.5, FAINT)]])
    x = MX + lw + 0.25
    rw = W - MX - x
    box(s, x, y, rw, hh)
    text(s, x + 0.3, y + 0.25, rw - 0.5, 0.3, [[R("UNIT ECONOMICS, MEASURED ON VULTR", MONO, 10.5, MUTED)]])
    tiles = [("$49", "per approver, per month"), ("73%", "gross margin at full use"), ("$0.00003", "per rehearsal"), ("$0.02–0.044", "per three-model AI check")]
    tw = (rw - 0.6 - 0.2) / 2
    for k, (n, l) in enumerate(tiles):
        r, c = divmod(k, 2)
        tx, ty = x + 0.3 + c * (tw + 0.2), y + 0.68 + r * 1.12
        box(s, tx, ty, tw, 0.98, fill=PAPER, line=LINE, radius=0.14)
        text(s, tx + 0.22, ty + 0.12, tw - 0.4, 0.5, [[R(n, MONO, 24, INK)]])
        text(s, tx + 0.22, ty + 0.6, tw - 0.4, 0.3, [[R(l, SANS, 11.5, MUTED)]])
    text(s, x + 0.3, y + 3.05, rw - 0.6, 0.8, [[R("Who buys: ", SANS, 12, INK, bold=True), R("Heads of Operations, Support and Finance Ops.  ", SANS, 12, MUTED),
                                                R("Why they must: ", SANS, 12, INK, bold=True), R("EU AI Act Art. 14 & 12 (human oversight, records) and SOC 2 CC8.1 (approved changes). ", SANS, 12, MUTED),
                                                R("Open core: ", SANS, 12, INK, bold=True), R("MIT, one command to self-host on your own Vultr.", SANS, 12, MUTED)]], spacing=1.15)
    footer(s, 9)
    notes(s, "One caught mistake in the demo is 32 thousand dollars. A seat is 49 dollars a month, so that single catch "
             "pays for it for 55 years. A rehearsal costs us three thousandths of a cent, and the EU AI Act and SOC 2 "
             "already ask companies for exactly this approval record.")


def s10_close(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    text(s, 0.5, 1.45, W - 1, 2.4, [[R("Agents should be bold.", SERIF, 60, INK)],
                                    [R("Businesses should be ", SERIF, 60, INK), R("safe.", SERIF, 60, BLUE, italic=True)]], align=PP_ALIGN.CENTER, spacing=0.95)
    bx, by, bw, bh = 2.55, 4.2, 8.23, 1.75
    box(s, bx, by, bw, bh, radius=0.22)
    qr = HERE / "qr.png"
    if qr.exists():
        s.shapes.add_picture(str(qr), Inches(bx + 0.3), Inches(by + 0.22), Inches(1.31), Inches(1.31))
    text(s, bx + 1.95, by + 0.3, bw - 2.2, 0.5, [[R("149-28-206-186.sslip.io", MONO, 24, INK)]])
    text(s, bx + 1.95, by + 0.85, bw - 2.2, 0.35, [[R("Judge mode: eight clicks, each a real rehearsal on Vultr.", SANS, 14, MUTED)]])
    text(s, bx + 1.95, by + 1.22, bw - 2.2, 0.3, [[R("github.com/vidigoat/stunt-double", MONO, 11.5, MUTED)]])
    text(s, 0.5, 6.35, W - 1, 0.35, [[R("Let the double ", SERIF, 18, INK), R("take the hit.", SERIF, 18, BLUE, italic=True)]], align=PP_ALIGN.CENTER)
    footer(s, 10, left="Stunt Double  ·  Team Dragon  ·  Vultr: Agent Rush")
    notes(s, "Agents should be bold. Businesses should be safe. Now they can be both. Try it live: judge mode is eight "
             "clicks. Let the double take the hit.")


def fade(slide) -> None:
    """A quiet fade between slides (PowerPoint and Keynote play it; it must follow clrMapOvr)."""
    from lxml import etree
    t = etree.SubElement(slide._element, qn("p:transition"), spd="med")
    etree.SubElement(t, qn("p:fade"))


def build() -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    for f in (s01_cover, s02_problem, s03_gap, s04_how, s05_containment, s06_engine, s07_proof, s08_vultr, s09_business, s10_close):
        f(prs)
    for sl in list(prs.slides)[1:]:
        fade(sl)
    prs.core_properties.title = "Stunt Double"
    prs.core_properties.subject = "Let the double take the hit. Vultr: Agent Rush, Challenge 01."
    prs.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
