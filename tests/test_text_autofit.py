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
