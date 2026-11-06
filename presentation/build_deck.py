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


# The Vultr mark (Simple Icons, 24-unit box), as two polygons; the tiny corner rounding is dropped.
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


def chip(slide, x, y, label, dark=False, color=None, w=None):
    w = w or (0.16 + 0.085 * len(label))
    box(slide, x, y, w, 0.34, fill=D_CARD if dark else CARD, line=D_LINE if dark else LINE, radius=0.17)
    text(slide, x, y + 0.075, w, 0.25, [[R(label, MONO, 9.5, color or ("DDDDDA" if dark else MUTED))]], align=PP_ALIGN.CENTER)
    return w


# ---- slides ---------------------------------------------------------------------------------------------------

IMG = HERE / "img"
CUR = [0]

def veil(slide, x, y, w, h, color: str, alpha: float):
    """A rectangle of one color at a given opacity (0..1), for legibility over photos."""
    from lxml import etree
    s = box(slide, x, y, w, h, fill=color, line=None, radius=0)
    clr = s.fill._xPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
    a = etree.SubElement(clr, qn("a:alpha"))
    a.set("val", str(int(alpha * 100000)))
    return s



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



def column_chart(slide, x, y, w, h, cats, vals, colors, fmt, labels=None, maxv=None, label_size=18):
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("s", vals)
    ch = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    ch.has_legend = False
    ch.has_title = False
    ch.font.name, ch.font.size = MONO, Pt(11)
    plot = ch.plots[0]
    plot.gap_width = 55
    ser = plot.series[0]
    for k, c in enumerate(colors):
        pt = ser.points[k]
        pt.format.fill.solid(); pt.format.fill.fore_color.rgb = rgb(c)
        pt.format.line.fill.background()
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = fmt, False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.name, dl.font.color.rgb = Pt(label_size), MONO, rgb(INK)
    if labels:
        for k, t in enumerate(labels):
            if t:
                tf = ser.points[k].data_label.text_frame
                tf.text = t
                for r in tf.paragraphs[0].runs:
                    r.font.size, r.font.name, r.font.color.rgb = Pt(label_size), MONO, rgb(INK)
                ser.points[k].data_label.position = XL_LABEL_POSITION.OUTSIDE_END
    va = ch.value_axis
    va.visible = False
    va.has_major_gridlines = False
    va.minimum_scale = 0
    if maxv:
        va.maximum_scale = maxv
    ca = ch.category_axis
    ca.tick_labels.font.size, ca.tick_labels.font.color.rgb = Pt(12), rgb(MUTED)
    ca.format.line.color.rgb = rgb(LINE)
    return ch



