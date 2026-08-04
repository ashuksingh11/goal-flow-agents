#!/usr/bin/env python3
"""Build the "One goal, eight engines" slide.

Single source of truth: COPY (locked text) + build_scene() (geometry in CSS px,
1 inch = 100 px). Two renderers consume the same scene list:

  render_pptx()          -> harness-flow.pptx   (13.333 x 7.5 in, real shapes)
  render_html_preview()  -> preview.html        (1333 x 750 px, same coords)

Running `python3 build_harness_slide.py` produces both.
"""

import math
import os

BASE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- palette ----
BG          = '#ECEFF4'   # slide background
CARD        = '#FFFFFF'   # card fill
INK         = '#1A1E2C'   # primary ink
INK2        = '#5C6377'   # secondary ink
INK3        = '#6E7690'   # quiet ink
ACCENT      = '#3F6FE8'   # gates, connectors, numbers
ACCENT_TINT = '#E9EFFC'   # gate fill
GREEN       = '#12A150'   # "what it did" mark
GREEN_TINT  = '#E7F7EE'
HAIR        = '#E2E6F0'   # hairline (dividers inside white cards only)
BORDER      = '#868FA6'   # visible container border, used sparingly

# ------------------------------------------------------------- type scale ----
PT_TITLE = 30.0
PT_NAME  = 13.0
PT_BODY  = 11.0
PT_SMALL = 10.5

FONT_PPTX = 'Segoe UI'
FONT_CSS  = '"Segoe UI", system-ui, -apple-system, sans-serif'

# ------------------------------------------------------------------- copy ----
TITLE    = 'One goal, eight engines'
SUBTITLE = '"Plan my weekly meal." — what the Family Hub does with a sentence'
QUOTE    = '"Plan my weekly meal."'

GATE_CONFIRM = ('Confirm', 'The family checks it heard right')
GATE_APPROVE = ('Approve', 'The plan goes to the board')

ENGINES = [
    (1, 'Pre-Check Engine',     'Is the kitchen ready to be asked?',
        'The fridge was online and signed in, so it went ahead.'),
    (2, 'Capability Manager',   'What is this fridge allowed to do?',
        "It could read the fridge, the calendar, the recipe book and the family's activity."),
    (3, 'Task Manager',         'Turn one sentence into a to-do list.',
        'Broke the week into smaller jobs and kept track of them.'),
    (4, 'Grounding',            'Go and look at the real world.',
        'Spinach, yoghurt, bread and chicken were about to go off.'),
    (5, 'Planner',              'Decide what to actually cook.',
        'Seven dinners, each with the reason it is there.'),
    (6, 'Safety Policy Engine', 'Check nothing breaks a house rule.',
        'The peanut allergy, no pork and low salt all held.'),
    (7, 'Approval',             'Nothing real happens without a person.',
        'The shopping list changes waited for a yes.'),
]
ENGINE8 = (8, 'Monitor & Adapt', 'Keep watching after the plan is made.',
           'Fish arrived, so it changed the next dinner.', 'Later, when a day passes')

# --------------------------------------------------------------- geometry ----
W, H   = 1333.0, 750.0
MARG   = 48.0
CARD_W = 288.0
CARD_H = 186.0
GAP    = (W - 2 * MARG - 4 * CARD_W) / 3.0          # ~28.3
XS     = [MARG + i * (CARD_W + GAP) for i in range(4)]

ROWA_Y, ROWA_H = 122.0, 56.0
ROWB_Y = 224.0
ROWC_Y = 448.0
E8_Y, E8_H = 664.0, 64.0

# ------------------------------------------------------- scene primitives ----

def run(t, size, color, bold=False, italic=False, spc=None):
    return dict(t=t, size=size, color=color, bold=bold, italic=italic, spc=spc)

def para(runs, align='left', leading=1.12):
    return dict(runs=runs, align=align, leading=leading)


def arrow_h(x_tail, x_tip, cy, shaft=4.0, head_l=11.0, head_w=14.0):
    d = 1.0 if x_tip > x_tail else -1.0
    xb = x_tip - d * head_l
    s, hw = shaft / 2.0, head_w / 2.0
    return [(x_tail, cy - s), (xb, cy - s), (xb, cy - hw), (x_tip, cy),
            (xb, cy + hw), (xb, cy + s), (x_tail, cy + s)]


