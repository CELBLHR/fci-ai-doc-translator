# -*- coding: utf-8 -*-
"""pytest 公共夹具。

两个约定
--------
1. 测试用 PPT 全部在 tmp 目录即时生成，不提交二进制样本。
2. 被测模块按**文件路径**加载，不走 `import app.xxx`——因为 `app/__init__.py`
   会拉起 Flask / SQLAlchemy 等整套 Web 依赖，单元测试不需要它们。
"""
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load(name: str, rel_path: str):
    path = os.path.join(ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# 供测试直接 import
text_autofit = _load("text_autofit", os.path.join("app", "function", "text_autofit.py"))
color_fidelity = _load("color_fidelity", os.path.join("app", "function", "color_fidelity.py"))


class StubMetrics:
    """确定性字体度量：不依赖系统字体，任何 CI 机器结果一致。

    规则：拉丁字符 0.5em、CJK 1.0em、行高固定 1.2em。
    """

    def width_pt(self, text, font_name, size_pt, bold):
        em = 0.0
        for ch in text or "":
            em += 1.0 if ord(ch) > 0x2E80 else 0.5
        return em * size_pt

    def line_height_pt(self, font_name, size_pt, bold):
        return 1.2 * size_pt


@pytest.fixture
def stub_metrics():
    return StubMetrics()


@pytest.fixture
def empty_prs():
    from pptx import Presentation
    prs = Presentation()
    prs.slide_width = 9144000      # 10 inch
    prs.slide_height = 6858000     # 7.5 inch
    return prs


def make_box(prs, x_in, y_in, w_in, h_in, text, size=14, wrap=True,
             autofit_none=True, name=None):
    """在新增的一页上放一个固定尺寸文本框。"""
    from pptx.util import Inches, Pt
    from pptx.enum.text import MSO_AUTO_SIZE

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    tb = slide.shapes.add_textbox(Inches(x_in), Inches(y_in),
                                  Inches(w_in), Inches(h_in))
    tf = tb.text_frame
    tf.word_wrap = wrap
    if autofit_none:
        tf.auto_size = MSO_AUTO_SIZE.NONE     # 固定尺寸，不随文字长高
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.name = "Arial"
    if name:
        tb.name = name
    return tb


def set_solid_fill(run, inner_xml):
    """给 run 写入自定义 solidFill（可带 schemeClr 与修饰符）。"""
    from lxml import etree
    from pptx.oxml.ns import qn
    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    rPr = run._r.get_or_add_rPr()
    for el in rPr.findall(qn("a:solidFill")):
        rPr.remove(el)
    rPr.insert(0, etree.fromstring(
        f'<a:solidFill xmlns:a="{A}">{inner_xml}</a:solidFill>'))