def title(slide, parts, dark=False, size=42, y=0.98, h=1.6):
    headline(slide, parts, dark=dark, y=y, size=size, h=h)



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
    y, gap = 2.4, 0.4
    bw = (W - 2 * MX - gap * 4) / 5
    for i, ((n, t, d), ic) in enumerate(zip(steps, ["copy", "play", "measure", "approve", "replay"])):
        x = MX + i * (bw + gap)
        hi = i == 3
        box(s, x, y, bw, 2.35, fill=INK if hi else CARD, line=None if hi else LINE)
        badge(s, ic, x + 0.25, y + 0.25, d=0.6, fill=BLUE if hi else BLUE_SOFT, tone="white" if hi else "blue")
        text(s, x + 0.25, y + 1.0, bw - 0.4, 0.5, [[R(t, SERIF, 23, "FAFAF8" if hi else INK)]])
        text(s, x + 0.25, y + 1.52, bw - 0.4, 0.8, [[R(d, SANS, 11.5, "C9C9C4" if hi else MUTED)]], spacing=1.1)
        if i < 4:
            arrow_line(s, x + bw + 0.07, y + 1.17, x + bw + gap - 0.07, y + 1.17, color=BLUE, width=2.25)
    y2 = 5.0
    for i, (n, l) in enumerate([("1.8 s", "median rehearsal, both sandboxes, on one $20/month Vultr VM"),
                                 ("0", "lines of the agent's code ever run against production"),
                                 ("2", "different people must approve big changes; every undo is rehearsed too")]):
        bw2 = (W - 2 * MX - 0.44) / 3
        x = MX + i * (bw2 + 0.22)
        box(s, x, y2, bw2, 1.55)
        icon(s, ["gauge", "shield", "users"][i], "blue", x + bw2 - 0.75, y2 + 0.28, 0.42)
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
    badge(s, "play", MX + 0.3, y + 0.28, d=0.5, fill="FFFFFF", tone="red")
    text(s, MX, y + 0.35, half, 0.3, [[R("SANDBOX  ·  CUSTOMERS", MONO, 11, RED)]], align=PP_ALIGN.CENTER)
    text(s, MX, y + 0.62, half, 1.4, [[R("0", MONO, 84, RED)]], align=PP_ALIGN.CENTER)
    text(s, MX, y + 2.2, half, 0.35, [[R("the plan deleted all 1,300, on the double", SANS, 14, MUTED)]], align=PP_ALIGN.CENTER)
    x = MX + half + 0.3
    box(s, x, y, half, hh)
    badge(s, "shield", x + 0.3, y + 0.28, d=0.5, fill=GREEN_SOFT, tone="green")
    text(s, x, y + 0.35, half, 0.3, [[R("PRODUCTION  ·  CUSTOMERS", MONO, 11, MUTED)]], align=PP_ALIGN.CENTER)
    text(s, x, y + 0.62, half, 1.4, [[R("1,300", MONO, 84, INK)]], align=PP_ALIGN.CENTER)
    text(s, x, y + 2.2, half, 0.35, [[R("untouched. Approval locked.", SANS, 14, MUTED)]], align=PP_ALIGN.CENTER)
    y2 = 5.42
    box(s, MX, y2, W - 2 * MX, 1.05)
    text(s, MX + 0.35, y2 + 0.2, 5.6, 0.7, [[R("ANOTHER PLAN SAID", MONO, 9.5, MUTED)], [R("“Audit complete. Read-only: no changes were made.”", SERIF, 16, INK)]], spacing=1.15)
    text(s, MX + 6.3, y2 + 0.2, 5.3, 0.7, [[R("A SEPARATE SANDBOX MEASURED", MONO, 9.5, MUTED)],
                                           [R("300 rows changed.  ", SANS, 16, INK, bold=True), R("The plan lied.", SANS, 16, RED, bold=True)]], spacing=1.15)
    footer(s, 5)
    notes(s, "Here's a plan that deletes every customer. It ran for real, on the double: zero customers left. "
             "Production still has 1,300, and approval locks. And when a plan lies about what it did, the separate "
             "measurement catches that too: another plan said no changes, and changed 300 rows.")



