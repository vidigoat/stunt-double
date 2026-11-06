"""Build the Stunt Double deck as a native, editable PowerPoint file.

Every headline, number and label is a real text box; cards are shapes; the market chart is a native chart; the
744 units of work are 744 shapes. Fonts: Georgia and Helvetica Neue, already on every Mac and PC.

    python3 presentation/build_deck.py        # StuntDouble.pptx, StuntDouble.pdf, cover.png and web/public/og.png
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
# Fonts every Mac and PC already has: nothing to install. (Windows shows Arial for Helvetica Neue.)
SERIF, SANS, MONO = "Georgia", "Helvetica Neue", "Helvetica Neue"
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
    if fill in (CARD, "FFFFFF"):
        soft_shadow(s)
    s.text_frame.text = ""
    return flat(s)


def soft_shadow(shape, alpha=0.07, blur=0.22, dist=0.05):
    from lxml import etree
    sp = shape._element.spPr
    eff = sp.find(qn("a:effectLst"))
    if eff is None:
        eff = etree.SubElement(sp, qn("a:effectLst"))
    for ch in list(eff):
        eff.remove(ch)
    sh = etree.SubElement(eff, qn("a:outerShdw"), blurRad=str(int(blur * 914400)), dist=str(int(dist * 914400)), dir="5400000", algn="t", rotWithShape="0")
    c = etree.SubElement(sh, qn("a:srgbClr"), val="0A0A0A")
    etree.SubElement(c, qn("a:alpha"), val=str(int(alpha * 100000)))


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
    text(slide, MX, y, 9, 0.3, [[R("●  ", MONO, 14, BLUE), R(label.upper(), MONO, 14, D_MUTED if dark else MUTED, bold=True)]])


def headline(slide, parts, dark=False, y=0.98, size=40, w=11.6, h=1.5):
    """parts: list of lines; each line a list of (text, accent?) pairs."""
    ink, acc = ("FAFAF8", BLUE_ON_DARK) if dark else (INK, BLUE)
    paras = [[R(t, SERIF, size, acc if a else ink, italic=a) for t, a in line] for line in parts]
    text(slide, MX, y, w, h, paras, spacing=0.92)


def underline(slide, y):
    box(slide, MX, y, 0.58, 0.045, fill=BLUE, line=None, radius=0.02)


VULTR_MARK = [
    [(8.36, 2.172), (7.348, 1.6), (1.2, 1.6), (0, 2.8), (0.182, 3.44), (11.782, 21.84), (13.817, 21.84),
     (16.892, 16.966), (17.074, 16.326), (16.892, 15.684)],
    [(18.709, 10.852), (20.744, 10.852), (21.8, 9.178), (23.817, 5.978), (24.0, 5.338), (23.817, 4.698), (22.217, 2.172),
     (21.201, 1.601), (15.053, 1.601), (13.852, 2.801), (14.04, 3.441)],
]


def vultr_mark(slide, x, y, size, color="007BFC"):
    k = Inches(size) / 24
    for poly in VULTR_MARK:
        (x0, y0), rest = poly[0], poly[1:]
        fb = slide.shapes.build_freeform(Inches(x) + int(x0 * k), Inches(y) + int(y0 * k), scale=1.0)
        fb.add_line_segments([(Inches(x) + int(px * k), Inches(y) + int(py * k)) for px, py in rest], close=True)
        sh = fb.convert_to_shape()
        sh.fill.solid(); sh.fill.fore_color.rgb = rgb(color)
        sh.line.fill.background(); sh.shadow.inherit = False
        flat(sh)


def notes(slide, s: str) -> None:
    slide.notes_slide.notes_text_frame.text = s


# ---- slides ---------------------------------------------------------------------------------------------------

IMG = HERE / "img"
CUR = [0]

def gradient_veil(slide, x, y, w, h, color: str, a_from: float, a_to: float, angle: float = 90.0):
    """A rectangle fading from one opacity to another (photo overlays)."""
    from lxml import etree
    s = box(slide, x, y, w, h, fill=color, line=None, radius=0)
    s.fill.gradient()
    s.fill.gradient_angle = angle
    for stop, a in zip(s.fill.gradient_stops, (a_from, a_to)):
        stop.color.rgb = rgb(color)
        el = stop._gs.find(qn("a:srgbClr"))
        al = etree.SubElement(el, qn("a:alpha"))
        al.set("val", str(int(a * 100000)))
    return s



def logo(slide, x, y, size, dark=False):
    slide.shapes.add_picture(str(IMG / ("logo-dark.png" if dark else "logo-light.png")), Inches(x), Inches(y), Inches(size), Inches(size))



def fade(slide) -> None:
    """A quiet fade between slides (PowerPoint and Keynote play it; it must follow clrMapOvr)."""
    from lxml import etree
    t = etree.SubElement(slide._element, qn("p:transition"), spd="med")
    etree.SubElement(t, qn("p:fade"))



# ---- final-version overrides: no tiny footers; sections are the kicker ----------------------------------------
ICONS = HERE / "img" / "icons"


def icon(slide, name, tone, x, y, size):
    slide.shapes.add_picture(str(ICONS / f"{name}-{tone}.png"), Inches(x), Inches(y), Inches(size), Inches(size))


def badge(slide, name, x, y, d=0.62, fill=BLUE_SOFT, tone="blue", pad=0.27):
    """An icon in a soft circle: the deck's one recurring ornament."""
    oval(slide, x, y, d, fill)
    icon(slide, name, tone, x + d * pad, y + d * pad, d * (1 - 2 * pad))


