# -*- coding: utf-8 -*-
"""text_autofit 单元测试。"""
import hashlib
import zipfile

import pytest
from pptx.util import Inches

from conftest import make_box, text_autofit as ta


def _norm(tf):
    from pptx.oxml.ns import qn
    bodyPr = tf._txBody.find(qn("a:bodyPr"))
    return bodyPr.find(qn("a:normAutofit"))


def test_fits_returns_full_scale(empty_prs, stub_metrics):
    """文字放得下时不应缩排，但属性仍写入（fontScale=100000）。"""
    tb = make_box(empty_prs, 1, 1, 5, 3, "短文本", size=14)
    report = ta.autofit_presentation(empty_prs, metrics=stub_metrics)
    assert report[0]["scale"] == 1.0
    el = _norm(tb.text_frame)
    assert el is not None
    assert el.get("fontScale") == "100000"


def test_overflow_shrinks_and_fits(empty_prs, stub_metrics):
    """溢出时必须缩小，且缩小后估算高度不超过可用高度。"""
    long_cn = "这是一段很长的中文文本。" * 20
    tb = make_box(empty_prs, 1, 1, 4, 0.6, long_cn, size=18)
    report = ta.autofit_presentation(empty_prs, metrics=stub_metrics)
    rec = report[0]
    assert rec["scale"] < 1.0

    scale = rec["scale"]
    need, _, avail, _ = ta.measure_frame(tb.text_frame, tb, stub_metrics, scale)
    assert need <= avail


def test_scale_quantized_to_5_percent(empty_prs, stub_metrics):
    """缩放比必须落在 5% 步进上，避免出现 0.783 这种值。"""
    tb = make_box(empty_prs, 1, 1, 4, 0.8, "中文溢出测试" * 12, size=16)
    ta.autofit_presentation(empty_prs, metrics=stub_metrics)
    fs = int(_norm(tb.text_frame).get("fontScale"))
    assert fs % 5000 == 0, fs


def test_never_below_min_scale(empty_prs, stub_metrics):
    """极端溢出时不得低于下限。"""
    tb = make_box(empty_prs, 1, 1, 2, 0.3, "极小框里的超长文本" * 40, size=24)
    report = ta.autofit_presentation(empty_prs, metrics=stub_metrics)
    assert report[0]["scale"] >= ta.MIN_SCALE
    assert int(_norm(tb.text_frame).get("fontScale")) >= int(ta.MIN_SCALE * 100000)


def test_sp_autofit_shapes_are_skipped(empty_prs, stub_metrics):
    """spAutoFit（形状随文字长高）不应被缩排，也不应写入 fontScale。"""
    tb = make_box(empty_prs, 1, 1, 4, 0.6, "很长的文本" * 30, size=18,
                  autofit_none=False)
    from pptx.enum.text import MSO_AUTO_SIZE
    tb.text_frame.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
    report = ta.autofit_presentation(empty_prs, metrics=stub_metrics)
    assert report == []
    assert _norm(tb.text_frame) is None


def test_no_wrap_uses_single_line(empty_prs, stub_metrics):
    """不换行时只算一行高度，不因文字长而缩小。"""
    tb = make_box(empty_prs, 1, 1, 6, 2, "This is a very long line " * 6,
                  size=12, wrap=False)
    report = ta.autofit_presentation(empty_prs, metrics=stub_metrics)
    assert report[0]["lines"] == 1


def test_theme_parts_untouched(tmp_path, stub_metrics):
    """核心保证：只改 slide XML，主题/母版/媒体字节不变。"""
    from pptx import Presentation
    prs = Presentation()
    make_box(prs, 1, 1, 4, 0.6, "溢出文本" * 30, size=18,
             name="case")
    src = tmp_path / "src.pptx"
    prs.save(src)

    prs2 = Presentation(str(src))
    ta.autofit_presentation(prs2, metrics=stub_metrics)
    dst = tmp_path / "dst.pptx"
    prs2.save(dst)

    SENSITIVE = ("ppt/theme/", "ppt/slideMasters/", "ppt/slideLayouts/",
                 "ppt/media/")

    def hashes(p):
        with zipfile.ZipFile(p) as z:
            return {n: hashlib.sha256(z.read(n)).hexdigest()
                    for n in z.namelist() if n.startswith(SENSITIVE)}

    before, after = hashes(src), hashes(dst)
    assert before, "样本里应当有主题/母版 part"
    assert before == after, "主题/母版/媒体被改动了"

    # slide xml 确实变了
    with zipfile.ZipFile(src) as z:
        old_slide = z.read("ppt/slides/slide1.xml")
    with zipfile.ZipFile(dst) as z:
        new_slide = z.read("ppt/slides/slide1.xml")
    assert old_slide != new_slide


