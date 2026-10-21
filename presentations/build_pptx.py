# -*- coding: utf-8 -*-
"""To'rt fasl — kreativ animatsion PowerPoint prezentatsiya generatori."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from lxml import etree

W, H = Inches(13.333), Inches(7.5)
prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]

NAVY = RGBColor(0x0B, 0x10, 0x26)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SOFT = RGBColor(0xE8, 0xF0, 0xFF)
SPRING = RGBColor(0x5F, 0xD0, 0x6E)
SUMMER = RGBColor(0xFF, 0xC9, 0x3C)
AUTUMN = RGBColor(0xFF, 0x8C, 0x42)
WINTER = RGBColor(0x4C, 0xC9, 0xF0)

ANIMS = {}   # slide index -> [(spid, kind, dur_ms, delay_ms)]
TRANS = {}   # slide index -> (p14 xml body, dur_ms)


def new_slide():
    return prs.slides.add_slide(BLANK)


def set_alpha(shape, pct):
    """shape fill rangiga shaffoflik qo'shish (0..100)."""
    clr = shape._element.spPr.find(qn('a:solidFill')).find(qn('a:srgbClr'))
    a = etree.SubElement(clr, qn('a:alpha'))
    a.set('val', str(int(pct * 1000)))


def no_line(shape):
    shape.line.fill.background()
    shape.shadow.inherit = False


def bg_image(s, path):
    s.shapes.add_picture(path, 0, 0, width=W, height=H)


def overlay(s, pct=38, color=RGBColor(0x07, 0x0B, 0x16)):
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
    r.fill.solid(); r.fill.fore_color.rgb = color
    no_line(r); set_alpha(r, pct)
    return r


def txt(s, l, t, w, h, text, size, color=WHITE, bold=False, align=PP_ALIGN.LEFT,
        italic=False, font='Segoe UI'):
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic
    r.font.color.rgb = color; r.font.name = font
    return tb


def card(s, l, t, w, h, fill, alpha, lines, align=PP_ALIGN.LEFT, radius=True):
    """lines: [(text, size, bold, color), ...]"""
    shp = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(l), Inches(t), Inches(w), Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    no_line(shp)
    if alpha is not None:
        set_alpha(shp, alpha)
    tf = shp.text_frame; tf.word_wrap = True
    tf.margin_left = Inches(0.25); tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.15); tf.margin_bottom = Inches(0.15)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, (text, size, bold, color) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(6)
        r = p.add_run(); r.text = text
        r.font.size = Pt(size); r.font.bold = bold
        r.font.color.rgb = color; r.font.name = 'Segoe UI'
    return shp


def anim(s, shape, kind, dur=600, delay=0):
    ANIMS.setdefault(id(s), []).append((shape.shape_id, kind, dur, delay))


# ---------------------------------------------------------------- SLIDE 1
s = new_slide()
bg_image(s, 'assets_seasons/title.png')
overlay(s, 42)
t1 = txt(s, 0.8, 1.5, 11.7, 1.6, "TO'RT FASL", 76, WHITE, True, PP_ALIGN.CENTER)
t2 = txt(s, 1.5, 3.15, 10.3, 0.9,
         "Yil fasllari — tabiatning eng go'zal davriy afsonasi", 26, SOFT,
         False, PP_ALIGN.CENTER, italic=True)
chips = []
names = [("BAHOR", SPRING), ("YOZ", SUMMER), ("KUZ", AUTUMN), ("QISH", WINTER)]
x = 2.42
for name, col in names:
    c = card(s, x, 4.6, 2.0, 0.75, col, None, [(name, 20, True, NAVY)], PP_ALIGN.CENTER)
    chips.append(c); x += 2.18
t3 = txt(s, 1.5, 5.9, 10.3, 0.6, "Zamonaviy animatsion slayd-shou  ·  2026",
         15, SOFT, False, PP_ALIGN.CENTER)
anim(s, t1, 'grow', 800, 0)
anim(s, t2, 'fade', 700, 200)
for c in chips:
    anim(s, c, 'wipe', 500, 150)
anim(s, t3, 'fade', 600, 100)
TRANS[id(s)] = ('<p14:prism/>', 1800)

# ---------------------------------------------------------------- SLIDE 2
s = new_slide()
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; no_line(bg)
h = txt(s, 0.7, 0.45, 12, 0.9, "Bir yil — to'rt fasl davriy", 40, WHITE, True,
        PP_ALIGN.CENTER)
ring = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(4.17), Inches(1.5), Inches(5), Inches(5))
ring.fill.background(); no_line(ring)
ring.line.color.rgb = RGBColor(0x3A, 0x4A, 0x6B); ring.line.width = Pt(1.5)
center = card(s, 5.42, 2.75, 2.5, 2.5, RGBColor(0x14, 0x1C, 0x3A), None,
              [("365 kun", 22, True, WHITE), ("4 fasl", 22, True, SOFT),
               ("12 oy", 22, True, SOFT)], PP_ALIGN.CENTER)