def s06_engine(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, INK)
    kicker(s, "The Consequence Engine", dark=True)
    headline(s, [[("744 refunds planned. ", False), ("104 were right.", True)], [("It kept exactly those.", False)]], dark=True, h=1.7)
    # 744 units of work, 62 x 12: squares big enough, and gaps wide enough, that screen rounding can't show
    cols, rows = 62, 12
    gx, gy = MX, 2.78
    pitch = int(Inches(W - 2 * MX)) // cols
    gap = int(pitch * 0.24)
    for i in range(744):
        r, c = divmod(i, cols)
        sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(gx) + c * pitch, Inches(gy) + r * pitch, pitch - gap, pitch - gap)
        sh.adjustments[0] = 0.18
        sh.fill.solid(); sh.fill.fore_color.rgb = rgb(GREEN_ON_DARK if i in KEPT else "B8434A")
        sh.line.fill.background(); sh.shadow.inherit = False; flat(sh)
    bottom = gy + rows * pitch / 914400
    text(s, MX, bottom + 0.06, 8, 0.3, [[R("Each square: one charge, its refund and its email", SANS, 12, "8E8E88")]])
    text(s, W - MX - 4, bottom + 0.06, 4, 0.3, [[R("■ ", SANS, 12, GREEN_ON_DARK), R("keep 104     ", SANS, 12, "8E8E88"),
                                                 R("■ ", SANS, 12, "B8434A"), R("cut 640", SANS, 12, "8E8E88")]], align=PP_ALIGN.RIGHT)
    y, hh = 5.5, 1.55
    cw = 2.9
    for i, (k, n, l, kc, nc) in enumerate([("KEEP", "$5,136", "the right 104 refunds", GREEN_ON_DARK, "FAFAF8"),
                                           ("CUT", "$32,268", "640 never double-charged", RED_ON_DARK, RED_ON_DARK)]):
        x = MX + i * (cw + 0.22)
        box(s, x, y, cw, hh, fill=D_CARD, line=D_LINE)
        text(s, x + 0.3, y + 0.22, cw - 0.5, 0.3, [[R(k, MONO, 10.5, kc)]])
        text(s, x + 0.3, y + 0.48, cw - 0.4, 0.7, [[R(n, MONO, 34, nc)]])
        text(s, x + 0.3, y + 1.1, cw - 0.5, 0.35, [[R(l, SANS, 12.5, D_MUTED)]])
    x = MX + 2 * (cw + 0.22)
    hw = W - MX - x
    box(s, x, y, hw, hh, fill=D_CARD, line=D_LINE)
    steps = [("contract", "A contract before the plan: 104 to do"), ("graph", "Every change linked into 744 units"),
             ("replayproof", "Replay proves line 1 chose the 640"), ("scissors", "Cut them, re-run, check again")]
    colw = (hw - 0.6) / 2
    for j, (ic, t) in enumerate(steps):
        r, c = divmod(j, 2)
        ix, iy = x + 0.3 + c * colw, y + 0.27 + r * 0.6
        badge(s, ic, ix, iy, d=0.42, fill="1E2A4A", tone="lightblue", pad=0.24)
        text(s, ix + 0.52, iy - 0.02, colw - 0.6, 0.48, [[R(t, SANS, 12, "E4E4E0")]], anchor=MSO_ANCHOR.MIDDLE, spacing=1.0)
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
             ("63→41", "a school's database it had never seen: the trap found, the cut exact", [GREEN] * 41 + [RED] * 22, 13, "beyond the demo")]
    for i, (n, l, dots, per, src) in enumerate(cards):
        x = MX + i * (cw + 0.22)
        box(s, x, y, cw, hh)
        icon(s, "check", "green", x + cw - 0.62, y + 0.32, 0.36)
        text(s, x + 0.28, y + 0.25, cw - 0.95, 0.8, [[R(n, MONO, 40 if len(n) < 5 else 34, INK)]])
        text(s, x + 0.28, y + 1.05, cw - 0.5, 0.9, [[R(l, SANS, 12.5, MUTED)]], spacing=1.1)
        d = 0.27 if per == 6 else 0.13
        step = (cw - 0.56) / per
        rows_n = (len(dots) + per - 1) // per
        top = y + hh - 0.62 - rows_n * step
        for k, c in enumerate(dots):
            r, col = divmod(k, per)
            oval(s, x + 0.28 + col * step, top + r * step, d if per == 6 else min(d, step * 0.82), c)
    text(s, MX, 6.48, W - 2 * MX, 0.3, [[R("Held-out, honestly: 3 of 8 right plans approved outright; the other 5 were sent to a person with a stated reason. "
                                           "No wrong plan was approved.", SANS, 13, MUTED)]])
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
    box(s, MX + 0.3, y - 0.2, 1.12, 0.4, fill=INK, line=None, radius=0)
    vultr_mark(s, MX + 0.42, y - 0.15, 0.3)
    text(s, MX + 0.8, y - 0.14, 0.8, 0.3, [[R("Vultr", SANS, 14, "FAFAF8", bold=True)]])
    widths = [3.25, 4.75, 3.0]
    gap = (W - 2 * MX - 0.5 - sum(widths)) / 2
    x = MX + 0.25
    cols = [("Cloud Compute", "Web app, API and MCP server. Every rehearsal runs in two fresh gVisor sandboxes: no network, no secrets.", []),
            ("Serverless Inference", "Writes what a request means, cross-checks it, and judges the outcome.",
             ["Qwen · contract", "DeepSeek · cross-check", "GLM · jury + vision", "DeepSeek · jury", "MiniMax · jury"]),
            ("Vultr API", "A read-only double of your real server fleet. The key is used once and never kept.", [])]
    for (t, d, chips), w in zip(cols, widths):
        box(s, x, y + 0.3, w, hh, fill=D_CARD, line=D_LINE)
        icon(s, {"Cloud Compute": "cpu", "Serverless Inference": "brain", "Vultr API": "cloud"}[t], "white", x + w - 0.72, y + 0.55, 0.4)
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
    for i, (n, l, c) in enumerate([("MCP", "Any agent plugs in: MCP, SDK, CLI or REST. No approve tool.", "FAFAF8"),
                                    ("$8.64", "The whole build on Vultr, every test run included.", BLUE_ON_DARK)]):
        x = MX + i * (half + 0.22)
        box(s, x, y2, half, 1.0, fill=D_CARD, line=D_LINE)
        if i == 0:
            for k, b in enumerate(["claude", "cursor", "mcp", "python"]):
                icon(s, f"brand-{b}", "white", x + 0.32 + k * 0.52, y2 + 0.3, 0.4)
            text(s, x + 2.5, y2 + 0.16, half - 2.75, 0.7, [[R(l, SANS, 13, D_MUTED)]], anchor=MSO_ANCHOR.MIDDLE, spacing=1.1)
        else:
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
    y, hh = 2.4, 4.05
    lw = 4.6
    box(s, MX, y, lw, hh)
    text(s, MX + 0.3, y + 0.28, lw - 0.5, 0.35, [[R("One catch vs a year of a seat", SANS, 15, INK, bold=True)]])
    column_chart(s, MX + 0.15, y + 0.75, lw - 0.3, hh - 1.0, ["one caught mistake", "a seat, for a year"], (32268, 588), [RED, BLUE], '"$"#,##0', labels=["$32,268", "$588"], maxv=38000, label_size=15)
    x = MX + lw + 0.25
    rw = W - MX - x
    box(s, x, y, rw, hh)
    text(s, x + 0.3, y + 0.28, rw - 0.5, 0.35, [[R("Unit economics, measured on Vultr", SANS, 15, INK, bold=True)]])
    tiles = [("dollar", "$49", "per approver, per month"), ("percent", "73%", "gross margin at full use"),
             ("bolt", "$0.00003", "per rehearsal"), ("brain", "≤ $0.044", "per three-model AI check")]
    tw = (rw - 0.6 - 0.2) / 2
    for k, (ic, n, l) in enumerate(tiles):
        r, c = divmod(k, 2)
        tx, ty = x + 0.3 + c * (tw + 0.2), y + 0.78 + r * 1.06
        box(s, tx, ty, tw, 0.94, fill=PAPER, line=LINE, radius=0.14)
        badge(s, ic, tx + 0.2, ty + 0.2, d=0.54, fill=BLUE_SOFT, tone="blue", pad=0.24)
        text(s, tx + 0.88, ty + 0.12, tw - 1.0, 0.45, [[R(n, MONO, 22, INK)]])
        text(s, tx + 0.88, ty + 0.55, tw - 1.0, 0.3, [[R(l, SANS, 11.5, MUTED)]])
    rows = [("users", "Who buys", "Heads of Operations, Support and Finance Ops"),
            ("law", "Why they must", "EU AI Act Art. 14 and SOC 2 ask for this record"),
            ("code", "How it spreads", "Open core, MIT: self-host on your Vultr in one command")]
    for j, (ic, k, v) in enumerate(rows):
        ry = y + 3.0 + j * 0.34
        icon(s, ic, "blue", x + 0.32, ry + 0.02, 0.24)
        text(s, x + 0.66, ry, rw - 1.0, 0.3, [[R(k + ":  ", SANS, 12, INK, bold=True), R(v, SANS, 12, MUTED)]])
    notes(s, "One caught mistake in the demo is 32 thousand dollars. A seat is 49 dollars a month, so that single catch "
             "pays for it for 55 years. A rehearsal costs us three thousandths of a cent, and the EU AI Act and SOC 2 "
             "already ask companies for exactly this approval record.")


