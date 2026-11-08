# -*- coding: utf-8 -*-
"""测试样本生成器。

原则：**不提交二进制 pptx**，所有样本在 tmp 目录即时构建。
这样断言和样本可以一起 review，也不会把真实文档带进仓库。
"""
import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.enum.text import MSO_AUTO_SIZE, MSO_ANCHOR
from pptx.util import Inches, Pt


def _textbox(slide, x, y, w, h, text, size=14, bold=False, name=None,
             wrap=True, fixed=True):
    from pptx.enum.text import MSO_AUTO_SIZE as AS
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    if fixed:
        tf.auto_size = AS.NONE          # 固定尺寸，模拟真实客户文档
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.name = "Arial"
    if name:
        tb.name = name
    return tb


def build_mixed(path):
    """一份覆盖主要版式要素的文档：多语言、主题色、表格、组合形状、溢出。"""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # ---- slide 1: 标题 + 正文 + 主题色 ----
    s1 = prs.slides.add_slide(prs.slide_layouts[6])
    _textbox(s1, 0.8, 0.5, 11, 1.0, "Quarterly Portfolio Review", 32,
             bold=True, name="title")

    for i, t in enumerate([
        "New accounts reach first value in under four minutes.",
        "Delivery on committed dates holds at ninety-nine percent.",
        "Unit cost is down across two consecutive quarters.",
    ]):
        _textbox(s1, 0.8, 2.0 + i * 0.9, 8, 0.6, t, 16, name=f"bullet{i}")

    # 主题色文字（accent1 / accent2）+ 显式 RGB
    colored = _textbox(s1, 0.8, 5.2, 5, 0.6, "Themed accent text", 20,
                       name="themed")
    run = colored.text_frame.paragraphs[0].runs[0]
    run.font.color.theme_color = MSO_THEME_COLOR.ACCENT_1

    rgb_box = _textbox(s1, 6.5, 5.2, 5, 0.6, "Explicit RGB text", 20,
                       name="explicit_rgb")
    rgb_run = rgb_box.text_frame.paragraphs[0].runs[0]
    rgb_run.font.color.rgb = RGBColor(0x00, 0xB0, 0x50)

    # ---- slide 2: 表格 + 组合形状 ----
    s2 = prs.slides.add_slide(prs.slide_layouts[6])
    _textbox(s2, 0.8, 0.4, 8, 0.7, "Quarterly Metrics", 26, bold=True,
             name="table_title")

    tbl = s2.shapes.add_table(3, 3, Inches(0.8), Inches(1.6),
                              Inches(7.0), Inches(2.2)).table
    head = ["Metric", "Q1", "Q2"]
    data = [["Active teams", "1,240", "1,580"],
            ["Retention", "81%", "86%"]]
    for c, h in enumerate(head):
        tbl.cell(0, c).text = h
    for r_i, row in enumerate(data, start=1):
        for c_i, v in enumerate(row):
            tbl.cell(r_i, c_i).text = v

    # 组合形状：里面放一个文本框，验证组内缩放与遍历
    group = s2.shapes.add_group_shape()
    inner = group.shapes.add_textbox(Inches(8.2), Inches(1.6),
                                     Inches(3.5), Inches(0.8))
    inner.name = "grouped_text"
    ip = inner.text_frame.paragraphs[0]
    ir = ip.add_run()
    ir.text = "Text inside a group shape"
    ir.font.size = Pt(15)

    # ---- slide 3: 长文本溢出（触发 autofit）----
    s3 = prs.slides.add_slide(prs.slide_layouts[6])
    _textbox(s3, 0.8, 0.4, 10, 0.7, "Dense Content", 26, bold=True,
             name="dense_title")
    _textbox(s3, 0.8, 1.4, 4.5, 0.8,
             "This paragraph is deliberately far too long to fit inside "
             "a text box of this height, so the autofit step has to reduce "
             "the effective font size. " * 3,
             16, name="overflow_box")

    prs.save(path)
    return path


def build_edge(path):
    """边界样本：空文本框、不换行、极端溢出。"""
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])

    empty = s.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(3), Inches(0.6))
    empty.name = "empty_box"

    _textbox(s, 0.5, 1.5, 6, 1.2, "Single line that must not wrap at all. " * 3,
             14, name="nowrap_box", wrap=False)
    _textbox(s, 0.5, 3.2, 2.0, 0.4, "极端溢出样本，文字量远超文本框容量。" * 10,
             22, name="extreme_box")
    _textbox(s, 7.0, 0.5, 5.0, 3.0, "普通文本，正常放下。", 18,
             name="normal_box")

    prs.save(path)
    return path