pos = [(5.67, 1.35, "BAHOR", "Mart–May", SPRING),
       (8.35, 3.35, "YOZ", "Iyun–Avg", SUMMER),
       (5.67, 5.35, "KUZ", "Sent–Noy", AUTUMN),
       (2.99, 3.35, "QISH", "Dek–Fev", WINTER)]
circ = []
for cx, cy, nm, mo, col in pos:
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx), Inches(cy), Inches(2), Inches(2))
    c.fill.solid(); c.fill.fore_color.rgb = col; no_line(c)
    tf = c.text_frame; tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = nm; r.font.size = Pt(20); r.font.bold = True
    r.font.color.rgb = NAVY; r.font.name = 'Segoe UI'
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = mo; r2.font.size = Pt(13); r2.font.bold = True
    r2.font.color.rgb = NAVY; r2.font.name = 'Segoe UI'
    circ.append(c)
anim(s, h, 'fade', 700, 0)
anim(s, center, 'grow', 700, 100)
for c in circ:
    anim(s, c, 'grow', 600, 180)
TRANS[id(s)] = ('<p14:honeycomb/>', 1600)


# ------------------------------------------------- season slide builder
def season_slide(img, side, title, tag, bullets, stats, trans, dur=1700):
    s = new_slide()
    bg_image(s, img)
    overlay(s, 30)
    left = side == 'L'
    cx = 0.65 if left else 7.05
    panel = card(s, cx, 0.85, 5.65, 5.8, RGBColor(0x0A, 0x0F, 0x1E), 62, [])
    tf = panel.text_frame
    tf.margin_left = Inches(0.4); tf.margin_top = Inches(0.35)
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = title
    r.font.size = Pt(40); r.font.bold = True; r.font.color.rgb = WHITE
    r.font.name = 'Segoe UI'
    p = tf.add_paragraph()
    r = p.add_run(); r.text = tag
    r.font.size = Pt(18); r.font.italic = True; r.font.color.rgb = SOFT
    r.font.name = 'Segoe UI'
    p = tf.add_paragraph(); p.space_before = Pt(14)
    for b in bullets:
        p = tf.add_paragraph(); p.space_after = Pt(10)
        r = p.add_run(); r.text = "•  " + b
        r.font.size = Pt(17); r.font.color.rgb = WHITE; r.font.name = 'Segoe UI'
    sx = 7.05 if left else 0.65
    stat_shapes = []
    y = 1.15
    for icon, line in stats:
        st = card(s, sx, y, 5.65, 1.35, RGBColor(0x0A, 0x0F, 0x1E), 55,
                  [(icon, 26, True, WHITE), (line, 15, False, SOFT)])
        stat_shapes.append(st)
        y += 1.72
    anim(s, panel, 'wipe', 800, 0)
    for st in stat_shapes:
        anim(s, st, 'grow', 600, 220)
    TRANS[id(s)] = (trans, dur)
    return s


season_slide('assets_seasons/spring.png', 'L', "BAHOR 🌸", "Uyg'onish fasli",
             ["Oylar: Mart, Aprel, May",
              "Kun uzayadi, tun qisqaradi",
              "Daraxtlar gullab, qushlar qaytadi",
              "Tabiat qishki uyqudan uyg'onadi"],
             [("📅  Mart – May", "Yilning birinchi fasli"),
              ("🌡  +10…+20°C", "Mo''tadil iliq harorat"),
              ("🌸  Gullash mavsumi", "Olma, o'rik, gilos gullaydi")],
             '<p14:glitter dir="l"/>')

season_slide('assets_seasons/summer.png', 'R', "YOZ ☀️", "Quyosh fasli",
             ["Oylar: Iyun, Iyul, Avgust",
              "21-iyun — eng uzun kun (quyosh turishi)",
              "Tabiat jo'shqin: hosil boshlanadi",
              "Ta'til, sayil va sayohat mavsumi"],
             [("📅  Iyun – Avgust", "Yilning eng issiq fasli"),
              ("🌡  +25…+40°C", "Quyosh nurlari tik tushadi"),
              ("🌻  Eng uzun kun", "21-iyun, kunduz ~15 soat")],
             '<p14:vortex dir="l"/>')

season_slide('assets_seasons/autumn.png', 'L', "KUZ 🍂", "Hosil fasli",
             ["Oylar: Sentabr, Oktabr, Noyabr",
              "23-sentabr — kuzgi tengkunlik",
              "Barglar sarg'ayib, to'kiladi",
              "Hosil yig'ish va shukrona mavsumi"],
             [("📅  Sentabr – Noyabr", "Yilning uchinchi fasli"),
              ("🌡  +5…+15°C", "Salqin va sokin havo"),
              ("🌾  Hosil bayrami", "Bog' va dalalar barakasi")],
             '<p14:shred dir="l"/>')