def fade(slide) -> None:
    """A quiet fade between slides (PowerPoint and Keynote play it; it must follow clrMapOvr)."""
    from lxml import etree
    t = etree.SubElement(slide._element, qn("p:transition"), spd="med")
    etree.SubElement(t, qn("p:fade"))



def s12_vision(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, INK)
    section(s, "The bigger picture", 11, dark=True)
    title(s, [[("Code got CI/CD. Money got audits.", False)], [("Agent actions get a double.", True)]], dark=True, h=1.7)
    stages = [("TODAY", "Live on Vultr", "Databases, payments, email, APIs, a real browser and your Vultr fleet."),
              ("NEXT", "Every system agents touch", "More connectors, a Vultr VM per risky rehearsal, approvals in Slack."),
              ("THE STANDARD", "The approval layer for AI", "Every agent action rehearsed, approved, and sealed as evidence.")]
    y, cw = 2.55, (W - 2 * MX - 0.5) / 3
    arrow_line(s, MX + 0.3, y + 0.44, W - MX, y + 0.44, color="3A3A38", width=2.5)
    for i, (k, t, d) in enumerate(stages):
        x = MX + i * (cw + 0.25)
        badge(s, ["check", "zap", "flag"][i], x, y + 0.13, d=0.62, fill=BLUE if i == 0 else "262624", tone="white")
        text(s, x, y + 0.85, cw - 0.2, 0.3, [[R(k, MONO, 10.5, "8E8E88")]])
        text(s, x, y + 1.15, cw - 0.2, 0.5, [[R(t, SERIF, 22, "FAFAF8")]], spacing=1.0)
        text(s, x, y + 1.62, cw - 0.3, 0.8, [[R(d, SANS, 12.5, D_MUTED)]], spacing=1.12)
    # why it wins, against the four judging criteria
    yb, bw = 5.6, (W - 2 * MX - 0.6) / 4
    text(s, MX, yb - 0.4, 6, 0.3, [[R("WHY IT WINS", MONO, 10.5, "8E8E88")]])
    for i, (k, v) in enumerate([("Technology", "gVisor on Cloud Compute, 4 labs on Serverless Inference"),
                                ("Originality", "It approves the right part of a plan, proven by replay"),
                                ("Business value", "One catch pays a seat for 55 years; 73% margin"),
                                ("Presentation", "Live today: judge mode is eight clicks")]):
        x = MX + i * (bw + 0.2)
        box(s, x, yb, bw, 1.05, fill=D_CARD, line=D_LINE, radius=0.16)
        icon(s, ["cpu", "sparkles", "trophy", "eye"][i], "blue", x + bw - 0.5, yb + 0.15, 0.3)
        text(s, x + 0.22, yb + 0.14, bw - 0.4, 0.3, [[R(k, SANS, 12.5, "FFFFFF", bold=True)]])
        text(s, x + 0.22, yb + 0.45, bw - 0.4, 0.55, [[R(v, SANS, 11, D_MUTED)]], spacing=1.05)
    footer(s, 0, dark=True)
    notes(s, "Why it wins: real Vultr tech, a genuinely new idea, measured business value, and it's live. The bigger picture: code got CI/CD, money got audits, and agent actions need the same thing. Today Stunt "
             "Double rehearses databases, payments, email, APIs, browsers and cloud fleets. Next, every system agents "
             "touch. The goal: the approval layer every company uses before an agent acts.")