def arrow_v(y_tail, y_tip, cx, shaft=4.0, head_l=11.0, head_w=14.0):
    d = 1.0 if y_tip > y_tail else -1.0
    yb = y_tip - d * head_l
    s, hw = shaft / 2.0, head_w / 2.0
    return [(cx - s, y_tail), (cx - s, yb), (cx - hw, yb), (cx, y_tip),
            (cx + hw, yb), (cx + s, yb), (cx + s, y_tail)]


def semicircle(cx, cy, r, steps=16):
    """Flat-bottomed semicircle (person shoulders)."""
    pts = []
    for i in range(steps + 1):
        a = math.pi * (1.0 - i / steps)
        pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
    return pts


def build_scene():
    S = []

    def rect(x, y, w, h, fill=None, line=None, lw=1.0, radius=0.0, dash=False):
        S.append(dict(kind='rect', x=x, y=y, w=w, h=h, fill=fill, line=line,
                      lw=lw, radius=radius, dash=dash))

    def ellipse(x, y, w, h, fill=None, line=None, lw=1.0):
        S.append(dict(kind='ellipse', x=x, y=y, w=w, h=h, fill=fill,
                      line=line, lw=lw))

    def poly(pts, fill):
        S.append(dict(kind='poly', pts=pts, fill=fill))

    def seg(x1, y1, x2, y2, color, lw=2.0, dash=False):
        S.append(dict(kind='line', x1=x1, y1=y1, x2=x2, y2=y2, color=color,
                      lw=lw, dash=dash))

    def text(x, y, w, h, paras, valign='top'):
        S.append(dict(kind='text', x=x, y=y, w=w, h=h, paras=paras,
                      valign=valign))

    def person(cx, cy):
        """Small human glyph: head + shoulders, accent."""
        ellipse(cx - 5.5, cy - 14.0, 11.0, 11.0, fill=ACCENT)
        poly(semicircle(cx, cy + 11.0, 10.0), ACCENT)

    def gate(x, y, w, h, name, line_txt):
        rect(x, y, w, h, fill=ACCENT_TINT, line=ACCENT, lw=1.5, radius=h / 2.0)
        person(x + 34.0, y + h / 2.0)
        text(x + 56.0, y, w - 72.0, h,
             [para([run(name, PT_NAME, INK, bold=True)]),
              para([run(line_txt, PT_SMALL, INK2)])], valign='middle')

    def engine_card(x, y, num, name, purpose, did):
        rect(x, y, CARD_W, CARD_H, fill=CARD, radius=10.0)
        ellipse(x + 18, y + 17, 28, 28, fill=ACCENT)
        text(x + 18, y + 17, 28, 28,
             [para([run(str(num), PT_BODY, '#FFFFFF', bold=True)], align='center')],
             valign='middle')
        text(x + 58, y + 15, CARD_W - 72, 32,
             [para([run(name, PT_NAME, INK, bold=True)])], valign='middle')
        text(x + 18, y + 54, CARD_W - 36, 40,
             [para([run(purpose, PT_BODY, INK2)], leading=1.15)])
        seg(x + 18, y + 97, x + CARD_W - 18, y + 97, HAIR, lw=1.0)
        rect(x + 18, y + 106, CARD_W - 36, 66, fill=GREEN_TINT, radius=8.0)
        text(x + 28, y + 114, 16, 18,
             [para([run('✓', PT_SMALL, GREEN, bold=True)])])
        text(x + 46, y + 114, CARD_W - 74, 54,
             [para([run(did, PT_SMALL, INK)], leading=1.18)])

    # background
    rect(0, 0, W, H, fill=BG)

    # title block
    text(MARG, 26, 900, 48,
         [para([run(TITLE, PT_TITLE, INK, bold=True, spc=-30)])])
    text(MARG, 80, 1100, 26, [para([run(SUBTITLE, PT_NAME, INK2)])])

    # --- row A: spoken goal -> Confirm gate --------------------------------
    entry_w = 250.0
    rect(MARG, ROWA_Y, entry_w, ROWA_H, fill=CARD, line=BORDER, lw=1.2,
         radius=ROWA_H / 2.0)
    text(MARG + 16, ROWA_Y, entry_w - 32, ROWA_H,
         [para([run(QUOTE, PT_NAME, INK, italic=True)], align='center')],
         valign='middle')

    ax0 = MARG + entry_w + 10          # arrow entry -> gate
    gate_x = MARG + entry_w + 60       # 358
    poly(arrow_h(ax0, gate_x - 10, ROWA_Y + ROWA_H / 2.0), ACCENT)
    gate_w = 330.0
    gate(gate_x, ROWA_Y, gate_w, ROWA_H, *GATE_CONFIRM)

    # elbow: Confirm gate -> engine 1
    gcx = gate_x + gate_w / 2.0
    e1cx = XS[0] + CARD_W / 2.0
    my = (ROWA_Y + ROWA_H + ROWB_Y) / 2.0
    seg(gcx, ROWA_Y + ROWA_H + 1, gcx, my, ACCENT, lw=2.2)
    seg(gcx + 1.1, my, e1cx, my, ACCENT, lw=2.2)
    poly(arrow_v(my - 1, ROWB_Y - 3, e1cx), ACCENT)

    # --- row B: engines 1-4, left to right ---------------------------------
    cyB = ROWB_Y + CARD_H / 2.0
    for i in range(4):
        engine_card(XS[i], ROWB_Y, *ENGINES[i])
        if i < 3:
            gx = XS[i] + CARD_W
            poly(arrow_h(gx + 4, gx + GAP - 4, cyB), ACCENT)

    # down connector: engine 4 -> engine 5
    dcx = XS[3] + CARD_W / 2.0
    poly(arrow_v(ROWB_Y + CARD_H + 3, ROWC_Y - 3, dcx), ACCENT)

    # --- row C: engines 5-7 right to left, then Approve gate ---------------
    cyC = ROWC_Y + CARD_H / 2.0
    for j, col in enumerate([3, 2, 1]):        # engines 5, 6, 7
        engine_card(XS[col], ROWC_Y, *ENGINES[4 + j])
        gx = XS[col]                            # leftward arrow into next slot
        poly(arrow_h(gx - 4, gx - GAP + 4, cyC), ACCENT)

    ag_h = 90.0
    ag_y = ROWC_Y + (CARD_H - ag_h) / 2.0
    gate(XS[0], ag_y, CARD_W, ag_h, *GATE_APPROVE)

    # --- dashed loop: board <-> Monitor & Adapt ----------------------------
    ag_bot = ag_y + ag_h
    xd, xu = XS[0] + 92.0, XS[0] + 196.0
    seg(xd, ag_bot + 3, xd, E8_Y - 12, ACCENT, lw=2.0, dash=True)
    poly(arrow_v(E8_Y - 12, E8_Y - 2, xd), ACCENT)
    seg(xu, E8_Y - 3, xu, ag_bot + 12, ACCENT, lw=2.0, dash=True)
    poly(arrow_v(ag_bot + 12, ag_bot + 2, xu), ACCENT)

    # --- engine 8: detached "later" band -----------------------------------
    n8, name8, purpose8, did8, badge8 = ENGINE8
    e8_w = W - 2 * MARG
    x8, y8 = MARG, E8_Y
    rect(x8, y8, e8_w, E8_H, fill=CARD, line=BORDER, lw=1.1, radius=10.0)
    ellipse(x8 + 18, y8 + 19, 26, 26, fill=ACCENT)
    text(x8 + 18, y8 + 19, 26, 26,
         [para([run(str(n8), PT_BODY, '#FFFFFF', bold=True)], align='center')],
         valign='middle')
    text(x8 + 54, y8, 200, E8_H,
         [para([run(name8, PT_NAME, INK, bold=True)])], valign='middle')
    rect(x8 + 264, y8 + 18, 205, 28, fill=HAIR, radius=14.0)
    text(x8 + 264, y8 + 18, 205, 28,
         [para([run(badge8, PT_SMALL, INK2)], align='center')], valign='middle')
    text(x8 + 500, y8, 320, E8_H,
         [para([run(purpose8, PT_BODY, INK2)])], valign='middle')
    seg(x8 + 838, y8 + 12, x8 + 838, y8 + E8_H - 12, HAIR, lw=1.0)
    chip_x = x8 + 852
    rect(chip_x, y8 + 12, x8 + e8_w - 14 - chip_x, E8_H - 24,
         fill=GREEN_TINT, radius=8.0)
    text(chip_x + 12, y8, 16, E8_H,
         [para([run('✓', PT_SMALL, GREEN, bold=True)])], valign='middle')
    text(chip_x + 30, y8, x8 + e8_w - 26 - chip_x - 30, E8_H,
         [para([run(did8, PT_SMALL, INK)])], valign='middle')

    return S


