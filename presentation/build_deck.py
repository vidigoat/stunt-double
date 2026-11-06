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
TOTAL = 12
CUR = [0]   # the slide being built (set by build())

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
    text(slide, W - MX - 2, H - 0.48, 2, 0.25, [[R(f"{CUR[0]:02d} / {TOTAL}", MONO, 9, c)]], align=PP_ALIGN.RIGHT)


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


# ---- extra primitives for the presentation layer ----------------------------------------------------------------
IMG = HERE / "img"


def gradient_bg(slide, c1: str, c2: str, angle: float = 135.0) -> None:
    f = slide.background.fill
    f.gradient()
    f.gradient_angle = angle
    st = f.gradient_stops
    st[0].color.rgb, st[0].position = rgb(c1), 0.0
    st[1].color.rgb, st[1].position = rgb(c2), 1.0


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


def section(slide, label: str, n: int, dark=False):
    """Kicker with a section number: '02  THE SHIFT'."""
    text(slide, MX, 0.62, 9, 0.3, [[R(f"{CUR[0] - 1:02d}", MONO, 10.5, BLUE_ON_DARK if dark else BLUE), R("   " + label.upper(), MONO, 10.5, D_MUTED if dark else MUTED)]])


def title(slide, parts, dark=False, size=42, y=0.98, h=1.6):
    headline(slide, parts, dark=dark, y=y, size=size, h=h)


def logo(slide, x, y, size, dark=False):
    slide.shapes.add_picture(str(IMG / ("logo-dark.png" if dark else "logo-light.png")), Inches(x), Inches(y), Inches(size), Inches(size))


def arrow(slide, x, y, w, h, color=FAINT):
    s = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = rgb(color); s.line.fill.background(); s.shadow.inherit = False
    flat(s)


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


