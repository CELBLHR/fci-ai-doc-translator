# -*- coding: utf-8 -*-
"""
Generate synthetic demo decks for the FCI AI translation showcase.

Modes
-----
en        English-only deck (the "source" document)
zh        Chinese-only deck (translation only)
bilingual ZH paragraph above, EN paragraph below ("上中下英")

All content is fabricated (fictional company "Northwind Labs", invented
metrics). No client data is used anywhere.
"""
import os
import sys

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out")
os.makedirs(OUT, exist_ok=True)

NAVY = RGBColor(0x1F, 0x35, 0x64)
TEAL = RGBColor(0x2E, 0x9E, 0xAA)
AMBER = RGBColor(0xE8, 0xA8, 0x3C)
GRAY = RGBColor(0x5A, 0x62, 0x70)
LIGHT = RGBColor(0xF2, 0xF5, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARKTXT = RGBColor(0x22, 0x28, 0x33)
SUBTXT = RGBColor(0xC9, 0xD6, 0xEA)

EN = "English"
ZH = "Chinese"

MODE = "en"           # en | zh | bilingual
BI_SCALE = 0.72       # bilingual needs two lines per paragraph


def S(x):
    """Scale a font size for the current mode."""
    return x * BI_SCALE if MODE == "bilingual" else x


# ---------------------------------------------------------------- demo content
SLIDES = [
    {
        "title": "Northwind Labs \u00b7 Portfolio Review",
        "subtitle": "Q3 Product Performance and FY26 Roadmap Direction",
        "blocks": [
            ("3 core products", "launched in 18 months"),
            ("42%", "revenue growth year over year"),
        ],
        "foot": "Internal review \u00b7 Q3 FY25",
    },
    {
        "title": "Where We Win, Where We Stall",
        "cards": [
            ("Fast onboarding",
             "New accounts reach first value in under four minutes."),
            ("Reliable pipeline",
             "Ninety-nine point nine percent delivery on committed dates."),
            ("Cost discipline",
             "Unit cost down twenty-eight percent across two quarters."),
        ],
    },
    {
        "title": "Quarterly Metrics",
        "table": {
            "head": ["Metric", "Q1", "Q2", "Q3"],
            "rows": [
                ["Active teams", "1,240", "1,580", "2,010"],
                ["Retention", "81%", "86%", "89%"],
                ["Support load", "3.2k", "2.7k", "2.1k"],
            ],
        },
        "notes": [
            "Retention is the clearest signal of product fit.",
            "Support load fell while accounts doubled.",
            "Next step: expand into two adjacent segments.",
        ],
    },
]

# fabricated translations; deliberately longer than the English
TR = {
    "Northwind Labs \u00b7 Portfolio Review": "Northwind 实验室内 \u00b7 产品组合复盘",
    "Q3 Product Performance and FY26 Roadmap Direction":
        "第三季度产品表现评估与下一财年路线图方向",
    "3 core products": "3 条核心产品线",
    "launched in 18 months": "在 18 个月内完成发布",
    "42%": "42%",
    "revenue growth year over year": "年同比营收增长率",
    "Internal review \u00b7 Q3 FY25": "内部复盘材料 \u00b7 2025 财年第三季度",
    "Where We Win, Where We Stall": "我们的优势所在，以及停滞环节",
    "Fast onboarding": "快速上手体验",
    "New accounts reach first value in under four minutes.":
        "新账户平均在四分钟以内即可获得首次可用价值。",
    "Reliable pipeline": "可靠的交付管道",
    "Ninety-nine point nine percent delivery on committed dates.":
        "在承诺日期完成交付的比例达到百分之九十九点九。",
    "Cost discipline": "成本管控",
    "Unit cost down twenty-eight percent across two quarters.":
        "在两个季度内将单位成本降低了百分之二十八。",
    "Quarterly Metrics": "各季度关键指标",
    "Metric": "指标", "Q1": "一季度", "Q2": "二季度", "Q3": "三季度",
    "Active teams": "活跃团队数", "Retention": "留存率", "Support load": "支持负载",
    "Retention is the clearest signal of product fit.":
        "留存率是产品与需求匹配程度最清晰的信号。",
    "Support load fell while accounts doubled.":
        "在账户数量翻倍的同时，支持负载反而下降了。",
    "Next step: expand into two adjacent segments.":
        "下一步：向两个相邻细分市场扩展。",
}


# ---------------------------------------------------------------- primitives
def set_font(run, size, bold=False, color=DARKTXT, lang=EN, italic=False):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.name = "Segoe UI"
    f.color.rgb = color
    run._r.get_or_add_rPr().set("lang", "zh-CN" if lang == ZH else "en-US")


def _prep(tf, anchor):
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0


def _para(tf, text, size, bold, color, align, space_after, lang, italic, first):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    r = p.add_run()
    r.text = text
    set_font(r, size, bold, color, lang=lang, italic=italic)


def emit(tf, text, size, bold=False, color=DARKTXT, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, space_after=4, italic=False):
    """Write one logical string according to the active MODE."""
    _prep(tf, anchor)
    if MODE == "en":
        _para(tf, text, size, bold, color, align, space_after, EN, italic, True)
    elif MODE == "zh":
        _para(tf, TR.get(text, text), size, bold, color, align, space_after,
              ZH, italic, True)
    else:  # bilingual: Chinese above, English below
        _para(tf, TR.get(text, text), size, bold, color, align, 1.5, ZH,
              italic, True)
        _para(tf, text, size * 0.94, bold, color, align, space_after, EN,
              italic, False)


def cell_emit(cell, text, size, bold=False, color=DARKTXT, sub_color=None):
    tf = cell.text_frame
    _prep(tf, MSO_ANCHOR.MIDDLE)
    p0 = tf.paragraphs[0]
    p0.alignment = PP_ALIGN.LEFT
    r = p0.add_run()
    if MODE == "en":
        r.text = text
        set_font(r, size, bold, color, lang=EN)
    elif MODE == "zh":
        r.text = TR.get(text, text)
        set_font(r, size, bold, color, lang=ZH)
    else:
        r.text = TR.get(text, text)
        set_font(r, size, bold, color, lang=ZH)
        p1 = tf.add_paragraph()
        p1.alignment = PP_ALIGN.LEFT
        p1.space_before = Pt(1)
        r1 = p1.add_run()
        r1.text = text
        set_font(r1, size * 0.82, bold, sub_color or GRAY, lang=EN)


def rect(slide, x, y, w, h, fill=None, line=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
    shp.shadow.inherit = False
    return shp


# ---------------------------------------------------------------- deck builder
def build(mode):
    global MODE
    MODE = mode
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    for spec in SLIDES:
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        rect(slide, 0, 0, prs.slide_width, Inches(1.95), fill=NAVY)
        rect(slide, 0, Inches(1.95), prs.slide_width, Inches(0.12), fill=TEAL)

        tb = slide.shapes.add_textbox(Inches(0.85), Inches(0.40),
                                      Inches(10.6), Inches(1.05))
        emit(tb.text_frame, spec["title"], S(34), bold=True, color=WHITE,
             anchor=MSO_ANCHOR.MIDDLE)

        if "subtitle" in spec:
            tb2 = slide.shapes.add_textbox(Inches(0.85), Inches(1.48),
                                           Inches(9.6), Inches(0.42))
            emit(tb2.text_frame, spec["subtitle"], S(15), color=SUBTXT)

            for i, (big, small) in enumerate(spec["blocks"]):
                x = Inches(0.85 + i * 3.15)
                rect(slide, x, Inches(2.58), Inches(2.95), Inches(2.05),
                     fill=LIGHT, line=RGBColor(0xD8, 0xDF, 0xEA))
                tb3 = slide.shapes.add_textbox(x + Inches(0.24), Inches(2.78),
                                               Inches(2.5), Inches(1.0))
                emit(tb3.text_frame, big, S(26), bold=True, color=NAVY)
                tb4 = slide.shapes.add_textbox(x + Inches(0.24), Inches(3.88),
                                               Inches(2.5), Inches(0.62))
                emit(tb4.text_frame, small, S(12), bold=True, color=GRAY)

            tb5 = slide.shapes.add_textbox(Inches(0.85), Inches(5.05),
                                           Inches(9.0), Inches(0.5))
            emit(tb5.text_frame, spec["foot"], S(12), color=GRAY)

        if "cards" in spec:
            for i, (head, body) in enumerate(spec["cards"]):
                y = Inches(2.42 + i * 1.64)
                rect(slide, Inches(0.85), y, Inches(0.09), Inches(1.26),
                     fill=AMBER)
                tbh = slide.shapes.add_textbox(Inches(1.15), y - Inches(0.02),
                                               Inches(9.6), Inches(0.56))
                emit(tbh.text_frame, head, S(20), bold=True, color=NAVY)
                tbb = slide.shapes.add_textbox(Inches(1.15), y + Inches(0.52),
                                               Inches(9.6), Inches(0.72))
                emit(tbb.text_frame, body, S(14), bold=True, italic=True,
                     color=GRAY)

        if "table" in spec:
            tspec = spec["table"]
            rows, cols = len(tspec["rows"]) + 1, len(tspec["head"])
            table = slide.shapes.add_table(
                rows, cols, Inches(0.85), Inches(2.42),
                Inches(7.1), Inches(3.4)).table
            for c, htxt in enumerate(tspec["head"]):
                cell = table.cell(0, c)
                cell.text = ""
                cell_emit(cell, htxt, S(14), bold=True, color=WHITE,
                          sub_color=SUBTXT)
                cell.fill.solid()
                cell.fill.fore_color.rgb = NAVY
            for ri, row in enumerate(tspec["rows"], start=1):
                for ci, val in enumerate(row):
                    cell = table.cell(ri, ci)
                    cell.text = ""
                    cell_emit(cell, val, S(13), bold=(ci == 0))
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = LIGHT if ri % 2 else WHITE

            tbn = slide.shapes.add_textbox(Inches(8.35), Inches(2.42),
                                           Inches(4.15), Inches(3.5))
            _prep(tbn.text_frame, MSO_ANCHOR.TOP)
            first = True
            for note in spec["notes"]:
                if MODE == "bilingual":
                    _para(tbn.text_frame, TR.get(note, note), S(13), True, GRAY,
                          PP_ALIGN.LEFT, 1.5, ZH, True, first)
                    first = False
                    _para(tbn.text_frame, note, S(13) * 0.92, True, GRAY,
                          PP_ALIGN.LEFT, 9, EN, True, False)
                else:
                    txt = note if MODE == "en" else TR.get(note, note)
                    lang = EN if MODE == "en" else ZH
                    _para(tbn.text_frame, txt, S(13), True, GRAY, PP_ALIGN.LEFT,
                          9, lang, True, first)
                    first = False

    return prs


if __name__ == "__main__":
    targets = {
        "en": "demo-original-en.pptx",
        "zh": "demo-translated-zh.pptx",
        "bilingual": "demo-bilingual-zh-en.pptx",
    }
    for mode, name in targets.items():
        path = os.path.join(OUT, name)
        build(mode).save(path)
        print("saved:", path)