# ---------------------------------------------------------- pptx renderer ----

def render_pptx(scene, path):
    from pptx import Presentation
    from pptx.util import Emu, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.enum.dml import MSO_LINE_DASH_STYLE as MSO_LINE

    def E(px):
        return Emu(int(round(px * 9144)))          # 1 px = 1/100 in = 9144 EMU

    def C(hexstr):
        return RGBColor.from_string(hexstr.lstrip('#'))

    prs = Presentation()
    prs.slide_width = E(W)
    prs.slide_height = E(H)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    shapes = slide.shapes

    def style_shape(shp, fill, line, lw, dash=False):
        if fill:
            shp.fill.solid()
            shp.fill.fore_color.rgb = C(fill)
        else:
            shp.fill.background()
        if line:
            shp.line.color.rgb = C(line)
            shp.line.width = Pt(lw)
            if dash:
                shp.line.dash_style = MSO_LINE.DASH
        else:
            shp.line.fill.background()
        try:
            shp.shadow.inherit = False
        except Exception:
            pass

    for el in scene:
        k = el['kind']
        if k == 'rect':
            if el['radius'] > 0:
                shp = shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                       E(el['x']), E(el['y']), E(el['w']), E(el['h']))
                shp.adjustments[0] = min(0.5, el['radius'] / min(el['w'], el['h']))
            else:
                shp = shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                       E(el['x']), E(el['y']), E(el['w']), E(el['h']))
            style_shape(shp, el['fill'], el['line'], el['lw'], el['dash'])
        elif k == 'ellipse':
            shp = shapes.add_shape(MSO_SHAPE.OVAL,
                                   E(el['x']), E(el['y']), E(el['w']), E(el['h']))
            style_shape(shp, el['fill'], el['line'], el['lw'])
        elif k == 'poly':
            pts = el['pts']
            fb = shapes.build_freeform(E(pts[0][0]), E(pts[0][1]), scale=1.0)
            fb.add_line_segments([(E(x), E(y)) for x, y in pts[1:]], close=True)
            shp = fb.convert_to_shape()
            style_shape(shp, el['fill'], None, 0)
        elif k == 'line':
            conn = shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                        E(el['x1']), E(el['y1']),
                                        E(el['x2']), E(el['y2']))
            conn.line.color.rgb = C(el['color'])
            conn.line.width = Pt(el['lw'])
            if el['dash']:
                conn.line.dash_style = MSO_LINE.DASH
            try:
                conn.shadow.inherit = False
            except Exception:
                pass
        elif k == 'text':
            tb = shapes.add_textbox(E(el['x']), E(el['y']), E(el['w']), E(el['h']))
            tf = tb.text_frame
            tf.word_wrap = True
            tf.margin_left = tf.margin_right = 0
            tf.margin_top = tf.margin_bottom = 0
            tf.vertical_anchor = (MSO_ANCHOR.MIDDLE if el['valign'] == 'middle'
                                  else MSO_ANCHOR.TOP)
            for i, p in enumerate(el['paras']):
                pp = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                pp.alignment = {'left': PP_ALIGN.LEFT, 'center': PP_ALIGN.CENTER,
                                'right': PP_ALIGN.RIGHT}[p['align']]
                pp.line_spacing = p['leading']
                for r in p['runs']:
                    rr = pp.add_run()
                    rr.text = r['t']
                    f = rr.font
                    f.name = FONT_PPTX
                    f.size = Pt(r['size'])
                    f.bold = r['bold']
                    f.italic = r['italic']
                    f.color.rgb = C(r['color'])
                    if r['spc'] is not None:
                        rr._r.get_or_add_rPr().set('spc', str(int(r['spc'])))

    prs.save(path)


