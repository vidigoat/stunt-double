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



# ---- the simple deck: one idea per slide, big type, nothing small ----------------------------------------------
IMG = HERE / "img"
M = 1.0                                     # generous margins


def logo(slide, x, y, size, dark=False):
    slide.shapes.add_picture(str(IMG / ("logo-dark.png" if dark else "logo-light.png")), Inches(x), Inches(y), Inches(size), Inches(size))


def wordmark(slide, x, y, size=26, dark=False, center=False):
    """The landing page's mark: the two figures, then 'Stunt Double' with 'Double' in italics."""
    ink = "FAFAF8" if dark else INK
    icon = size / 72 * 1.45
    if center:
        tw = size / 72 * 6.1
        x = (W - icon - 0.14 - tw) / 2
    logo(slide, x, y, icon, dark=dark)
    text(slide, x + icon + 0.14, y - size / 72 * 0.12, 5, icon + 0.2, [[R("Stunt ", SERIF, size, ink), R("Double", SERIF, size, ink, italic=True)]], anchor=MSO_ANCHOR.MIDDLE)


def big_title(slide, parts, y=1.0, size=54, dark=False, align=PP_ALIGN.LEFT, x=M, w=None, h=2.2):
    ink, acc = ("FAFAF8", BLUE_ON_DARK) if dark else (INK, BLUE)
    paras = [[R(t, SERIF, size, acc if a else ink, italic=a) for t, a in line] for line in parts]
    text(slide, x, y, w or (W - 2 * x), h, paras, align=align, spacing=0.95)


def line(slide, t, y, size=22, color=MUTED, align=PP_ALIGN.LEFT, x=M, w=None, h=0.9):
    text(slide, x, y, w or (W - 2 * x), h, [[R(t, SANS, size, color)]], align=align, spacing=1.15)


def plain(slide, color=PAPER):
    s = slide
    bg(s, color)
    return s


def new(prs, color=PAPER):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg(s, color)
    return s