season_slide('assets_seasons/winter.png', 'R', "QISH ❄️", "Sukunat fasli",
             ["Oylar: Dekabr, Yanvar, Fevral",
              "21-dekabr — eng qisqa kun",
              "Qor yog'ib, daryolar muzlaydi",
              "Qishki sport va bayramlar mavsumi"],
             [("📅  Dekabr – Fevral", "Yilning so'nggi fasli"),
              ("🌡  −5…−20°C", "Sovuq va tiniq havo"),
              ("⛷  Qishki sport", "Chang'i, konki, qorbobo")],
             '<p14:flip dir="l"/>')

# ---------------------------------------------------------------- SLIDE 7
s = new_slide()
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; no_line(bg)
h = txt(s, 0.7, 0.4, 12, 0.9, "Fasllar solishtirmasi", 40, WHITE, True,
        PP_ALIGN.CENTER)
cols = [("BAHOR", SPRING, ["Mart–May", "+10…20°C", "kun uzayadi", "gullash"]),
        ("YOZ", SUMMER, ["Iyun–Avg", "+25…40°C", "eng uzun kun", "jo'shqinlik"]),
        ("KUZ", AUTUMN, ["Sent–Noy", "+5…15°C", "kun qisqaradi", "hosil"]),
        ("QISH", WINTER, ["Dek–Fev", "−5…−20°C", "eng qisqa kun", "sukunat"])]
x = 0.62
col_shapes = []
for nm, col, rows in cols:
    lines = [(nm, 24, True, NAVY)] + [(r, 16, False, WHITE) for r in rows]
    c = card(s, x, 1.6, 2.92, 4.9, RGBColor(0x15, 0x1E, 0x3D), None, lines,
             PP_ALIGN.CENTER)
    # sarlavha rangi: birinchi qator rangi uchun alohida kichik header
    hd = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x + 0.35),
                            Inches(1.35), Inches(2.22), Inches(0.7))
    hd.fill.solid(); hd.fill.fore_color.rgb = col; no_line(hd)
    tf = hd.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = nm; r.font.size = Pt(20); r.font.bold = True
    r.font.color.rgb = NAVY; r.font.name = 'Segoe UI'
    col_shapes.append(c); col_shapes.append(hd)
    x += 3.06
anim(s, h, 'fade', 600, 0)
for c in col_shapes:
    anim(s, c, 'grow', 550, 140)
TRANS[id(s)] = ('<p14:pan dir="l"/>', 1500)

# ---------------------------------------------------------------- SLIDE 8
s = new_slide()
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
bg.fill.solid(); bg.fill.fore_color.rgb = NAVY; no_line(bg)
h = txt(s, 0.7, 0.4, 12, 0.9, "Qiziqarli faktlar 🌍", 40, WHITE, True,
        PP_ALIGN.CENTER)
facts = [("🌍  Sabab", "Yer o'qi 23,5° ga og'ganligi sababli fasllar almashadi — "
                      "Yorug'lik burchagi yil davomida o'zgaradi."),
         ("🔄  Teskari fasllar", "Janubiy yarimsharda fasllar teskari: bizda qish "
                                "bo'lsa, Avstraliyada yoz bo'ladi."),
         ("🌴  Ekvator", "Ekvator atrofida fasl deyarli sezilmaydi — faqat yomg'irli "
                         "va quruq mavsum ajratiladi."),
         ("🌡  Rekordlar", "Eng sovuq: −89,2°C (Antarktida). Eng issiq: +56,7°C "
                           "(Dolina o'limi, AQSh).")]
pos = [(0.75, 1.6), (6.85, 1.6), (0.75, 4.35), (6.85, 4.35)]
fshapes = []
for (fx, fy), (ft, fb) in zip(pos, facts):
    c = card(s, fx, fy, 5.75, 2.5, RGBColor(0x15, 0x1E, 0x3D), None,
             [(ft, 22, True, SUMMER), (fb, 15, False, SOFT)])
    fshapes.append(c)
anim(s, h, 'fade', 600, 0)
for c in fshapes:
    anim(s, c, 'grow', 600, 200)
TRANS[id(s)] = ('<p14:fragment/>', 1700)

# ---------------------------------------------------------------- SLIDE 9
s = new_slide()
bg_image(s, 'assets_seasons/title.png')
overlay(s, 48)
t1 = txt(s, 1.0, 2.4, 11.3, 1.4, "Tabiat — eng buyuk san'atkor", 48, WHITE,
         True, PP_ALIGN.CENTER)