def bars(slide, x, y, w, h, items, maxv):
    """items: (category, value, label, color). Rounded-top bars, labels above, categories below."""
    n = len(items)
    slot = w / n
    bw = slot * 0.5
    base = y + h - 0.4
    box(slide, x, base, w, 0.012, fill=LINE, line=None, radius=0)
    for i, (cat, v, lab, col) in enumerate(items):
        bh = max(0.06, (h - 1.0) * v / maxv)
        bx = x + i * slot + (slot - bw) / 2
        b = slide.shapes.add_shape(MSO_SHAPE.ROUND_2_SAME_RECTANGLE, Inches(bx), Inches(base - bh), Inches(bw), Inches(bh))
        b.adjustments[0] = 0.12 if bh > 0.3 else 0.0
        b.fill.solid(); b.fill.fore_color.rgb = rgb(col); b.line.fill.background(); b.shadow.inherit = False; flat(b)
        text(slide, x + i * slot, base - bh - 0.48, slot, 0.42, [[R(lab, MONO, 21, INK)]], align=PP_ALIGN.CENTER)
        text(slide, x + i * slot, base + 0.08, slot, 0.3, [[R(cat, SANS, 14, MUTED)]], align=PP_ALIGN.CENTER)


def pill(slide, x, y, label, fill=BLUE_SOFT, color=BLUE, size=12, w=None):
    w = w or (0.3 + 0.1 * len(label))
    box(slide, x, y, w, 0.36, fill=fill, line=None, radius=0.18)
    text(slide, x, y, w, 0.36, [[R(label, MONO, size, color, bold=True)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def mesh(slide, color="ECECE6", step=0.42):
    """The landing page's grid paper: hairlines every few millimetres, faded toward the bottom."""
    n = 0
    y = 0.0
    while y < H:
        box(slide, 0, y, W, 0.008, fill=color, line=None, radius=0)
        y += step
    x = 0.0
    while x < W:
        box(slide, x, 0, 0.008, H, fill=color, line=None, radius=0)
        x += step
        n += 1
    gradient_veil(slide, 0, 0, W, H, PAPER, 0.0, 0.92, angle=90)    # the mesh fades out toward the bottom


def wordmark(slide, x, y, size=26, dark=False):
    ink = "FAFAF8" if dark else INK
    icon = size / 72 * 1.5
    logo(slide, x, y, icon, dark=dark)
    text(slide, x + icon + 0.12, y, 5, icon, [[R("Stunt ", SERIF, size, ink), R("Double", SERIF, size, ink, italic=True)]], anchor=MSO_ANCHOR.MIDDLE)


# ==== the deck: 12 slides, nothing under 14 pt ======================================================================
def new_slide(prs, color=PAPER):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg(s, color)
    return s


def para(slide, x, y, w, h, t, size=15, color=MUTED, font=SANS, align=PP_ALIGN.LEFT, **o):
    return text(slide, x, y, w, h, [[R(t, font, size, color, **o)]], align=align, spacing=1.12)


def s01_cover(prs):
    s = new_slide(prs); mesh(s)
    wordmark(s, W / 2 - 1.65, 0.72, size=28)
    box(s, W / 2 - 2.8, 1.62, 5.6, 0.48, fill=CARD, line=LINE, radius=0.24)
    text(s, W / 2 - 2.8, 1.62, 5.6, 0.48, [[R("NEW   ", SANS, 14, BLUE, bold=True), R("Built for Vultr: Agent Rush  ·  Blast Radius Zero", SANS, 14, MUTED)]],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 0.5, 2.18, W - 1, 1.3, [[R("Let the double", SERIF, 88, INK)]], align=PP_ALIGN.CENTER)
    box(s, 3.05, 3.5, 7.23, 1.45, fill=BLUE, line=None, radius=0.12)
    text(s, 3.05, 3.48, 7.23, 1.4, [[R("take the hit.", SERIF, 88, "FFFFFF", italic=True)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    para(s, 2.0, 5.25, W - 4.0, 0.8, "Your AI agent tries every action on a copy of your business first. You approve what would happen, not code.",
         size=18, align=PP_ALIGN.CENTER)
    cy = 6.3
    for k, (ic, tone, fill, big, small, x0) in enumerate([("x", "red", RED_SOFT, "$37,404", "the plan: 744 refunds", 2.45),
                                                         ("check2", "green", GREEN_SOFT, "$5,136", "approved: the right 104", 7.13)]):
        box(s, x0, cy, 3.75, 0.86, fill=CARD, line=LINE, radius=0.43)
        badge(s, ic, x0 + 0.15, cy + 0.15, d=0.56, fill=fill, tone=tone, pad=0.26)
        text(s, x0 + 0.86, cy + 0.07, 2.8, 0.4, [[R(big, MONO, 20, RED if k == 0 else INK)]])
        text(s, x0 + 0.86, cy + 0.46, 2.8, 0.32, [[R(small, SANS, 14, MUTED)]])
    badge(s, "arrow", W / 2 - 0.26, cy + 0.17, d=0.52, fill=BLUE, tone="white", pad=0.25)
    notes(s, "In the movies, the star never jumps from the burning building. The stunt double does. Stunt Double gives "
             "every AI agent a double of your business to take the hit first.")


def s02_problem(prs):
    s = new_slide(prs)
    kicker(s, "The problem")
    headline(s, [[("Agents stopped answering.", False)], [("They started acting.", True)]], h=1.7)
    underline(s, 2.62)
    y = 3.05
    for i, (when, what) in enumerate([("JULY 2025", "An AI agent deleted a company's production database, during a code freeze."),
                                       ("SPRING 2026", "Another deleted a startup's database and its backups, in nine seconds.")]):
        yy = y + i * 1.88
        box(s, MX, yy, 6.9, 1.7)
        badge(s, "alert", MX + 0.32, yy + 0.32, d=0.62, fill=RED_SOFT, tone="red")
        text(s, MX + 1.18, yy + 0.26, 5.5, 0.3, [[R(when, MONO, 14, RED, bold=True)]])
        text(s, MX + 1.18, yy + 0.62, 5.5, 0.9, [[R(what, SERIF, 21, INK)]], spacing=1.05)
    x = MX + 7.15
    dw = W - MX - x
    box(s, x, y, dw, 3.58, fill=INK, line=None, radius=0.2)
    text(s, x + 0.4, y + 0.34, dw - 0.8, 0.3, [[R("AND TODAY'S SAFETY STEP?", MONO, 14, "9A9A94", bold=True)]])
    text(s, x + 0.4, y + 0.74, dw - 0.8, 1.4, [[R("A manager reads code they can't read, and clicks ", SERIF, 24, "FAFAF8"),
                                                R("approve.", SERIF, 24, BLUE_ON_DARK, italic=True)]], spacing=1.05)
    box(s, x + 0.4, y + 2.3, dw - 0.8, 0.015, fill="2C2C2A", line=None, radius=0)
    text(s, x + 0.4, y + 2.5, 1.7, 0.7, [[R("40%+", MONO, 34, RED_ON_DARK)]])
    para(s, x + 2.05, y + 2.48, dw - 2.4, 0.9, "of agent projects to be scrapped by 2027 (Gartner)", size=14, color="C9C9C4")
    notes(s, "AI agents don't just answer any more. They refund customers, send email, delete servers. In July 2025 one "
             "deleted a company's production database during a code freeze (eWeek); this spring another wiped a database "
             "and its backups in nine seconds (Information Age, May 2026). And today's safety step is a person reading "
             "code they can't read. Gartner expects over 40% of agentic AI projects to be cancelled by 2027, partly for "
             "inadequate risk controls.")


def s03_how(prs):
    s = new_slide(prs)
    kicker(s, "How it works")
    headline(s, [[("Rehearse. Measure. ", False), ("Then", True), (" approve.", False)]], h=0.9)
    underline(s, 1.95)
    steps = [("copy", "Copy", "A fresh copy of your business."), ("play", "Rehearse", "The plan runs sealed, offline."),
             ("measure", "Measure", "A second sandbox records every change."), ("approve", "Approve", "A person approves the consequences."),
             ("replay", "Replay", "Only those changes go live.")]
    y, gap = 2.4, 0.4
    bw = (W - 2 * MX - gap * 4) / 5
    for i, (ic, t, d) in enumerate(steps):
        x = MX + i * (bw + gap)
        hi = i == 3
        box(s, x, y, bw, 2.45, fill=INK if hi else CARD, line=None if hi else LINE)
        badge(s, ic, x + 0.25, y + 0.25, d=0.6, fill=BLUE if hi else BLUE_SOFT, tone="white" if hi else "blue")
        text(s, x + 0.25, y + 1.0, bw - 0.4, 0.5, [[R(t, SERIF, 23, "FAFAF8" if hi else INK)]])
        para(s, x + 0.25, y + 1.5, bw - 0.4, 0.9, d, size=14, color="C9C9C4" if hi else MUTED)
        if i < 4:
            badge(s, "arrow", x + bw + gap / 2 - 0.21, y + 1.0, d=0.42, fill="FFFFFF", tone="blue", pad=0.25)
    y2 = 5.15
    bw2 = (W - 2 * MX - 0.44) / 3
    for i, (ic, n, l) in enumerate([("gauge", "1.8 s", "median rehearsal, on one Vultr VM"),
                                    ("shield", "0", "lines of agent code run in production"),
                                    ("users", "2", "people approve every big change")]):
        x = MX + i * (bw2 + 0.22)
        box(s, x, y2, bw2, 1.62)
        icon(s, ic, "blue", x + bw2 - 0.75, y2 + 0.3, 0.42)
        text(s, x + 0.3, y2 + 0.18, bw2 - 1.2, 0.7, [[R(n, MONO, 38, INK)]])
        para(s, x + 0.3, y2 + 0.88, bw2 - 0.5, 0.5, l, size=15)
    notes(s, "Every action runs first on a copy of the business, sealed in a gVisor sandbox on Vultr with no network and no "
             "secrets. A second sandbox, running only our code, measures what really changed. A person approves that, and "
             "only those measured effects are replayed for real, after a drift check. A rehearsal takes 1.8 seconds.")


def s04_containment(prs):
    s = new_slide(prs)
    kicker(s, "Containment  ·  Challenge 01")
    headline(s, [[("The blast radius is ", False), ("zero.", True)]], h=0.9)
    underline(s, 1.95)
    y, hh, cw = 2.45, 2.6, 5.1
    for k, (ic, tone, fill, lab, n, sub, ncol) in enumerate([
            ("trash", "red", RED_SOFT, "THE DOUBLE", "0", "customers left after the plan ran", RED),
            ("shield", "green", GREEN_SOFT, "PRODUCTION", "1,300", "customers, untouched. Approval locked.", INK)]):
        x = MX if k == 0 else W - MX - cw
        box(s, x, y, cw, hh, fill=CARD, line=LINE, radius=0.22)
        badge(s, ic, x + 0.35, y + 0.35, d=0.6, fill=fill, tone=tone)
        text(s, x + 1.1, y + 0.5, cw - 1.4, 0.35, [[R(lab, MONO, 14, RED if k == 0 else GREEN, bold=True)]])
        text(s, x + 0.35, y + 0.95, cw - 0.7, 1.0, [[R(n, MONO, 60, ncol)]])
        para(s, x + 0.35, y + 2.02, cw - 0.7, 0.4, sub, size=16)
    wx = W / 2
    lock_top, label_bottom = y + hh / 2 - 0.5, y + hh / 2 + 0.7
    box(s, wx - 0.015, y + 0.15, 0.03, lock_top - 0.1 - (y + 0.15), fill=LINE, line=None, radius=0)      # wall above the lock
    box(s, wx - 0.015, label_bottom + 0.08, 0.03, y + hh - 0.15 - (label_bottom + 0.08), fill=LINE, line=None, radius=0)  # and below the label
    badge(s, "lock", wx - 0.38, lock_top, d=0.76, fill=INK, tone="white", pad=0.27)
    para(s, wx - 1.0, y + hh / 2 + 0.34, 2.0, 0.3, "gVisor wall", size=14, align=PP_ALIGN.CENTER)
    y2 = 5.35
    box(s, MX, y2, W - 2 * MX, 1.2, fill=CARD, line=LINE, radius=0.2)
    badge(s, "quote", MX + 0.3, y2 + 0.3, d=0.6, fill=BLUE_SOFT, tone="blue")
    text(s, MX + 1.1, y2 + 0.2, 5.3, 0.85, [[R("Another plan said", SANS, 14, MUTED)], [R("“Read-only audit. No changes made.”", SERIF, 19, INK)]], spacing=1.1)
    badge(s, "eye", MX + 6.55, y2 + 0.3, d=0.6, fill=RED_SOFT, tone="red")
    text(s, MX + 7.35, y2 + 0.2, 4.3, 0.85, [[R("A second sandbox measured", SANS, 14, MUTED)],
                                             [R("300 rows changed. ", SANS, 19, INK, bold=True), R("Caught.", SANS, 19, RED, bold=True)]], spacing=1.1)
    notes(s, "Here's a plan that deletes every customer. It ran for real, on the double: zero customers left. Production "
             "still has 1,300, and approval locks. Because our own code measures the result in a second sandbox, a plan "
             "that lies about what it did is caught too: one said 'no changes' and had changed 300 rows.")


def grid744(s, lit=True):
    cols, rows = 62, 12
    gx, gy = MX, 2.75
    pitch = int(Inches(W - 2 * MX)) // cols
    gap = int(pitch * 0.24)
    for i in range(744):
        r, c = divmod(i, cols)
        sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(gx) + c * pitch, Inches(gy) + r * pitch, pitch - gap, pitch - gap)
        sh.adjustments[0] = 0.18
        sh.name = f"!!unit{i}"
        sh.fill.solid(); sh.fill.fore_color.rgb = rgb(GREEN_ON_DARK if (lit and i in KEPT) else "B8434A")
        sh.line.fill.background(); sh.shadow.inherit = False; flat(sh)
    return gy + rows * pitch / 914400


def s05a_question(prs):
    """The setup for the reveal: every planned refund, all red, one question."""
    s = new_slide(prs, INK)
    kicker(s, "The Consequence Engine", dark=True)
    headline(s, [[("The agent planned 744 refunds.", False)], [("How many were right?", True)]], dark=True, h=1.7)
    bottom = grid744(s, lit=False)
    para(s, MX, bottom + 0.05, 8, 0.3, "Each square: one charge, its refund and its email", size=14, color="9A9A94")
    text(s, MX, 5.75, W - 2 * MX, 1.0, [[R("$37,404", MONO, 54, RED_ON_DARK), R("   about to leave the business.", SANS, 22, "C9C9C4")]], anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "Now the hard case: a plan that's only partly wrong. Asked to refund everyone who was double-charged, the "
             "agent planned 744 refunds: $37,404. Every rule passes. So how many of these were actually right?")


def s05_engine(prs):
    s = new_slide(prs, INK)
    kicker(s, "The Consequence Engine", dark=True)
    headline(s, [[("744 refunds planned. ", False), ("104 were right.", True)], [("It kept exactly those.", False)]], dark=True, h=1.7)
    bottom = grid744(s, lit=True)
    para(s, MX, bottom + 0.05, 8, 0.3, "Each square: one charge, its refund and its email", size=14, color="9A9A94")
    text(s, W - MX - 4, bottom + 0.05, 4, 0.3, [[R("■ ", SANS, 14, GREEN_ON_DARK), R("keep 104     ", SANS, 14, "9A9A94"),
                                                 R("■ ", SANS, 14, "B8434A"), R("cut 640", SANS, 14, "9A9A94")]], align=PP_ALIGN.RIGHT)
    y, hh, cw = 5.5, 1.55, 2.9
    for i, (k, n, l, kc, nc) in enumerate([("KEEP", "$5,136", "the right 104", GREEN_ON_DARK, "FAFAF8"),
                                           ("CUT", "$32,268", "640 never double-charged", RED_ON_DARK, RED_ON_DARK)]):
        x = MX + i * (cw + 0.22)
        box(s, x, y, cw, hh, fill=D_CARD, line=D_LINE)
        text(s, x + 0.3, y + 0.2, cw - 0.5, 0.3, [[R(k, MONO, 14, kc, bold=True)]])
        text(s, x + 0.3, y + 0.45, cw - 0.4, 0.7, [[R(n, MONO, 34, nc)]])
        para(s, x + 0.3, y + 1.08, cw - 0.5, 0.35, l, size=14, color=D_MUTED)
    x = MX + 2 * (cw + 0.22)
    hw = W - MX - x
    box(s, x, y, hw, hh, fill=D_CARD, line=D_LINE)
    colw = (hw - 0.5) / 2
    for j, (ic, t) in enumerate([("contract", "Contract: 104 to do"), ("graph", "744 units of work"),
                                 ("replayproof", "Line 1 chose the 640"), ("scissors", "Cut, re-run, re-check")]):
        r, c = divmod(j, 2)
        ix, iy = x + 0.28 + c * colw, y + 0.24 + r * 0.6
        badge(s, ic, ix, iy, d=0.46, fill="1E2A4A", tone="lightblue", pad=0.24)
        text(s, ix + 0.56, iy, colw - 0.6, 0.46, [[R(t, SANS, 14, "E4E4E0")]], anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "Only 104. Before the plan existed, the engine writes down what the "
             "request means: 104 refunds. The plan does 744. Replaying it proves line 1 chose the 640 wrong ones. The "
             "engine cuts them out, re-runs just the 104 in a fresh sandbox, and every check passes. Guardrails block or "
             "allow; this approves exactly the right part.")


def browser(slide, x, y, w, img, url="149-28-206-186.sslip.io/app"):
    from PIL import Image
    iw, ih = Image.open(img).size
    h = w * ih / iw
    bar = 0.4
    box(slide, x, y, w + 0.16, h + bar + 0.08, fill=CARD, line=LINE, radius=0.16)
    for k, c in enumerate(["F2B8BA", "F5DCA0", "BFE3CB"]):
        oval(slide, x + 0.2 + k * 0.2, y + 0.14, 0.12, c)
    box(slide, x + 0.95, y + 0.09, w - 1.6, 0.24, fill=PAPER, line=None, radius=0.12)
    slide.shapes.add_picture(str(img), Inches(x + 0.08), Inches(y + bar), Inches(w))
    return h + bar + 0.08


def s06_product(prs):
    s = new_slide(prs)
    kicker(s, "The real product, live on Vultr")
    headline(s, [[("Six checks. ", False), ("One plain answer.", True)]], h=0.9)
    underline(s, 1.95)
    text(s, W - MX - 5.0, 1.12, 5.0, 0.5, [[R("Try it: 149-28-206-186.sslip.io", SANS, 16, BLUE, bold=True)]], align=PP_ALIGN.RIGHT)
    browser(s, MX, 2.35, W - 2 * MX - 0.16, HERE / "img" / "product.png")
    notes(s, "This is the real screen, on the live server, for the refund plan. Six independent layers each give one "
             "plain reason: it was measured, every change was proven by replay, the intent contract is broken, the rules "
             "pass, the AI jury objects, and big changes need two people. Combined by fixed rules into one decision: "
             "approve just the 104 of 744 changes that pass. And every step is sealed in a signed record your browser "
             "can verify.")

def s06b_features(prs):
    s = new_slide(prs)
    kicker(s, "Every core feature")
    headline(s, [[("Everything a careful team ", False), ("needs.", True)]], h=0.9)
    underline(s, 1.95)
    feats = [("db", "Your real systems", "Postgres, a Vultr fleet, any API, a browser."),
             ("approve", "Plain English", "Money, people, emails, rows. Never code."),
             ("users", "Two-person sign-off", "For big changes and every undo."),
             ("undo", "Rehearsed undo", "Regret it? The undo is rehearsed too."),
             ("brain", "Three-lab AI jury", "Each investigates the data on its own."),
             ("zap", "Learned rules", "The same mistake, blocked without AI."),
             ("lock", "Signed evidence", "A record your browser can verify."),
             ("code", "Any agent plugs in", "MCP, SDK, CLI, REST. No approve tool.")]
    cw, ch = (W - 2 * MX - 0.66) / 4, 2.0
    for k, (ic, t, d) in enumerate(feats):
        r, c = divmod(k, 4)
        x, y = MX + c * (cw + 0.22), 2.4 + r * (ch + 0.22)
        box(s, x, y, cw, ch, fill=CARD, line=LINE, radius=0.2)
        badge(s, ic, x + 0.28, y + 0.28, d=0.58, fill=BLUE_SOFT, tone="blue")
        text(s, x + 0.28, y + 0.98, cw - 0.45, 0.4, [[R(t, SANS, 17, INK, bold=True)]])
        para(s, x + 0.28, y + 1.36, cw - 0.45, 0.6, d, size=14)
    notes(s, "Everything a careful team needs. It works on your real systems: a read-only double of your Postgres, your "
             "Vultr fleet, any HTTP API and a real browser. A person sees consequences in plain English, never code. Big "
             "changes need two different people, and every undo is rehearsed and approved too. An AI jury from three labs "
             "investigates the data with read-only SQL. Every catch can become a rule that blocks the same mistake without "
             "AI. Every decision is sealed in a signed record your browser can verify. And any agent plugs in over MCP, an "
             "SDK, a CLI or REST; there is no approve tool, so only a person can say yes.")


def s07_vultr(prs):
    s = new_slide(prs, INK)
    kicker(s, "Built on Vultr", dark=True)
    headline(s, [[("One VM. Four labs. ", False), ("Disposable doubles.", True)]], dark=True, h=0.9)
    y, hh = 2.3, 2.75
    box(s, MX, y, W - 2 * MX, hh, fill=None, line=D_LINE, width=1.25)
    box(s, MX + 0.3, y - 0.22, 1.25, 0.44, fill=INK, line=None, radius=0)
    vultr_mark(s, MX + 0.42, y - 0.15, 0.3)
    text(s, MX + 0.8, y - 0.17, 0.8, 0.34, [[R("Vultr", SANS, 15, "FAFAF8", bold=True)]])
    cw = (W - 2 * MX - 0.5 - 0.5) / 3
    for i, (ic, t, d) in enumerate([("cpu", "Cloud Compute", "Every rehearsal runs in two fresh gVisor sandboxes."),
                                    ("brain", "Serverless Inference", "Four labs' models write, check and judge."),
                                    ("cloud", "Vultr API", "A read-only double of your real server fleet.")]):
        x = MX + 0.25 + i * (cw + 0.25)
        box(s, x, y + 0.3, cw, hh - 0.55, fill=D_CARD, line=D_LINE)
        badge(s, ic, x + 0.3, y + 0.55, d=0.6, fill=BLUE, tone="white")
        text(s, x + 0.3, y + 1.3, cw - 0.5, 0.45, [[R(t, SANS, 20, "FAFAF8", bold=True)]])
        para(s, x + 0.3, y + 1.75, cw - 0.55, 0.7, d, size=15, color=D_MUTED)
    y2 = 5.45
    half = (W - 2 * MX - 0.25) / 2
    box(s, MX, y2, half, 1.15, fill=D_CARD, line=D_LINE)
    for k, b in enumerate(["claude", "cursor", "mcp", "python"]):
        icon(s, f"brand-{b}", "white", MX + 0.32 + k * 0.55, y2 + 0.36, 0.42)
    text(s, MX + 2.65, y2 + 0.15, half - 2.9, 0.85, [[R("Any agent plugs in. There is no approve tool.", SANS, 15, D_MUTED)]], anchor=MSO_ANCHOR.MIDDLE, spacing=1.12)
    x = MX + half + 0.25
    box(s, x, y2, half, 1.15, fill=D_CARD, line=D_LINE)
    text(s, x + 0.32, y2 + 0.2, 2.0, 0.75, [[R("$8.64", MONO, 34, BLUE_ON_DARK)]], anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 2.3, y2 + 0.15, half - 2.55, 0.85, [[R("The whole build on Vultr, every test included.", SANS, 15, D_MUTED)]], anchor=MSO_ANCHOR.MIDDLE, spacing=1.12)
    notes(s, "All of it runs on Vultr. Cloud Compute runs the web app, the API, the MCP server and every rehearsal in two "
             "fresh gVisor sandboxes. Serverless Inference runs four labs' models: Qwen writes the intent contract, DeepSeek "
             "cross-checks it, and GLM, DeepSeek and MiniMax judge the outcome; GLM also reads browser screenshots. The "
             "Vultr API gives a read-only double of your real fleet. Agents connect over MCP, an SDK, a CLI or REST. The "
             "whole build, every test run included, cost $8.64.")


def s08_proof(prs):
    s = new_slide(prs)
    kicker(s, "Proof, measured live on Vultr")
    headline(s, [[("Bad plans stopped. Good ones ", False), ("approved.", True)]], h=0.9)
    underline(s, 1.95)
    y, hh = 2.45, 3.55
    cw = (W - 2 * MX - 0.66) / 4
    for i, (n, l, dots, per) in enumerate([("12/12", "bad plans stopped", [RED] * 12, 6),
                                           ("8/8", "good plans approved, zero false alarms", [GREEN] * 8, 6),
                                           ("8/8", "wrong plans stopped on cases it never saw", [INK] * 8, 6),
                                           ("63→41", "a school's data, cut to exactly the right 41", [GREEN] * 41 + [RED] * 22, 13)]):
        x = MX + i * (cw + 0.22)
        box(s, x, y, cw, hh)
        icon(s, "check", "green", x + cw - 0.62, y + 0.32, 0.36)
        text(s, x + 0.28, y + 0.25, cw - 0.95, 0.8, [[R(n, MONO, 36, INK)]])
        para(s, x + 0.28, y + 1.05, cw - 0.5, 0.9, l, size=15)
        d = 0.3 if per == 6 else 0.14
        step = (cw - 0.56) / per
        rows_n = (len(dots) + per - 1) // per
        top = y + hh - 0.35 - rows_n * step
        for k, c in enumerate(dots):
            r, col = divmod(k, per)
            oval(s, x + 0.28 + col * step, top + r * step, d if per == 6 else min(d, step * 0.82), c)
    text(s, MX, 6.3, W - 2 * MX, 0.45, [[R("No wrong plan was ever approved. ", SANS, 18, INK, bold=True), R("Every case, and every miss, is published.", SANS, 18, MUTED)]])
    notes(s, "Measured live on Vultr: the engine stopped 12 of 12 bad plans and approved 8 of 8 good ones, with no false "
             "alarms. On 16 held-out cases written before the run, it stopped all 8 wrong plans (3 of 8 right plans were "
             "approved outright; the other 5 went to a person with a reason). On a school's database it had never seen, "
             "it found the 22 students who took their withdrawal back and kept exactly the right 41 of 63. 201 tests run in CI.")


def s09_studies(prs):
    s = new_slide(prs)
    kicker(s, "Why it matters now")
    headline(s, [[("Agents are getting the keys, ", False), ("fast.", True)]], h=0.9)
    underline(s, 1.95)
    y, hh = 2.4, 4.1
    cw = (W - 2 * MX - 0.5) / 3
    text(s, MX, 6.72, W - 2 * MX, 0.45, [[R("Every one of those agents needs a ", SANS, 18, INK), R("stunt double.", SERIF, 20, BLUE, italic=True)]])
    for i, (t, growth, items, maxv, src) in enumerate([
            ("Enterprise apps with AI agents", "33×", [("2024", 0.6, "<1%", BLUE_SOFT), ("2028", 33, "33%", BLUE)], 33, "Gartner"),
            ("Work decisions made by agents", "0 → 15%", [("2024", 0.0, "0%", BLUE_SOFT), ("2028", 15, "15%+", BLUE)], 15, "Gartner"),
            ("AI agents market", "6.7×", [("2025", 7.84, "$7.8B", BLUE_SOFT), ("2030", 52.62, "$52.6B", BLUE)], 52.62, "MarketsandMarkets")]):
        x = MX + i * (cw + 0.25)
        box(s, x, y, cw, hh, fill=CARD, line=LINE, radius=0.22)
        text(s, x + 0.32, y + 0.32, cw - 1.75, 0.75, [[R(t, SANS, 16, INK, bold=True)]], spacing=1.05)
        pw = 0.36 + 0.11 * len(growth)
        pill(s, x + cw - 0.32 - pw, y + 0.32, growth, size=14, w=pw)
        bars(s, x + 0.3, y + 1.05, cw - 0.6, hh - 1.55, items, maxv)
        para(s, x + 0.32, y + hh - 0.45, cw - 0.6, 0.3, src, size=14, color=FAINT)
    notes(s, "Why now: Gartner expects a third of enterprise software to include agentic AI by 2028, up from under 1%, "
             "and agents to make at least 15% of day-to-day work decisions. The AI agents market grows from about $7.8 "
             "billion in 2025 to $52.6 billion by 2030 (MarketsandMarkets). Every one of those agents needs a stunt double.")


def s10_business(prs):
    s = new_slide(prs)
    kicker(s, "Business")
    headline(s, [[("One catch pays for a seat for ", False), ("55 years.", True)]], h=0.9)
    underline(s, 1.95)
    y, hh = 2.4, 4.15
    lw = 4.6
    box(s, MX, y, lw, hh)
    text(s, MX + 0.32, y + 0.32, lw - 0.5, 0.4, [[R("One catch vs a year of a seat", SANS, 16, INK, bold=True)]])
    bars(s, MX + 0.3, y + 0.95, lw - 0.6, hh - 1.15, [("one mistake", 32268, "$32,268", RED), ("a seat, a year", 588, "$588", BLUE)], 32268)
    x = MX + lw + 0.25
    rw = W - MX - x
    box(s, x, y, rw, hh)
    tw, th = (rw - 0.6 - 0.2) / 2, 1.7
    for k, (ic, n, l) in enumerate([("dollar", "$49", "per approver, per month"), ("percent", "73%", "gross margin, measured"),
                                    ("bolt", "$0.00003", "per rehearsal"), ("law", "Required", "by EU AI Act, SOC 2")]):
        r, c = divmod(k, 2)
        tx, ty = x + 0.3 + c * (tw + 0.2), y + 0.3 + r * (th + 0.2)
        box(s, tx, ty, tw, th, fill=PAPER, line=LINE, radius=0.16)
        badge(s, ic, tx + 0.25, ty + 0.25, d=0.56, fill=BLUE_SOFT, tone="blue", pad=0.24)
        text(s, tx + 0.25, ty + 0.85, tw - 0.4, 0.45, [[R(n, MONO, 26, INK)]])
        para(s, tx + 0.25, ty + 1.27, tw - 0.4, 0.35, l, size=15)
    notes(s, "One caught mistake in the demo is $32,268; a seat is $49 a month, so that single catch pays for it for 55 "
             "years. A rehearsal costs us $0.00003 and a three-model AI check at most $0.044, so a full seat runs at a 73% "
             "gross margin. Buyers: Heads of Operations, Support and Finance Ops. The EU AI Act (Articles 14 and 12) and "
             "SOC 2 (CC8.1) already ask for exactly this approval record. Open core, MIT: one command self-hosts it on "
             "your own Vultr account.")


def s11_why(prs):
    s = new_slide(prs, INK)
    kicker(s, "Why it wins", dark=True)
    headline(s, [[("Code got CI/CD. Money got audits.", False)], [("Agent actions get a double.", True)]], dark=True, h=1.7)
    cw, ch = (W - 2 * MX - 0.25) / 2, 1.78
    for i, (ic, t, d) in enumerate([("cpu", "Application of technology", "gVisor on Cloud Compute, four labs on Serverless Inference."),
                                    ("sparkles", "Originality", "Not block or allow: it approves exactly the right part, proven by replay."),
                                    ("trophy", "Business value", "One caught mistake pays for a seat for 55 years, at a 73% margin."),
                                    ("eye", "Live, not a mockup", "Judge mode is eight clicks, each a real rehearsal on Vultr.")]):
        r, c = divmod(i, 2)
        x, y = MX + c * (cw + 0.25), 2.95 + r * (ch + 0.22)
        box(s, x, y, cw, ch, fill=D_CARD, line=D_LINE, radius=0.2)
        badge(s, ic, x + 0.35, y + 0.38, d=0.68, fill=BLUE, tone="white")
        text(s, x + 1.3, y + 0.32, cw - 1.6, 0.42, [[R(t, SANS, 20, "FAFAF8", bold=True)]])
        para(s, x + 1.3, y + 0.8, cw - 1.6, 0.85, d, size=16, color=D_MUTED)
    notes(s, "Why it wins. Application of technology: real gVisor isolation on Vultr Cloud Compute and four labs' models on "
             "Serverless Inference. Originality: guardrails block or allow; this approves exactly the right part of a plan, "
             "with promises written before the plan and proof by replay. Business value: one catch pays for a seat for 55 "
             "years. And it's live today. Next: more connectors, a Vultr VM per risky rehearsal, approvals in Slack, and the "
             "approval layer every company uses before an agent acts.")


def s12_close(prs):
    s = new_slide(prs, INK)
    s.shapes.add_picture(str(IMG / "close-16x9.jpg"), 0, 0, Inches(W), Inches(H))
    gradient_veil(s, 0, 0, W, H, "05070D", 0.25, 0.7, angle=90)
    wordmark(s, W / 2 - 1.55, 0.85, size=26, dark=True)
    text(s, 0.5, 1.85, W - 1, 2.4, [[R("Agents should be bold.", SERIF, 62, "FFFFFF")],
                                    [R("Businesses should be ", SERIF, 62, "FFFFFF"), R("safe.", SERIF, 62, "9DB8FF", italic=True)]], align=PP_ALIGN.CENTER, spacing=0.95)
    bx, by, bw, bh = 2.55, 4.4, 8.23, 1.7
    box(s, bx, by, bw, bh, fill="FFFFFF", line=None, radius=0.24)
    s.shapes.add_picture(str(HERE / "qr.png"), Inches(bx + 0.27), Inches(by + 0.22), Inches(1.26), Inches(1.26))
    text(s, bx + 1.85, by + 0.28, bw - 2.1, 0.5, [[R("149-28-206-186.sslip.io", MONO, 24, INK)]])
    para(s, bx + 1.85, by + 0.82, bw - 2.1, 0.35, "Judge mode: eight clicks, each a real rehearsal.", size=16)
    para(s, bx + 1.85, by + 1.18, bw - 2.1, 0.35, "github.com/vidigoat/stunt-double", size=14, font=MONO)
    text(s, 0.5, 6.45, W - 1, 0.45, [[R("Let the double ", SERIF, 22, "FFFFFF"), R("take the hit.", SERIF, 22, "9DB8FF", italic=True)]], align=PP_ALIGN.CENTER)
    notes(s, "Agents should be bold. Businesses should be safe. Now they can be both. Try it live: judge mode is eight "
             "clicks. Let the double take the hit. Photo: 'Stormy sunset over the Waimakariri River basin, New Zealand', "
             "Wikimedia Commons, CC BY-SA 4.0.")


SLIDES = (s01_cover, s02_problem, s03_how, s04_containment, s05a_question, s05_engine, s06_product, s06b_features, s07_vultr, s08_proof, s09_studies, s10_business, s12_close)


ALT = {"product.png": "The live Stunt Double console: six decision layers, and 104 of 744 refunds kept",
       "qr.png": "QR code to the live demo, 149-28-206-186.sslip.io/app",
       "close-16x9.jpg": "Stormy sunset over the Waimakariri River basin, New Zealand",
       "logo": "Stunt Double logo: two figures, you and your double",
       "brand-claude": "Claude logo", "brand-cursor": "Cursor logo", "brand-mcp": "Model Context Protocol logo",
       "brand-python": "Python logo"}


def morph(slide) -> None:
    """PowerPoint's Morph: the same 744 named squares change colour in place. Players without Morph fall back to a fade."""
    from lxml import etree
    P = "http://schemas.openxmlformats.org/presentationml/2006/main"
    xml = ('<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
           '<mc:Choice xmlns:p159="http://schemas.microsoft.com/office/powerpoint/2015/09/main" Requires="p159">'
           f'<p:transition xmlns:p="{P}" spd="slow"><p159:morph option="byObject"/></p:transition></mc:Choice>'
           f'<mc:Fallback><p:transition xmlns:p="{P}" spd="slow"><p:fade/></p:transition></mc:Fallback></mc:AlternateContent>')
    slide._element.append(etree.fromstring(xml))


def build() -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    from pptx.shapes.shapetree import SlideShapes
    real_add = SlideShapes.add_picture

    def tagged(self, image_file, *a, **k):
        pic = real_add(self, image_file, *a, **k)
        pic._element.nvPicPr.cNvPr.set("descr", next((v for kk, v in ALT.items() if kk in str(image_file)), "Icon"))
        return pic
    SlideShapes.add_picture = tagged
    try:
        for f in SLIDES:
            f(prs)
    finally:
        SlideShapes.add_picture = real_add
    for i, sl in enumerate(prs.slides):
        if SLIDES[i] is s05_engine:
            morph(sl)
        elif i:
            fade(sl)
    prs.core_properties.title = "Stunt Double"
    prs.core_properties.subject = "Let the double take the hit. Vultr: Agent Rush, Challenge 01."
    prs.save(OUT)
    return OUT


def export_images() -> None:
    """The PDF (the submission's slides), the cover image (slide 1, 1920x1080) and the site's social preview (1200x630).
    Needs LibreOffice (soffice) and poppler (pdftoppm)."""
    import shutil
    import subprocess
    from PIL import Image
    if not (shutil.which("soffice") and shutil.which("pdftoppm")):
        print("soffice/pdftoppm not found: skipped the PDF and images")
        return
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(HERE), str(OUT)], check=True, capture_output=True)
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-png", "-singlefile", "-scale-to-x", "1920", "-scale-to-y", "1080",
                    str(HERE / "StuntDouble.pdf"), str(HERE / "cover")], check=True)
    im = Image.open(HERE / "cover.png").convert("RGB").resize((1200, 675), Image.LANCZOS)
    im.crop((0, 38, 1200, 668)).save(HERE.parent / "web" / "public" / "og.png", optimize=True)


if __name__ == "__main__":
    print(build())
    export_images()