# ---- slides -------------------------------------------------------------------------------------------------------
def s01_cover(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    gradient_bg(s, "070B16", "0E1E4A", angle=120)
    box(s, 0, H - 0.07, W, 0.07, fill=BLUE, line=None, radius=0)                       # a thin signal line at the base
    logo(s, MX, 0.7, 0.62, dark=True)
    text(s, MX + 0.78, 0.78, 4, 0.5, [[R("Stunt ", SERIF, 24, "FAFAF8"), R("Double", SERIF, 24, "FAFAF8", italic=True)]])
    text(s, W - MX - 5.5, 0.86, 5.5, 0.3, [[R("VULTR: AGENT RUSH  ·  CHALLENGE 01", MONO, 10.5, "8EA3D6")]], align=PP_ALIGN.RIGHT)
    text(s, MX - 0.05, 1.95, 11.5, 1.4, [[R("Let the double", SERIF, 96, "FAFAF8")]])
    box(s, MX, 3.35, 7.75, 1.5, fill=BLUE, line=None, radius=0.1)
    text(s, MX + 0.3, 3.33, 7.4, 1.45, [[R("take the hit.", SERIF, 96, "FFFFFF", italic=True)]], anchor=MSO_ANCHOR.MIDDLE)
    text(s, MX, 5.35, 7.6, 0.9, [[R("Every action an AI agent wants to take is rehearsed first on a copy of your business, "
                                  "in a sealed Vultr sandbox. You approve what would happen, not code.", SANS, 17, "C9D3EE")]], spacing=1.15)
    # the one number that sells it
    box(s, W - MX - 3.6, 3.55, 3.6, 2.6, fill=None, line="2A3B6B", radius=0.2, width=1)
    text(s, W - MX - 3.3, 3.8, 3.1, 0.3, [[R("ONE PLAN, CAUGHT", MONO, 10, "8EA3D6")]])
    text(s, W - MX - 3.3, 4.12, 3.1, 0.7, [[R("$37,404", MONO, 34, RED_ON_DARK)]])
    text(s, W - MX - 3.3, 4.75, 3.1, 0.35, [[R("planned for 744 people", SANS, 13, "C9D3EE")]])
    text(s, W - MX - 3.3, 5.2, 3.1, 0.7, [[R("$5,136", MONO, 34, GREEN_ON_DARK)]])
    text(s, W - MX - 3.3, 5.83, 3.1, 0.35, [[R("approved: the right 104", SANS, 13, "C9D3EE")]])
    text(s, MX, H - 0.55, 8, 0.25, [[R("149-28-206-186.sslip.io  ·  github.com/vidigoat/stunt-double", MONO, 9.5, "6F80AE")]])
    notes(s, "In the movies, the star never jumps from the burning building. The stunt double does. "
             "Stunt Double gives every AI agent a double of your business to take the hit first.")


def s02_shift(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    section(s, "The shift", 1)
    title(s, [[("AI agents are getting the keys.", False)], [("Their mistakes are real.", True)]], h=1.7)
    underline(s, 2.62)
    y, hh = 3.0, 3.65
    cw = 2.95
    for i, (lab, cats, vals, labels, maxv) in enumerate([
            ("ENTERPRISE APPS WITH AGENTIC AI", ["2024", "2028"], (0.6, 33), ["<1%", "33%"], 40),
            ("WORK DECISIONS MADE BY AGENTS", ["2024", "2028"], (0.3, 15), ["0%", "15%+"], 18)]):
        x = MX + i * (cw + 0.22)
        box(s, x, y, cw, hh)
        text(s, x + 0.28, y + 0.26, cw - 0.45, 0.5, [[R(lab, MONO, 9.5, MUTED)]], spacing=1.1)
        column_chart(s, x + 0.15, y + 0.75, cw - 0.3, hh - 1.2, cats, vals, [BLUE_SOFT, BLUE], '0"%"', labels=labels, maxv=maxv, label_size=17)
        text(s, x + 0.28, y + hh - 0.4, cw - 0.45, 0.25, [[R("Source: Gartner", MONO, 8.5, FAINT)]])
    x = MX + 2 * (cw + 0.22) + 0.03
    dw = W - MX - x
    box(s, x, y, dw, hh, fill=INK, line=None, radius=0.2)
    for j, (when, what) in enumerate([("JULY 2025", "An AI agent deleted a company's production database, during a code freeze."),
                                     ("SPRING 2026", "Another deleted a startup's database and its backups, in nine seconds.")]):
        yy = y + 0.3 + j * 1.08
        text(s, x + 0.38, yy, dw - 0.7, 0.3, [[R(when, MONO, 10, RED_ON_DARK)]])
        text(s, x + 0.38, yy + 0.3, dw - 0.7, 0.75, [[R(what, SERIF, 17, "FAFAF8")]], spacing=1.04)
    box(s, x + 0.38, y + 2.5, dw - 0.76, 0.02, fill="2C2C2A", line=None, radius=0)
    text(s, x + 0.38, y + 2.62, 1.6, 0.6, [[R("40%+", MONO, 30, RED_ON_DARK)]])
    text(s, x + 1.95, y + 2.62, dw - 2.3, 0.85, [[R("of agentic AI projects will be cancelled by 2027, partly for inadequate risk controls.", SANS, 11.5, "C9C9C4")]], spacing=1.08)
    text(s, x + 0.38, y + hh - 0.36, dw - 0.7, 0.25, [[R("eWeek · Information Age · Gartner", MONO, 8.5, "77776F")]])
    footer(s, 0)
    notes(s, "AI agents are moving from answering to acting: Gartner expects a third of enterprise software to include "
             "agentic AI by 2028, and agents to make at least 15% of daily work decisions. And when they're wrong, it's real: "
             "in July 2025 an agent deleted a production database during a code freeze; this spring another wiped a "
             "database and its backups in nine seconds. Today's safety step is a person reading code they can't read.")


def s04_solution(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    section(s, "The solution", 3)
    title(s, [[("Every action is rehearsed on a ", False), ("double", True), (" first.", False)]], h=0.9)
    underline(s, 1.95)
    steps = [("Copy", "A fresh copy of the business the agent needs: data, payments, email, APIs, servers."),
             ("Rehearse", "The plan runs in sandbox 1: gVisor, no network, no secrets."),
             ("Measure", "Sandbox 2, our code only, measures what really changed."),
             ("Approve", "A person approves the consequences, in plain English."),
             ("Replay", "Only those measured effects reach production, after a drift check.")]
    y, ch_w = 2.55, 0.22
    bw = (W - 2 * MX - ch_w * 4 - 0.1 * 8) / 5
    x = MX
    for i, (t, d) in enumerate(steps):
        hi = i == 3
        box(s, x, y, bw, 2.75, fill=INK if hi else CARD, line=None if hi else LINE, radius=0.2)
        oval(s, x + 0.28, y + 0.3, 0.46, BLUE if hi else BLUE_SOFT)
        text(s, x + 0.28, y + 0.3, 0.46, 0.46, [[R(str(i + 1), MONO, 15, "FFFFFF" if hi else BLUE)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(s, x + 0.28, y + 0.98, bw - 0.4, 0.5, [[R(t, SERIF, 23, "FAFAF8" if hi else INK)]])
        text(s, x + 0.28, y + 1.55, bw - 0.4, 1.1, [[R(d, SANS, 12, "C9C9C4" if hi else MUTED)]], spacing=1.1)
        x += bw
        if i < 4:
            arrow(s, x + 0.1, y + 1.2, ch_w, 0.34, color="C9C9C2")
            x += ch_w + 0.2
    box(s, MX, 5.62, W - 2 * MX, 0.95, fill=BLUE_SOFT, line=None, radius=0.18)
    text(s, MX + 0.4, 5.62, W - 2 * MX - 0.8, 0.95, [[R("The agent's own code never runs against production.  ", SANS, 16, INK, bold=True),
                                                       R("A rehearsal takes 1.8 s (median, both sandboxes, on one $20/month Vultr VM).", SANS, 16, MUTED)]], anchor=MSO_ANCHOR.MIDDLE)
    footer(s, 4)
    notes(s, "Stunt Double gives every agent a double. Each action is rehearsed first on a copy of the business, sealed in "
             "a gVisor sandbox on Vultr. A second sandbox measures what truly changed. A person approves that, and only "
             "those measured effects are replayed for real.")


def s05_approve(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    section(s, "What a person sees", 4)
    title(s, [[("Approve ", False), ("consequences,", True), (" not code.", False)]], h=0.9)
    underline(s, 1.95)
    # the approval card, as the product shows it
    x, y, w, h = MX, 2.35, W - 2 * MX, 4.3
    box(s, x, y, w, h, fill=CARD, line=LINE, radius=0.22)
    box(s, x, y, w, 0.55, fill="F4F4F1", line=None, radius=0)
    oval(s, x + 0.3, y + 0.21, 0.13, RED)
    text(s, x + 0.55, y + 0.15, 5, 0.3, [[R("APPROVAL REQUIRED", MONO, 10.5, INK)]])
    text(s, x + w - 6.3, y + 0.15, 6.0, 0.3, [[R("rehearsed in sd-d002755d · gVisor · 1.9 s · destroyed", MONO, 9.5, MUTED)]], align=PP_ALIGN.RIGHT)
    text(s, x + 0.4, y + 0.8, w - 0.8, 0.4, [[R("“Refund everyone who was double-charged last week and send them an apology.”", SANS, 15, MUTED)]])
    text(s, x + 0.4, y + 1.22, w - 0.8, 0.5, [[R("If approved: $37,404 to 744 people, 744 emails, 744 charges changed. ", SANS, 17, INK),
                                                R("Nothing else leaves the sandbox.", SANS, 17, MUTED)]])
    tiles = [("MONEY OUT", "$37,404", RED), ("EMAILS", "744", INK), ("VIPS EMAILED", "8", INK), ("VERDICT", "Critical", RED)]
    tw = (w - 0.8 - 0.6) / 4
    for k, (lab, v, c) in enumerate(tiles):
        tx = x + 0.4 + k * (tw + 0.2)
        box(s, tx, y + 1.9, tw, 1.0, fill=RED_SOFT if k == 3 else PAPER, line=LINE, radius=0.14)
        text(s, tx + 0.22, y + 2.02, tw - 0.4, 0.25, [[R(lab, MONO, 9, MUTED)]])
        text(s, tx + 0.22, y + 2.3, tw - 0.4, 0.55, [[R(v, SERIF if k == 3 else MONO, 26, c)]])
    box(s, x + 0.4, y + 3.1, w - 0.8, 0.95, fill=RED_SOFT, line="F3B9BB", radius=0.14)
    text(s, x + 0.65, y + 3.2, w - 1.3, 0.8, [[R("✕  Plan refunds 640 customers who were never double-charged.", SANS, 16, INK, bold=True)],
                                              [R("Three AI models from different labs each found it on their own: GLM, DeepSeek and MiniMax on Vultr. Approval locks until a person writes why.", SANS, 12.5, MUTED)]], spacing=1.15)
    footer(s, 5)
    notes(s, "This is what a person sees: not code, but what would happen. 37 thousand dollars to 744 people, and three "
             "AI models from different labs each found that 640 of them were never double-charged.")


def s06_containment(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    section(s, "Containment  ·  Challenge 01", 5)
    title(s, [[("The blast radius is ", False), ("zero.", True)]], h=0.9)
    underline(s, 1.95)
    y, hh = 2.4, 2.85
    half = (W - 2 * MX - 0.3) / 2
    box(s, MX, y, half, hh, fill=RED_SOFT, line="F3B9BB")
    text(s, MX, y + 0.35, half, 0.3, [[R("THE DOUBLE  ·  CUSTOMERS", MONO, 11, RED)]], align=PP_ALIGN.CENTER)
    text(s, MX, y + 0.62, half, 1.4, [[R("0", MONO, 88, RED)]], align=PP_ALIGN.CENTER)
    text(s, MX, y + 2.25, half, 0.35, [[R("“Clean up the customer table” deleted all 1,300", SANS, 14, MUTED)]], align=PP_ALIGN.CENTER)
    x = MX + half + 0.3
    box(s, x, y, half, hh)
    text(s, x, y + 0.35, half, 0.3, [[R("PRODUCTION  ·  CUSTOMERS", MONO, 11, MUTED)]], align=PP_ALIGN.CENTER)
    text(s, x, y + 0.62, half, 1.4, [[R("1,300", MONO, 88, INK)]], align=PP_ALIGN.CENTER)
    text(s, x, y + 2.25, half, 0.35, [[R("untouched. Approval locked.", SANS, 14, MUTED)]], align=PP_ALIGN.CENTER)
    y2 = 5.5
    box(s, MX, y2, W - 2 * MX, 1.05)
    text(s, MX + 0.35, y2 + 0.2, 5.8, 0.7, [[R("ANOTHER PLAN SAID", MONO, 9.5, MUTED)], [R("“Audit complete. Read-only: no changes were made.”", SERIF, 16, INK)]], spacing=1.15)
    text(s, MX + 6.4, y2 + 0.2, 5.2, 0.7, [[R("A SEPARATE SANDBOX MEASURED", MONO, 9.5, MUTED)],
                                           [R("300 rows changed.  ", SANS, 16, INK, bold=True), R("The plan lied.", SANS, 16, RED, bold=True)]], spacing=1.15)
    footer(s, 6)
    notes(s, "Here's a plan that deletes every customer. It ran for real, on the double: zero customers left. Production "
             "still has 1,300, and approval locks. And because our own code measures the result in a second sandbox, "
             "a plan that lies about what it did is caught too.")


def s07_engine(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, INK)
    section(s, "The Consequence Engine", 6, dark=True)
    title(s, [[("744 refunds planned. ", False), ("104 were right.", True)], [("It kept exactly those.", False)]], dark=True, h=1.7)
    cols, rows = 93, 8
    gx, gy = MX, 2.85
    cell = (W - 2 * MX) / cols
    sq = cell * 0.8
    for i in range(744):
        r, c = divmod(i, cols)
        box(s, gx + c * cell, gy + r * cell, sq, sq, fill=GREEN_ON_DARK if i in KEPT else "C2474B", line=None, radius=0)
    text(s, MX, gy + rows * cell + 0.08, 8, 0.25, [[R("each square is one unit of work: a charge, its refund and its email", MONO, 9, "77776F")]])
    text(s, W - MX - 4, gy + rows * cell + 0.08, 4, 0.25, [[R("■ ", MONO, 9, GREEN_ON_DARK), R("keep 104   ", MONO, 9, "77776F"),
                                                             R("■ ", MONO, 9, "C2474B"), R("cut 640", MONO, 9, "77776F")]], align=PP_ALIGN.RIGHT)
    y, cw = 4.42, 3.4
    for i, (k, n, l, kc, nc) in enumerate([("KEEP", "$5,136", "104 refunds · 104 emails", GREEN_ON_DARK, "FAFAF8"),
                                           ("CUT", "$32,268", "640 refunds to people never double-charged", RED_ON_DARK, RED_ON_DARK)]):
        x = MX + i * (cw + 0.22)
        box(s, x, y, cw, 2.15, fill=D_CARD, line=D_LINE)
        text(s, x + 0.32, y + 0.28, cw - 0.6, 0.3, [[R(k, MONO, 10.5, kc)]])
        text(s, x + 0.32, y + 0.62, cw - 0.5, 0.9, [[R(n, MONO, 42, nc)]])
        text(s, x + 0.32, y + 1.5, cw - 0.6, 0.5, [[R(l, SANS, 13, D_MUTED)]])
    x = MX + 2 * (cw + 0.22)
    cw2 = W - MX - x
    box(s, x, y, cw2, 2.15, fill=D_CARD, line=D_LINE)
    text(s, x + 0.32, y + 0.28, cw2 - 0.6, 0.3, [[R("HOW", MONO, 10.5, BLUE_ON_DARK)]])
    for j, (n, t) in enumerate([("1", "Contract, before the plan: 104 to do"), ("2", "Effect graph: 744 units of work"),
                                ("3", "Replay proof: line 1 chose the 640"), ("4", "Cut, re-run fresh, checked again")]):
        text(s, x + 0.32, y + 0.64 + j * 0.34, cw2 - 0.5, 0.3, [[R(n + "   ", MONO, 11, BLUE_ON_DARK), R(t, SANS, 12, "DDDDDA")]])
    footer(s, 7, dark=True)
    notes(s, "Now the hard case: a plan that's only partly wrong. Before the plan exists, the engine writes down what the "
             "request means: 104 refunds. The plan does 744. Replaying it proves line 1 chose the 640 wrong ones. The "
             "engine cuts them out, re-runs just the 104 in a fresh sandbox, and every check passes. Nobody else does this: "
             "guardrails block or allow; this approves exactly the right part.")


def s08_features(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    section(s, "Everything it does", 7)
    title(s, [[("Everything an agent does, ", False), ("rehearsed.", True)]], h=0.9)
    underline(s, 1.95)
    groups = [("FOR THE PERSON APPROVING", BLUE, [
                  ("Plain-English consequences", "money out, people, emails, rows"),
                  ("Two-person approval", "for big changes and every undo"),
                  ("Rehearsed undo", "regret it? the undo is rehearsed too"),
                  ("Signed evidence", "Ed25519 record your browser verifies")]),
              ("FOR THE BUSINESS", GREEN, [
                  ("Works on your systems", "Postgres, Vultr fleet, any API, a browser"),
                  ("Every catch becomes a rule", "the same mistake blocked, no AI"),
                  ("Audit trail", "EU AI Act and SOC 2 change records"),
                  ("Slack and email", "reviewers pinged with a link")]),
              ("UNDER THE HOOD", INK, [
                  ("Two-phase gVisor sandbox", "no network, no secrets, destroyed"),
                  ("AI jury of three labs", "each investigates with read-only SQL"),
                  ("Intent contract + proof", "promises before the plan, replay after"),
                  ("MCP, SDK, CLI, REST", "any agent plugs in; no approve tool")])]
    cw = (W - 2 * MX - 0.5) / 3
    y = 2.35
    for i, (g, c, items) in enumerate(groups):
        x = MX + i * (cw + 0.25)
        box(s, x, y, cw, 4.25)
        box(s, x, y, cw, 0.07, fill=c, line=None, radius=0)
        text(s, x + 0.3, y + 0.3, cw - 0.5, 0.3, [[R(g, MONO, 10, c if c != INK else MUTED)]])
        for j, (t, d) in enumerate(items):
            yy = y + 0.78 + j * 0.85
            text(s, x + 0.3, yy, cw - 0.55, 0.35, [[R(t, SANS, 15, INK, bold=True)]])
            text(s, x + 0.3, yy + 0.34, cw - 0.55, 0.35, [[R(d, SANS, 12, MUTED)]])
    footer(s, 8)
    notes(s, "Stunt Double is a full layer between agents and everything they touch. For the approver: plain-English "
             "consequences, two-person approval, a rehearsed undo and signed evidence. For the business: it works on your "
             "real Postgres, Vultr fleet, APIs and browser flows, and every catch becomes a rule. Under the hood: a "
             "two-phase gVisor sandbox, an AI jury from three labs, intent contracts and proof by replay.")


def s09_proof(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    section(s, "Proof, measured live on Vultr", 8)
    title(s, [[("Bad plans stopped. Good ones ", False), ("approved.", True)]], h=0.9)
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
    text(s, MX, 6.48, W - 2 * MX, 0.3, [[R("Honestly: on the held-out cases 3 of 8 right plans were approved outright; the other 5 went to a person with a stated reason. "
                                           "No wrong plan was approved. Every case and miss is in the repo.", SANS, 11, MUTED)]])
    footer(s, 9)
    notes(s, "Measured live, not on slides. Twelve of twelve bad plans stopped, eight of eight good ones approved, every "
             "wrong plan stopped on cases we wrote down before running them, and the same engine found the trap in a "
             "school's database it had never seen. 201 automated tests run in CI.")


def s10_vultr(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, INK)
    section(s, "Built on Vultr", 9, dark=True)
    title(s, [[("One VM. Four labs. ", False), ("Disposable doubles.", True)]], dark=True, h=0.9)
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
                                    ("$8.64", "The whole build on Vultr, every test run included.", BLUE_ON_DARK)]):
        x = MX + i * (half + 0.22)
        box(s, x, y2, half, 1.0, fill=D_CARD, line=D_LINE)
        text(s, x + 0.3, y2 + 0.16, 1.9, 0.7, [[R(n, MONO, 32, c)]], anchor=MSO_ANCHOR.MIDDLE)
        text(s, x + 2.15, y2 + 0.16, half - 2.4, 0.7, [[R(l, SANS, 13, D_MUTED)]], anchor=MSO_ANCHOR.MIDDLE, spacing=1.1)
    footer(s, 10, dark=True)
    notes(s, "All of it runs on Vultr: one Cloud Compute VM with disposable gVisor sandboxes, four labs' models on "
             "Serverless Inference, and the Vultr API for a read-only double of your fleet. The whole build cost under "
             "nine dollars.")


def s11_business(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    section(s, "Business", 10)
    title(s, [[("One caught mistake pays for a seat for ", False), ("55 years.", True)]], size=38, h=0.9)
    underline(s, 1.95)
    y, hh = 2.4, 3.95
    lw = 4.6
    box(s, MX, y, lw, hh)
    text(s, MX + 0.3, y + 0.25, lw - 0.5, 0.3, [[R("ONE CATCH VS ONE SEAT", MONO, 10.5, MUTED)]])
    column_chart(s, MX + 0.2, y + 0.65, lw - 0.4, hh - 1.15, ["one caught mistake", "a seat, per year"], (32268, 588), [RED, BLUE], '"$"#,##0', maxv=38000, label_size=16)
    text(s, MX + 0.3, y + hh - 0.42, lw - 0.5, 0.25, [[R("The demo's refund trap vs $49 × 12", MONO, 8.5, FAINT)]])
    x = MX + lw + 0.25
    rw = W - MX - x
    box(s, x, y, rw, hh)
    text(s, x + 0.3, y + 0.25, rw - 0.5, 0.3, [[R("UNIT ECONOMICS, MEASURED ON VULTR", MONO, 10.5, MUTED)]])
    tiles = [("$49", "per approver, per month"), ("73%", "gross margin at full use"), ("$0.00003", "per rehearsal"), ("$52.6B", "AI agents market by 2030")]
    tw = (rw - 0.6 - 0.2) / 2
    for k, (n, l) in enumerate(tiles):
        r, c = divmod(k, 2)
        tx, ty = x + 0.3 + c * (tw + 0.2), y + 0.68 + r * 1.12
        box(s, tx, ty, tw, 0.98, fill=PAPER, line=LINE, radius=0.14)
        text(s, tx + 0.22, ty + 0.12, tw - 0.4, 0.5, [[R(n, MONO, 24, INK)]])
        text(s, tx + 0.22, ty + 0.6, tw - 0.4, 0.3, [[R(l, SANS, 11.5, MUTED)]])
    text(s, x + 0.3, y + 3.05, rw - 0.6, 0.8, [[R("Who buys: ", SANS, 12, INK, bold=True), R("Heads of Operations, Support and Finance Ops.  ", SANS, 12, MUTED),
                                                R("Why they must: ", SANS, 12, INK, bold=True), R("EU AI Act Art. 14 & 12 (human oversight, records), SOC 2 CC8.1 (approved changes).  ", SANS, 12, MUTED),
                                                R("Open core: ", SANS, 12, INK, bold=True), R("MIT, self-host in one command.  ", SANS, 12, MUTED), R("Market: MarketsandMarkets, 2025.", SANS, 10, FAINT)]], spacing=1.15)
    footer(s, 11)
    notes(s, "One caught mistake in the demo is 32 thousand dollars; a seat is 49 dollars a month, so that single catch "
             "pays for it for 55 years. A rehearsal costs us three thousandths of a cent, and the EU AI Act and SOC 2 "
             "already ask companies for exactly this approval record.")


def s12_vision(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); gradient_bg(s, "070B16", "0E1E4A", angle=120)
    section(s, "The bigger picture", 11, dark=True)
    title(s, [[("Code got CI/CD. Money got audits.", False)], [("Agent actions get a double.", True)]], dark=True, h=1.7)
    stages = [("TODAY", "Live on Vultr", "Databases, payments, email, APIs, a real browser and your Vultr fleet."),
              ("NEXT", "Every system agents touch", "More connectors, a Vultr VM per risky rehearsal, approvals in Slack."),
              ("THE STANDARD", "The approval layer for AI", "Every agent action rehearsed, approved, and sealed as evidence.")]
    y, cw = 2.55, (W - 2 * MX - 0.5) / 3
    box(s, MX, y + 0.42, W - 2 * MX, 0.04, fill="2A3B6B", line=None, radius=0)
    for i, (k, t, d) in enumerate(stages):
        x = MX + i * (cw + 0.25)
        oval(s, x, y + 0.3, 0.28, BLUE if i == 0 else "2A3B6B")
        text(s, x, y + 0.85, cw - 0.2, 0.3, [[R(k, MONO, 10.5, "8EA3D6")]])
        text(s, x, y + 1.15, cw - 0.2, 0.5, [[R(t, SERIF, 22, "FAFAF8")]], spacing=1.0)
        text(s, x, y + 1.62, cw - 0.3, 0.8, [[R(d, SANS, 12.5, "C9D3EE")]], spacing=1.12)
    # why it wins, against the four judging criteria
    yb, bw = 5.6, (W - 2 * MX - 0.6) / 4
    text(s, MX, yb - 0.4, 6, 0.3, [[R("WHY IT WINS", MONO, 10.5, "8EA3D6")]])
    for i, (k, v) in enumerate([("Application of technology", "gVisor on Cloud Compute, 4 labs on Serverless Inference"),
                                ("Originality", "It approves the right part of a plan, proven by replay"),
                                ("Business value", "One catch pays a seat for 55 years; 73% margin"),
                                ("Presentation", "Live today: judge mode is eight clicks")]):
        x = MX + i * (bw + 0.2)
        box(s, x, yb, bw, 1.05, fill="111A33", line="2A3B6B", radius=0.16)
        text(s, x + 0.22, yb + 0.14, bw - 0.4, 0.3, [[R(k, SANS, 12.5, "FFFFFF", bold=True)]])
        text(s, x + 0.22, yb + 0.45, bw - 0.4, 0.55, [[R(v, SANS, 11, "C9D3EE")]], spacing=1.05)
    footer(s, 0, dark=True)
    notes(s, "Why it wins: real Vultr tech, a genuinely new idea, measured business value, and it's live. The bigger picture: code got CI/CD, money got audits, and agent actions need the same thing. Today Stunt "
             "Double rehearses databases, payments, email, APIs, browsers and cloud fleets. Next, every system agents "
             "touch. The goal: the approval layer every company uses before an agent acts.")


def s13_why(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, PAPER)
    section(s, "Why it wins", 12)
    title(s, [[("Built for ", False), ("Blast Radius Zero,", True), (" end to end.", False)]], h=0.9)
    underline(s, 1.95)
    cols = [("Application of technology", ["gVisor sandboxes on Cloud Compute", "4 labs' models on Serverless Inference", "A double of your Vultr fleet", "201 tests + live end-to-end"]),
            ("Originality", ["Approves the right part of a plan", "Promises written before the plan", "Proof by replay: plans can't lie"]),
            ("Business value", ["One catch pays a seat for 55 years", "73% gross margin, measured", "Required by the EU AI Act and SOC 2"]),
            ("Presentation", ["Live: judge mode is 8 clicks", "Every claim linked to a measured eval", "Open source, MIT"])]
    cw = (W - 2 * MX - 0.66) / 4
    y = 2.35
    for i, (t, pts) in enumerate(cols):
        x = MX + i * (cw + 0.22)
        box(s, x, y, cw, 4.2, fill=INK if i == 1 else CARD, line=None if i == 1 else LINE)
        dark = i == 1
        text(s, x + 0.3, y + 0.3, cw - 0.5, 0.3, [[R(f"0{i + 1}", MONO, 11, BLUE_ON_DARK if dark else BLUE)]])
        text(s, x + 0.3, y + 0.65, cw - 0.5, 0.9, [[R(t, SERIF, 22, "FAFAF8" if dark else INK)]], spacing=1.0)
        for j, p in enumerate(pts):
            yy = y + 1.7 + j * 0.62
            oval(s, x + 0.32, yy + 0.09, 0.09, BLUE_ON_DARK if dark else BLUE)
            text(s, x + 0.55, yy, cw - 0.8, 0.55, [[R(p, SANS, 12, "DDDDDA" if dark else INK)]], spacing=1.05)
    footer(s, 13)
    notes(s, "Why it should win. Application of technology: gVisor on Cloud Compute, four labs' models on Serverless "
             "Inference, a double of a real Vultr fleet. Originality: it approves exactly the right part of a plan, with "
             "promises written before the plan and proof by replay. Business value: one catch pays for a seat for 55 "
             "years. And it's live: judge mode is eight clicks.")


def s14_close(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6]); bg(s, INK)
    s.shapes.add_picture(str(IMG / "close-16x9.jpg"), 0, 0, Inches(W), Inches(H))
    gradient_veil(s, 0, 0, W, H, "05070D", 0.15, 0.78, angle=90)
    logo(s, W / 2 - 0.32, 0.85, 0.64, dark=True)
    text(s, 0.5, 1.75, W - 1, 2.4, [[R("Agents should be bold.", SERIF, 60, "FFFFFF")],
                                    [R("Businesses should be ", SERIF, 60, "FFFFFF"), R("safe.", SERIF, 60, "9DB8FF", italic=True)]], align=PP_ALIGN.CENTER, spacing=0.95)
    bx, by, bw, bh = 2.55, 4.45, 8.23, 1.65
    box(s, bx, by, bw, bh, fill="FFFFFF", line=None, radius=0.22)
    qr = HERE / "qr.png"
    if qr.exists():
        s.shapes.add_picture(str(qr), Inches(bx + 0.25), Inches(by + 0.2), Inches(1.25), Inches(1.25))
    text(s, bx + 1.85, by + 0.28, bw - 2.1, 0.5, [[R("149-28-206-186.sslip.io", MONO, 24, INK)]])
    text(s, bx + 1.85, by + 0.82, bw - 2.1, 0.35, [[R("Judge mode: eight clicks, each a real rehearsal on Vultr.", SANS, 14, MUTED)]])
    text(s, bx + 1.85, by + 1.17, bw - 2.1, 0.3, [[R("github.com/vidigoat/stunt-double", MONO, 11.5, MUTED)]])
    text(s, 0.5, 6.45, W - 1, 0.4, [[R("Let the double ", SERIF, 20, "FFFFFF"), R("take the hit.", SERIF, 20, "9DB8FF", italic=True)]], align=PP_ALIGN.CENTER)
    text(s, W - 5.2, H - 0.35, 5.0, 0.25, [[R("Photo: Stormy sunset over the Waimakariri River basin, New Zealand · Wikimedia Commons · CC BY-SA 4.0", SANS, 7, "B8BFCC")]], align=PP_ALIGN.RIGHT)
    text(s, MX, H - 0.48, 6, 0.25, [[R("Stunt Double  ·  Team Dragon  ·  Vultr: Agent Rush", MONO, 9, "B8BFCC")]])
    notes(s, "Agents should be bold. Businesses should be safe. Now they can be both. Try it live: judge mode is eight "
             "clicks. Let the double take the hit.")


def fade(slide) -> None:
    from lxml import etree
    t = etree.SubElement(slide._element, qn("p:transition"), spd="med")
    etree.SubElement(t, qn("p:fade"))


SLIDES = (s01_cover, s02_shift, s04_solution, s05_approve, s06_containment, s07_engine, s08_features,
          s09_proof, s10_vultr, s11_business, s12_vision, s14_close)


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