t2 = txt(s, 1.5, 3.9, 10.3, 0.8, "E'tiboringiz uchun rahmat!  🍃 ☀️  ❄️",
         26, SOFT, False, PP_ALIGN.CENTER, italic=True)
x = 2.42
chips = []
for name, col in names:
    c = card(s, x, 5.1, 2.0, 0.75, col, None, [(name, 20, True, NAVY)],
             PP_ALIGN.CENTER)
    chips.append(c); x += 2.18
anim(s, t1, 'grow', 800, 0)
anim(s, t2, 'fade', 700, 250)
for c in chips:
    anim(s, c, 'wipe', 500, 150)
TRANS[id(s)] = ('<p14:ripple/>', 1800)

# ================================================================ INJECT
P_NS = 'http://schemas.openxmlformats.org/presentationml/2006/main'
P14_NS = 'http://schemas.microsoft.com/office/powerpoint/2010/main'


def inject(slide, idx):
    el = slide._element
    # --- transition
    body, dur = TRANS[id(slide)]
    tr_xml = (f'<p:transition xmlns:p="{P_NS}" xmlns:p14="{P14_NS}" '
              f'spd="slow" p14:dur="{dur}">{body}</p:transition>')
    el.append(etree.fromstring(tr_xml))
    # --- timing (entrance animations, auto-play on slide show)
    effects = ANIMS.get(id(slide), [])
    if not effects:
        return
    nid = [1]

    def next_id():
        nid[0] += 1
        return nid[0] - 1

    eff_xml = []
    for spid, kind, edur, delay in effects:
        pid = next_id()
        beh = [f'<p:set><p:cBhvr><p:cTn id="{next_id()}" dur="1" fill="hold">'
               f'<p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
               f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl><p:attrNameLst>'
               f'<p:attrName>style.visibility</p:attrName></p:attrNameLst>'
               f'</p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>']
        if kind == 'fade':
            preset, sub = 10, 0
            beh.append(f'<p:animEffect transition="in" filter="fade"><p:cBhvr>'
                       f'<p:cTn id="{next_id()}" dur="{edur}"/>'
                       f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr>'
                       f'</p:animEffect>')
        elif kind == 'wipe':
            preset, sub = 22, 4
            beh.append(f'<p:animEffect transition="in" filter="wipe(right)">'
                       f'<p:cBhvr><p:cTn id="{next_id()}" dur="{edur}"/>'
                       f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr>'
                       f'</p:animEffect>')
        else:  # grow = zoom + fade
            preset, sub = 16, 0
            beh.append(f'<p:animScale from="0 0" to="100000 100000"><p:cBhvr>'
                       f'<p:cTn id="{next_id()}" dur="{edur}"/>'
                       f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr>'
                       f'</p:animScale>')
            beh.append(f'<p:animEffect transition="in" filter="fade"><p:cBhvr>'
                       f'<p:cTn id="{next_id()}" dur="{edur}"/>'
                       f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr>'
                       f'</p:animEffect>')
        eff_xml.append(
            f'<p:par><p:cTn id="{pid}" presetID="{preset}" presetClass="entr" '
            f'presetSubtype="{sub}" fill="hold" grpId="0" nodeType="afterEffect">'
            f'<p:stCondLst><p:cond delay="{delay}"/></p:stCondLst>'
            f'<p:childTnLst>{"".join(beh)}</p:childTnLst></p:cTn></p:par>')
    root_id = next_id()
    seq_id = next_id()
    g1 = next_id()
    g2 = next_id()
    timing = (
        f'<p:timing xmlns:p="{P_NS}"><p:tnLst><p:par>'
        f'<p:cTn id="{root_id}" dur="indefinite" restart="never" nodeType="tmRoot">'
        f'<p:childTnLst><p:seq concurrent="1" nextAc="seek">'
        f'<p:cTn id="{seq_id}" dur="indefinite" nodeType="mainSeq">'
        f'<p:childTnLst><p:par><p:cTn id="{g1}" fill="hold">'
        f'<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
        f'<p:par><p:cTn id="{g2}" fill="hold">'
        f'<p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
        f'{"".join(eff_xml)}'
        f'</p:childTnLst></p:cTn></p:par>'
        f'</p:childTnLst></p:cTn></p:par></p:childTnLst>'
        f'<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/>'
        f'</p:tgtEl></p:cond></p:prevCondLst>'
        f'<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/>'
        f'</p:tgtEl></p:cond></p:nextCondLst>'
        f'</p:cTn></p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>')
    el.append(etree.fromstring(timing))


for i, slide in enumerate(prs.slides):
    inject(slide, i)

OUT = 'yil_fasllari.pptx'
prs.save(OUT)
print('saved', OUT, 'slides:', len(prs.slides.__iter__.__self__._sldIdLst))