# ---------------------------------------------------------- html renderer ----

def render_html_preview(scene, path):
    PX = 100.0 / 72.0                              # 1 pt = 1.389 px

    def css_border(el):
        if not el['line']:
            return ''
        style = 'dashed' if el['dash'] else 'solid'
        return f"border:{el['lw'] * PX:.2f}px {style} {el['line']};"

    out = []
    for el in scene:
        k = el['kind']
        if k == 'rect':
            out.append(
                f"<div style=\"position:absolute;left:{el['x']:.1f}px;top:{el['y']:.1f}px;"
                f"width:{el['w']:.1f}px;height:{el['h']:.1f}px;box-sizing:border-box;"
                f"background:{el['fill'] or 'transparent'};"
                f"border-radius:{el['radius']:.1f}px;{css_border(el)}\"></div>")
        elif k == 'ellipse':
            out.append(
                f"<div style=\"position:absolute;left:{el['x']:.1f}px;top:{el['y']:.1f}px;"
                f"width:{el['w']:.1f}px;height:{el['h']:.1f}px;box-sizing:border-box;"
                f"background:{el['fill'] or 'transparent'};border-radius:50%;"
                f"{css_border(dict(el, dash=False))}\"></div>")
        elif k == 'poly':
            pts = ' '.join(f"{x:.1f},{y:.1f}" for x, y in el['pts'])
            out.append(
                f"<svg style=\"position:absolute;left:0;top:0;pointer-events:none\" "
                f"width=\"{W:.0f}\" height=\"{H:.0f}\">"
                f"<polygon points=\"{pts}\" fill=\"{el['fill']}\"/></svg>")
        elif k == 'line':
            dash = ' stroke-dasharray="6 5"' if el['dash'] else ''
            out.append(
                f"<svg style=\"position:absolute;left:0;top:0;pointer-events:none\" "
                f"width=\"{W:.0f}\" height=\"{H:.0f}\">"
                f"<line x1=\"{el['x1']:.1f}\" y1=\"{el['y1']:.1f}\" "
                f"x2=\"{el['x2']:.1f}\" y2=\"{el['y2']:.1f}\" "
                f"stroke=\"{el['color']}\" stroke-width=\"{el['lw'] * PX:.2f}\"{dash}/>"
                f"</svg>")
        elif k == 'text':
            just = 'center' if el['valign'] == 'middle' else 'flex-start'
            paras_html = []
            for p in el['paras']:
                spans = []
                for r in p['runs']:
                    st = (f"font-size:{r['size'] * PX:.2f}px;color:{r['color']};"
                          f"font-weight:{700 if r['bold'] else 400};"
                          f"font-style:{'italic' if r['italic'] else 'normal'};")
                    if r['spc'] is not None:
                        st += f"letter-spacing:{r['spc'] / 100.0 * PX:.2f}px;"
                    spans.append(f"<span style=\"{st}\">{r['t']}</span>")
                paras_html.append(
                    f"<div style=\"text-align:{p['align']};"
                    f"line-height:{p['leading']:.2f}\">{''.join(spans)}</div>")
            out.append(
                f"<div style=\"position:absolute;left:{el['x']:.1f}px;top:{el['y']:.1f}px;"
                f"width:{el['w']:.1f}px;height:{el['h']:.1f}px;display:flex;"
                f"flex-direction:column;justify-content:{just};\">"
                f"{''.join(paras_html)}</div>")

    html = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<title>harness slide preview</title><style>"
        f"html,body{{margin:0;padding:0}}body{{font-family:{FONT_CSS};}}"
        "</style></head><body>"
        f"<div style=\"position:relative;width:{W:.0f}px;height:{H:.0f}px;"
        f"overflow:hidden\">{''.join(out)}</div>"
        "</body></html>")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    scene = build_scene()
    render_pptx(scene, os.path.join(BASE, 'harness-flow.pptx'))
    render_html_preview(scene, os.path.join(BASE, 'preview.html'))
    print('wrote harness-flow.pptx and preview.html')


if __name__ == '__main__':
    main()