# ---- final-version overrides: no tiny footers; sections are the kicker ----------------------------------------
ICONS = HERE / "img" / "icons"


def icon(slide, name, tone, x, y, size):
    slide.shapes.add_picture(str(ICONS / f"{name}-{tone}.png"), Inches(x), Inches(y), Inches(size), Inches(size))


def badge(slide, name, x, y, d=0.62, fill=BLUE_SOFT, tone="blue", pad=0.27):
    """An icon in a soft circle: the deck's one recurring ornament."""
    oval(slide, x, y, d, fill)
    icon(slide, name, tone, x + d * pad, y + d * pad, d * (1 - 2 * pad))


def arrow_line(slide, x1, y1, x2, y2, color=FAINT, width=2.0):
    """A straight connector with a real arrowhead."""
    from lxml import etree
    from pptx.enum.shapes import MSO_CONNECTOR
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn("a:tailEnd"))
    tail.set("type", "triangle"); tail.set("w", "med"); tail.set("len", "med")
    return c


def footer(*_a, **_k) -> None:          # page numbers and footers removed: nothing small on any slide
    return None


def section(slide, label, _n=0, dark=False):
    kicker(slide, label, dark=dark)


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


def s01_cover(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    mesh(s)
    wordmark(s, W / 2 - 1.65, 0.8, size=28)
    box(s, W / 2 - 2.55, 1.72, 5.1, 0.42, fill=CARD, line=LINE, radius=0.21)
    text(s, W / 2 - 2.55, 1.72, 5.1, 0.42, [[R("NEW  ", MONO, 10.5, BLUE, bold=True), R("Built for Vultr: Agent Rush  ·  Blast Radius Zero", SANS, 12.5, MUTED)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 0.5, 2.25, W - 1, 1.3, [[R("Let the double", SERIF, 88, INK)]], align=PP_ALIGN.CENTER)
    box(s, 3.05, 3.55, 7.23, 1.45, fill=BLUE, line=None, radius=0.12)
    text(s, 3.05, 3.53, 7.23, 1.4, [[R("take the hit.", SERIF, 88, "FFFFFF", italic=True)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 2.2, 5.3, W - 4.4, 0.8, [[R("Your AI agent tries every action on a throwaway copy of your business first. "
                                         "You see what would happen, and approve the ", SANS, 17, MUTED), R("consequences", SANS, 17, INK, bold=True),
                                       R(", not the code.", SANS, 17, MUTED)]], align=PP_ALIGN.CENTER, spacing=1.15)
    box(s, 3.4, 6.3, 6.53, 0.56, fill=CARD, line=LINE, radius=0.28)
    text(s, 3.4, 6.3, 6.53, 0.56, [[R("$37,404 → 744 refunds", MONO, 13.5, RED), R("  caught  ·  ", MONO, 13.5, MUTED),
                                    R("$5,136 → the right 104", MONO, 13.5, INK)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "In the movies, the star never jumps from the burning building. The stunt double does. Stunt Double gives "
             "every AI agent a double of your business to take the hit first.")


def s02_problem(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    kicker(s, "The problem")
    headline(s, [[("Agents stopped answering.", False)], [("They started acting.", True)]], h=1.7)
    underline(s, 2.62)
    y = 3.05
    for i, (when, what) in enumerate([
        ("JULY 2025", "An AI agent deleted a company's production database, during a code freeze."),
        ("SPRING 2026", "Another deleted a startup's database and its backups, in nine seconds."),
    ]):
        yy = y + i * 1.88
        box(s, MX, yy, 6.9, 1.7)
        badge(s, "alert", MX + 0.32, yy + 0.32, d=0.62, fill=RED_SOFT, tone="red")
        text(s, MX + 1.18, yy + 0.27, 5.5, 0.3, [[R(when, MONO, 11.5, RED)]])
        text(s, MX + 1.18, yy + 0.62, 5.5, 0.9, [[R(what, SERIF, 21, INK)]], spacing=1.05)
    x = MX + 7.15
    dw = W - MX - x
    box(s, x, y, dw, 3.58, fill=INK, line=None, radius=0.2)
    text(s, x + 0.4, y + 0.35, dw - 0.8, 0.3, [[R("AND TODAY'S SAFETY STEP?", MONO, 11, "8E8E88")]])
    text(s, x + 0.4, y + 0.75, dw - 0.8, 1.4, [[R("A manager reads code they can't read, and clicks ", SERIF, 24, "FAFAF8"), R("approve.", SERIF, 24, BLUE_ON_DARK, italic=True)]], spacing=1.05)
    box(s, x + 0.4, y + 2.25, dw - 0.8, 0.015, fill="2C2C2A", line=None, radius=0)
    text(s, x + 0.4, y + 2.45, 1.7, 0.7, [[R("40%+", MONO, 34, RED_ON_DARK)]])
    text(s, x + 2.05, y + 2.45, dw - 2.45, 0.9, [[R("of agentic AI projects will be cancelled by 2027, partly for weak risk controls (Gartner)", SANS, 12.5, "C9C9C4")]], spacing=1.08)
    notes(s, "AI agents don't just answer any more. They refund customers, send email, delete servers. In July 2025 one "
             "deleted a company's production database during a code freeze (eWeek); this spring another wiped a database "
             "and its backups in nine seconds (Information Age, May 2026). And today's safety step is a person reading "
             "code they can't read. Gartner expects over 40% of agentic AI projects to be cancelled by 2027.")


def s07_studies(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    kicker(s, "Why it matters now")
    headline(s, [[("Agents are getting the keys, ", False), ("fast.", True)]], h=0.9)
    underline(s, 1.95)
    y, hh = 2.4, 4.3
    cw = (W - 2 * MX - 0.5) / 3
    panels = [("Enterprise apps with agentic AI", ["2024", "2028"], (0.6, 33), '0"%"', ["<1%", "33%"], 40, "Gartner"),
              ("Work decisions made by agents", ["2024", "2028"], (0.3, 15), '0"%"', ["0%", "15%+"], 18, "Gartner"),
              ("AI agents market", ["2025", "2030"], (7.84, 52.62), '"$"0.0"B"', None, 62, "MarketsandMarkets")]
    for i, (lab, cats, vals, fmt, labels, maxv, src) in enumerate(panels):
        x = MX + i * (cw + 0.25)
        box(s, x, y, cw, hh)
        text(s, x + 0.32, y + 0.3, cw - 0.55, 0.4, [[R(lab, SANS, 16, INK, bold=True)]])
        column_chart(s, x + 0.2, y + 0.85, cw - 0.4, hh - 1.4, cats, vals, [BLUE_SOFT, BLUE], fmt, labels=labels or ["$7.8B", "$52.6B"], maxv=maxv, label_size=17)
        text(s, x + 0.32, y + hh - 0.45, cw - 0.55, 0.3, [[R(src, MONO, 10, FAINT)]])
    notes(s, "Why now: Gartner expects a third of enterprise software to include agentic AI by 2028, up from under 1%, "
             "and agents to make at least 15% of day-to-day work decisions. The AI agents market grows from about $7.8 "
             "billion in 2025 to $52.6 billion by 2030 (MarketsandMarkets). Every one of those agents needs a stunt double.")


def s11_close(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, INK)
    s.shapes.add_picture(str(IMG / "close-16x9.jpg"), 0, 0, Inches(W), Inches(H))
    gradient_veil(s, 0, 0, W, H, "05070D", 0.25, 0.7, angle=90)
    wordmark(s, W / 2 - 1.55, 0.85, size=26, dark=True)
    text(s, 0.5, 1.85, W - 1, 2.4, [[R("Agents should be bold.", SERIF, 62, "FFFFFF")],
                                    [R("Businesses should be ", SERIF, 62, "FFFFFF"), R("safe.", SERIF, 62, "9DB8FF", italic=True)]], align=PP_ALIGN.CENTER, spacing=0.95)
    bx, by, bw, bh = 2.55, 4.4, 8.23, 1.7
    box(s, bx, by, bw, bh, fill="FFFFFF", line=None, radius=0.24)
    qr = HERE / "qr.png"
    if qr.exists():
        s.shapes.add_picture(str(qr), Inches(bx + 0.27), Inches(by + 0.22), Inches(1.26), Inches(1.26))
    text(s, bx + 1.85, by + 0.3, bw - 2.1, 0.5, [[R("149-28-206-186.sslip.io", MONO, 24, INK)]])
    text(s, bx + 1.85, by + 0.85, bw - 2.1, 0.35, [[R("Judge mode: eight clicks, each a real rehearsal on Vultr.", SANS, 15, MUTED)]])
    text(s, bx + 1.85, by + 1.2, bw - 2.1, 0.3, [[R("github.com/vidigoat/stunt-double", MONO, 12, MUTED)]])
    text(s, 0.5, 6.45, W - 1, 0.45, [[R("Let the double ", SERIF, 22, "FFFFFF"), R("take the hit.", SERIF, 22, "9DB8FF", italic=True)]], align=PP_ALIGN.CENTER)
    notes(s, "Agents should be bold. Businesses should be safe. Now they can be both. Try it live: judge mode is eight "
             "clicks. Let the double take the hit. Photo: 'Stormy sunset over the Waimakariri River basin, New Zealand', "
             "Wikimedia Commons, CC BY-SA 4.0.")


SLIDES = (s01_cover, s02_problem, s04_how, s05_containment, s06_engine, s07_proof, s07_studies, s08_vultr, s09_business, s12_vision, s11_close)


def build() -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    for i, f in enumerate(SLIDES, 1):
        CUR[0] = i
        f(prs)
    for sl in list(prs.slides)[1:]:
        fade(sl)
    prs.core_properties.title = "Stunt Double"
    prs.core_properties.subject = "Let the double take the hit. Vultr: Agent Rush, Challenge 01."
    prs.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