# ------------------------------------------------------- 组合缩放 / 断行 / 覆盖
def test_group_scale_halves_available_space(empty_prs, stub_metrics):
    """组内形状的实际渲染尺寸 = 自身尺寸 × 组变换比，必须被计入。"""
    from pptx.util import Inches
    from pptx.oxml.ns import qn

    slide = empty_prs.slides.add_slide(empty_prs.slide_layouts[6])
    group = slide.shapes.add_group_shape()
    inner = group.shapes.add_textbox(Inches(0), Inches(0), Inches(4), Inches(1))

    xfrm = group._element.grpSpPr.xfrm
    ext = xfrm.find(qn("a:ext"))
    ch = xfrm.find(qn("a:chExt"))
    # 子坐标空间是外部的 2 倍 → 实际显示缩小一半
    ch.set("cx", str(int(ext.get("cx")) * 2))
    ch.set("cy", str(int(ext.get("cy")) * 2))

    sx, sy = ta._group_scale(inner)
    assert sx == pytest.approx(0.5)
    assert sy == pytest.approx(0.5)

    _, _, avail_h, _ = ta.measure_frame(inner.text_frame, inner, stub_metrics)
    # 1 inch × 0.5 = 36pt，减去上下边距（各 0.05 inch）≈ 28.8pt
    assert avail_h == pytest.approx(28.8, abs=1.0)


def test_tokenize_splits_cjk_per_char_and_latin_per_word():
    """CJK 逐字断，拉丁按词断（词尾空格随词一起带走）。"""
    assert ta.tokenize("中文") == ["中", "文"]
    assert ta.tokenize("hello world") == ["hello ", "world"]
    assert ta.tokenize("A中") == ["A", "中"]


def test_write_replaces_existing_autofit_element(empty_prs):
    """写入前必须先清掉旧的 spAutoFit/noAutofit，否则 PowerPoint 行为不确定。"""
    from lxml import etree
    from pptx.oxml.ns import qn

    tb = make_box(empty_prs, 1, 1, 4, 2, "文本", size=14)
    tf = tb.text_frame
    bodyPr = tf._txBody.find(qn("a:bodyPr"))
    for tag in ("a:normAutofit", "a:spAutoFit", "a:noAutofit"):
        for el in bodyPr.findall(qn(tag)):
            bodyPr.remove(el)
    etree.SubElement(bodyPr, qn("a:spAutoFit"))

    ta.write_norm_autofit(tf, 0.85)
    assert bodyPr.find(qn("a:spAutoFit")) is None
    norm = bodyPr.find(qn("a:normAutofit"))
    assert norm is not None
    assert norm.get("fontScale") == "85000"


def test_table_cells_processed_only_when_enabled(empty_prs, stub_metrics):
    """表格单元格默认跳过（行高会自适应），显式开启后才处理。"""
    from pptx.util import Inches

    slide = empty_prs.slides.add_slide(empty_prs.slide_layouts[6])
    tbl = slide.shapes.add_table(1, 1, Inches(1), Inches(1),
                                 Inches(3), Inches(0.6)).table
    tbl.cell(0, 0).text = "很长的表格内容" * 8

    assert ta.autofit_presentation(empty_prs, metrics=stub_metrics) == []

    empty_prs2 = __import__("pptx").Presentation()
    slide2 = empty_prs2.slides.add_slide(empty_prs2.slide_layouts[6])
    tbl2 = slide2.shapes.add_table(1, 1, Inches(1), Inches(1),
                                   Inches(3), Inches(0.6)).table
    tbl2.cell(0, 0).text = "很长的表格内容" * 8
    rep = ta.autofit_presentation(empty_prs2, metrics=stub_metrics,
                                  include_cells=True)
    assert len(rep) == 1