# -*- coding: utf-8 -*-
"""
Generate a synthetic demo deck pair (EN original / ZH translated) and a
side-by-side comparison figure. 100% fabricated content - no client data.
"""
import os
import sys
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out")
os.makedirs(OUT, exist_ok=True)

NAVY = RGBColor(0x1F, 0x35, 0x64)
TEAL = RGBColor(0x2E, 0x9E, 0xAA)
AMBER = RGBColor(0xE8, 0xA8, 0x3C)
GRAY = RGBColor(0x5A, 0x62, 0x70)
LIGHT = RGBColor(0xF2, 0xF5, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARKTXT = RGBColor(0x22, 0x28, 0x33)

EN = "English"
ZH = "Chinese"

# ---------------------------------------------------------------- demo content
# Deliberately: every English string sits tight in its box, the Chinese
# translation is LONGER, so the original layout breaks - that is the point.
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

# fake but plausible translations (longer than original on purpose)
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
    "1,240": "1,240", "1,580": "1,580", "2,010": "2,010",
    "81%": "81%", "86%": "86%", "89%": "89%",
    "3.2k": "3.2k", "2.7k": "2.7k", "2.1k": "2.1k",
    "Retention is the clearest signal of product fit.":
        "留存率是产品与需求匹配程度最清晰的信号。",
    "Support load fell while accounts doubled.":
        "在账户数量翻倍的同时，支持负载反而下降了。",
    "Next step: expand into two adjacent segments.":
        "下一步：向两个相邻细分市场扩展。",
}


def set_font(run, size, bold=False, color=DARKTXT, name="Segoe UI", lang=EN,
             italic=False):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.name = name
    f.color.rgb = color
    rpr = run._r.get_or_add_rPr()
    rpr.set("lang", "zh-CN" if lang == ZH else "en-US")


def add_box(slide, x, y, w, h, shape_rect=False, fill=None, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    if shape_rect:
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
    tb = slide.shapes.add_textbox(x, y, w, h)
    return tb


def write(tf, text, size, bold=False, color=DARKTXT, align=PP_ALIGN.LEFT,
          anchor=MSO_ANCHOR.TOP, space_after=4, lang=EN, italic=False):
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = align
    p.space_after = Pt(space_after)
    r = p.add_run()
    r.text = text
    set_font(r, size, bold, color, lang=lang, italic=italic)


def build(translated=False):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    lang = ZH if translated else EN

    def t(s):
        return TR.get(s, s) if translated else s

    for spec in SLIDES:
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # background band
        add_box(slide, 0, 0, prs.slide_width, Inches(1.95),
                shape_rect=True, fill=NAVY)
        # accent bar
        add_box(slide, 0, Inches(1.95), prs.slide_width, Inches(0.12),
                shape_rect=True, fill=TEAL)

        # title  (fixed box, tight fit in EN -> overflows in ZH)
        tb = slide.shapes.add_textbox(Inches(0.85), Inches(0.55),
                                      Inches(10.2), Inches(0.95))
        write(tb.text_frame, t(spec["title"]), 34, bold=True, color=WHITE,
              anchor=MSO_ANCHOR.MIDDLE, lang=lang)

        if "subtitle" in spec:
            tb2 = slide.shapes.add_textbox(Inches(0.85), Inches(1.42),
                                           Inches(9.6), Inches(0.45))
            write(tb2.text_frame, t(spec["subtitle"]), 15, color=RGBColor(0xC9, 0xD6, 0xEA), lang=lang)

            # two stat cards (sized so ZH text wraps and grows but never overlaps)
            for i, (big, small) in enumerate(spec["blocks"]):
                x = Inches(0.85 + i * 3.15)
                add_box(slide, x, Inches(2.58), Inches(2.95), Inches(2.05),
                        shape_rect=True, fill=LIGHT, line=RGBColor(0xD8, 0xDF, 0xEA))
                tb3 = slide.shapes.add_textbox(x + Inches(0.24), Inches(2.78),
                                               Inches(2.5), Inches(0.95))
                write(tb3.text_frame, t(big), 26, bold=True, color=NAVY, lang=lang)
                tb4 = slide.shapes.add_textbox(x + Inches(0.24), Inches(3.86),
                                               Inches(2.5), Inches(0.62))
                write(tb4.text_frame, t(small), 12, bold=True, color=GRAY, lang=lang)

            tb5 = slide.shapes.add_textbox(Inches(0.85), Inches(5.05),
                                           Inches(9.0), Inches(0.5))
            write(tb5.text_frame, t(spec["foot"]), 12, color=GRAY, lang=lang)

        if "cards" in spec:
            for i, (head, body) in enumerate(spec["cards"]):
                y = Inches(2.45 + i * 1.62)
                add_box(slide, Inches(0.85), y, Inches(0.09), Inches(1.22),
                        shape_rect=True, fill=AMBER)
                tbh = slide.shapes.add_textbox(Inches(1.15), y - Inches(0.02),
                                               Inches(9.5), Inches(0.5))
                write(tbh.text_frame, t(head), 20, bold=True, color=NAVY, lang=lang)
                tbb = slide.shapes.add_textbox(Inches(1.15), y + Inches(0.5),
                                               Inches(9.5), Inches(0.7))
                write(tbb.text_frame, t(body), 14, bold=True, italic=True, color=GRAY, lang=lang)

        if "table" in spec:
            spec_t = spec["table"]
            rows, cols = len(spec_t["rows"]) + 1, len(spec_t["head"])
            left, top = Inches(0.85), Inches(2.45)
            width, height = Inches(7.1), Inches(3.4)
            table = slide.shapes.add_table(rows, cols, left, top, width, height).table
            for c, htxt in enumerate(spec_t["head"]):
                cell = table.cell(0, c)
                cell.text = ""
                p = cell.text_frame.paragraphs[0]
                r = p.add_run()
                r.text = t(htxt)
                set_font(r, 14, bold=True, color=WHITE, lang=lang)
                cell.fill.solid()
                cell.fill.fore_color.rgb = NAVY
            for ri, row in enumerate(spec_t["rows"], start=1):
                for ci, val in enumerate(row):
                    cell = table.cell(ri, ci)
                    cell.text = ""
                    p = cell.text_frame.paragraphs[0]
                    r = p.add_run()
                    r.text = t(val)
                    set_font(r, 13, bold=(ci == 0), color=DARKTXT, lang=lang)
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = LIGHT if ri % 2 else WHITE

            # right-hand takeaways (tight two-line box -> wraps in ZH)
            tbn = slide.shapes.add_textbox(Inches(8.35), Inches(2.45),
                                           Inches(4.15), Inches(3.4))
            tf = tbn.text_frame
            tf.word_wrap = True
            for i, note in enumerate(spec["notes"]):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.space_after = Pt(12)
                r = p.add_run()
                r.text = t(note)
                set_font(r, 13, bold=True, italic=True, color=GRAY, lang=lang)

    return prs


if __name__ == "__main__":
    en_path = os.path.join(OUT, "demo-original-en.pptx")
    zh_path = os.path.join(OUT, "demo-translated-zh.pptx")
    build(translated=False).save(en_path)
    build(translated=True).save(zh_path)
    print("saved:", en_path)
    print("saved:", zh_path)