# 1 -----------------------------------------------------------------------------------------------------------------
def s_cover(prs):
    s = new(prs)
    wordmark(s, 0, 0.95, size=28, center=True)
    text(s, 0.5, 2.05, W - 1, 1.3, [[R("Let the double", SERIF, 92, INK)]], align=PP_ALIGN.CENTER)
    box(s, 2.95, 3.42, 7.43, 1.5, fill=BLUE, line=None, radius=0.12)
    text(s, 2.95, 3.4, 7.43, 1.45, [[R("take the hit.", SERIF, 92, "FFFFFF", italic=True)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    line(s, "Every AI agent action, rehearsed on a copy of your business first.", 5.55, size=22, align=PP_ALIGN.CENTER)
    notes(s, "In the movies, the star never jumps from the burning building. The stunt double does. Stunt Double gives "
             "every AI agent a double of your business to take the hit first. Built for Vultr: Agent Rush, Challenge 01.")


# 2 -----------------------------------------------------------------------------------------------------------------
def s_shift(prs):
    s = new(prs)
    big_title(s, [[("AI agents don't just answer now.", False)], [("They act.", True)]])
    column_chart(s, M - 0.1, 3.1, 5.4, 3.7, ["2024", "2028"], (0.6, 33), [BLUE_SOFT, BLUE], '0"%"', labels=["<1%", "33%"], maxv=40, label_size=26)
    text(s, 7.0, 3.55, W - 7.0 - M, 1.4, [[R("33%", MONO, 72, INK)]])
    line(s, "of enterprise software will have AI agents by 2028.", 4.85, size=22, x=7.0, w=W - 7.0 - M, h=1.2)
    line(s, "They refund, email, edit databases and delete servers.", 5.95, size=18, color=FAINT, x=7.0, w=W - 7.0 - M)
    notes(s, "AI agents are moving from answering to acting. Gartner expects a third of enterprise software to include "
             "agentic AI by 2028, up from under 1% in 2024, and agents to make at least 15% of day-to-day work decisions. "
             "Source: Gartner (Oct 2024).")


# 3 -----------------------------------------------------------------------------------------------------------------
def s_problem(prs):
    s = new(prs)
    big_title(s, [[("When they're wrong,", False)], [("it's real.", True)]])
    for i, (when, what) in enumerate([("July 2025", "An AI agent deleted a company's production database, during a code freeze."),
                                       ("2026", "Another deleted a database and its backups, in nine seconds.")]):
        y = 3.35 + i * 1.55
        text(s, M, y, 2.2, 0.6, [[R(when, SANS, 22, RED)]])
        text(s, M + 2.3, y - 0.05, W - 2 * M - 2.3, 1.3, [[R(what, SERIF, 30, INK)]], spacing=1.0)
    notes(s, "And when agents are wrong, it's real money, real inboxes, real data. In July 2025 an AI agent deleted a "
             "company's production database during a code freeze (eWeek). In spring 2026 another deleted a startup's "
             "database and its backups in nine seconds (Information Age, May 2026). Gartner expects over 40% of agentic AI "
             "projects to be cancelled by 2027, partly for inadequate risk controls.")


# 4 -----------------------------------------------------------------------------------------------------------------
def s_solution(prs):
    s = new(prs)
    big_title(s, [[("So every agent gets ", False), ("a double.", True)]], h=1.2)
    steps = [("1", "Rehearse", "on a copy of your business"), ("2", "Measure", "what really changed"), ("3", "Approve", "the consequences, not code")]
    cw = (W - 2 * M - 0.6) / 3
    for i, (n, t, d) in enumerate(steps):
        x = M + i * (cw + 0.3)
        oval(s, x, 2.75, 0.75, BLUE)
        text(s, x, 2.75, 0.75, 0.75, [[R(n, SERIF, 30, "FFFFFF")]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(s, x, 3.75, cw, 0.9, [[R(t, SERIF, 44, INK)]])
        line(s, d, 4.75, size=22, x=x, w=cw - 0.2)
    line(s, "Nothing real happens until a person says yes.", 6.15, size=22, color=INK)
    notes(s, "Stunt Double gives every agent a double. Each action is rehearsed first on a copy of the business, in a "
             "sealed gVisor sandbox on Vultr with no network and no secrets. A second sandbox, running only our code, "
             "measures what really changed. A person approves that, and only those measured effects are replayed for "
             "real, after a drift check. The agent's own code never runs against production.")


# 5 -----------------------------------------------------------------------------------------------------------------
def s_containment(prs):
    s = new(prs)
    big_title(s, [[("The blast radius is ", False), ("zero.", True)]], h=1.2)
    half = (W - 2 * M - 0.4) / 2
    box(s, M, 2.55, half, 3.6, fill=RED_SOFT, line=None, radius=0.25)
    text(s, M, 3.0, half, 2.0, [[R("0", MONO, 110, RED)]], align=PP_ALIGN.CENTER)
    line(s, "customers left on the double", 5.15, size=22, align=PP_ALIGN.CENTER, x=M, w=half)
    x = M + half + 0.4
    box(s, x, 2.55, half, 3.6, fill="FFFFFF", line=LINE, radius=0.25)
    text(s, x, 3.0, half, 2.0, [[R("1,300", MONO, 110, INK)]], align=PP_ALIGN.CENTER)
    line(s, "customers in production, untouched", 5.15, size=22, align=PP_ALIGN.CENTER, x=x, w=half)
    notes(s, "Here's a plan that deletes every customer. It ran for real, on the double: zero customers left. Production "
             "still has 1,300, and approval locks. Because our own code measures the result in a second sandbox, a plan "
             "that lies about what it did is caught too: one said 'no changes' and had changed 300 rows.")


# 6 -----------------------------------------------------------------------------------------------------------------
def s_engine(prs):
    s = new(prs, INK)
    big_title(s, [[("744 refunds planned. ", False), ("104 were right.", True)], [("It kept exactly those.", False)]], dark=True, size=50)
    cols, rows = 93, 8
    cell = (W - 2 * M) / cols
    for i in range(744):
        r, c = divmod(i, cols)
        box(s, M + c * cell, 3.2 + r * cell, cell * 0.8, cell * 0.8, fill=GREEN_ON_DARK if i in KEPT else "C2474B", line=None, radius=0)
    for i, (n, t, c) in enumerate([("$5,136", "kept: the right 104", GREEN_ON_DARK), ("$32,268", "cut: 640 people never double-charged", RED_ON_DARK)]):
        x = M + i * 5.6
        text(s, x, 4.6, 5.4, 1.2, [[R(n, MONO, 60, c)]])
        line(s, t, 5.7, size=22, color="C9C9C4", x=x, w=5.4)
    notes(s, "Now the hard case: a plan that's only partly wrong. Before the plan exists, the engine writes down what the "
             "request means: 104 refunds. The plan does 744. Replaying it proves line 1 chose the 640 wrong ones. The "
             "engine cuts them out, re-runs just the 104 in a fresh sandbox, and every check passes. Guardrails block or "
             "allow; this approves exactly the right part.")


# 7 -----------------------------------------------------------------------------------------------------------------
def s_features(prs):
    s = new(prs)
    big_title(s, [[("Everything a careful team needs.", False)]], h=1.2)
    items = ["Plain-English approval", "Two-person approval", "Rehearsed undo",
             "AI jury of three labs", "Every catch becomes a rule", "Signed evidence"]
    cw = (W - 2 * M - 0.6) / 3
    for k, t in enumerate(items):
        r, c = divmod(k, 3)
        x, y = M + c * (cw + 0.3), 2.6 + r * 1.95
        box(s, x, y, cw, 1.65, fill="FFFFFF", line=LINE, radius=0.22)
        oval(s, x + 0.4, y + 0.5, 0.2, BLUE)
        text(s, x + 0.4, y + 0.85, cw - 0.6, 0.7, [[R(t, SANS, 21, INK, bold=True)]])
    notes(s, "Everything a careful team needs. A person sees consequences in plain English. Big changes need two "
             "different people, and every undo is rehearsed too. An AI jury from three labs investigates the data with "
             "read-only SQL. Every catch can become a rule that blocks the same mistake without AI. Every decision is "
             "sealed in a signed record your browser can verify. It works on your Postgres, your Vultr fleet, any API and "
             "a real browser, and agents connect over MCP, an SDK, a CLI or REST, with no approve tool.")


# 8 -----------------------------------------------------------------------------------------------------------------
def s_proof(prs):
    s = new(prs)
    big_title(s, [[("Measured live, ", False), ("not on slides.", True)]], h=1.2)
    stats = [("12/12", "bad plans stopped"), ("8/8", "good plans approved"), ("8/8", "unseen wrong plans stopped"), ("63→41", "on a school it never saw")]
    cw = (W - 2 * M) / 4
    for i, (n, t) in enumerate(stats):
        x = M + i * cw
        text(s, x, 3.0, cw - 0.1, 1.3, [[R(n, MONO, 46, INK)]])
        line(s, t, 4.2, size=20, x=x, w=cw - 0.4)
    line(s, "Zero false alarms. 201 automated tests.", 6.0, size=22, color=INK)
    notes(s, "Measured live on Vultr: the engine stopped 12 of 12 bad plans and approved 8 of 8 good ones, with no false "
             "alarms. On 16 held-out cases written before the run, it stopped all 8 wrong plans (3 of 8 right plans were "
             "approved outright; the other 5 went to a person with a reason). On a school's database it had never seen, "
             "it found the 22 students who took their withdrawal back and kept exactly the right 41 of 63.")


# 9 -----------------------------------------------------------------------------------------------------------------
def s_vultr(prs):
    s = new(prs, INK)
    vultr_mark(s, M, 1.12, 0.55)
    big_title(s, [[("Built on ", False), ("Vultr.", True)]], dark=True, x=M + 0.8, y=0.95, h=1.0)
    cols = [("Cloud Compute", "Every rehearsal in two fresh gVisor sandboxes."), ("Serverless Inference", "Four labs' models write, check and judge."),
            ("Vultr API", "A safe double of your real server fleet.")]
    cw = (W - 2 * M - 0.6) / 3
    for i, (t, d) in enumerate(cols):
        x = M + i * (cw + 0.3)
        box(s, x, 2.7, cw, 0.06, fill=BLUE, line=None, radius=0)
        text(s, x, 3.0, cw, 0.7, [[R(t, SERIF, 28, "FAFAF8")]])
        line(s, d, 3.75, size=20, color="C9C9C4", x=x, w=cw - 0.2, h=1.2)
    text(s, M, 5.55, 3.5, 1.0, [[R("$8.64", MONO, 54, BLUE_ON_DARK)]])
    line(s, "the whole build, every test included", 5.85, size=22, color="C9C9C4", x=M + 3.3, w=6)
    notes(s, "All of it runs on Vultr. Cloud Compute runs the web app, the API, the MCP server and every rehearsal in two "
             "fresh gVisor sandboxes. Serverless Inference runs four labs' models: Qwen writes the intent contract, DeepSeek "
             "cross-checks it, and GLM, DeepSeek and MiniMax judge the outcome. The Vultr API gives a read-only double of "
             "your real fleet. The whole build, every test run included, cost $8.64 (Vultr billing API).")


# 10 ----------------------------------------------------------------------------------------------------------------
def s_business(prs):
    s = new(prs)
    big_title(s, [[("One caught mistake pays for", False)], [("a seat for ", False), ("55 years.", True)]])
    for i, (n, t, c) in enumerate([("$32,268", "one mistake, caught", RED), ("$49", "a seat, per month", INK), ("73%", "gross margin", INK)]):
        x = M + i * 3.95
        text(s, x, 3.6, 3.8, 1.2, [[R(n, MONO, 50, c)]])
        line(s, t, 4.75, size=22, x=x, w=3.6)
    line(s, "For the teams who sign off on what AI agents do.", 6.0, size=22, color=INK)
    notes(s, "One caught mistake in the demo is $32,268; a seat is $49 a month, so that single catch pays for it for 55 "
             "years. A rehearsal costs us $0.00003 and a three-model AI check $0.02 to $0.044, so a full seat runs at a "
             "73% gross margin. Buyers: Heads of Operations, Support and Finance Ops. The EU AI Act (Art. 14 and 12) and "
             "SOC 2 (CC8.1) already ask for exactly this approval record. The AI agents market grows from $7.8B (2025) to "
             "$52.6B (2030) (MarketsandMarkets). Open core, MIT.")


# 11 ----------------------------------------------------------------------------------------------------------------
def s_close(prs):
    s = new(prs, INK)
    s.shapes.add_picture(str(IMG / "close-16x9.jpg"), 0, 0, Inches(W), Inches(H))
    veil(s, 0, 0, W, H, "05070D", 0.45)
    wordmark(s, 0, 1.0, size=28, dark=True, center=True)
    text(s, 0.5, 2.15, W - 1, 2.4, [[R("Agents should be bold.", SERIF, 64, "FFFFFF")],
                                    [R("Businesses should be ", SERIF, 64, "FFFFFF"), R("safe.", SERIF, 64, "9DB8FF", italic=True)]], align=PP_ALIGN.CENTER, spacing=0.95)
    line(s, "Try it live: 149-28-206-186.sslip.io", 5.3, size=24, color="FFFFFF", align=PP_ALIGN.CENTER)
    notes(s, "Agents should be bold. Businesses should be safe. Now they can be both. Try it live: judge mode is eight "
             "clicks. Let the double take the hit. Code: github.com/vidigoat/stunt-double. "
             "Photo: 'Stormy sunset over the Waimakariri River basin, New Zealand', Wikimedia Commons, CC BY-SA 4.0.")


def fade(slide) -> None:
    from lxml import etree
    t = etree.SubElement(slide._element, qn("p:transition"), spd="med")
    etree.SubElement(t, qn("p:fade"))


SLIDES = (s_cover, s_shift, s_problem, s_solution, s_containment, s_engine, s_features, s_proof, s_vultr, s_business, s_close)


def build() -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    for f in SLIDES:
        f(prs)
    for sl in list(prs.slides)[1:]:
        fade(sl)
    prs.core_properties.title = "Stunt Double"
    prs.core_properties.subject = "Let the double take the hit. Vultr: Agent Rush, Challenge 01."
    prs.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
