# -*- coding: utf-8 -*-
"""color_fidelity 单元测试。

期望值来源：本机 PowerPoint 12.0 COM 读回的 `Font.Color.RGB` 实测结果
（2026-10-21，Office 2007 默认主题 accent1=#4F81BD、accent2=#C0504D）。
"""
import hashlib
import zipfile

import pytest

from conftest import make_box, set_solid_fill
from conftest import color_fidelity as cf

_apply_mods = cf._apply_mods
snapshot_rpr = cf.snapshot_rpr
restore_rpr = cf.restore_rpr
color_signature = cf.color_signature
load_theme = cf.load_theme
load_clr_map = cf.load_clr_map
resolve_run_color = cf.resolve_run_color


# --------------------------------------------------------------- 修饰符数学
def test_lum_mod_matches_powerpoint():
    """accent1 + lumMod75 + lumOff15 -> PowerPoint 实测 #5686C0。"""
    assert _apply_mods((79, 129, 189), {"lumMod": 75000, "lumOff": 15000}) == (86, 134, 192)


def test_shade_is_linear_space():
    """accent2 + shade60 -> PowerPoint 实测 #993E3C。

    若按 gamma 空间直接乘 0.6 会得到 #73302E——这是本测试要守住的关键差异。
    """
    assert _apply_mods((192, 80, 77), {"shade": 60000}) == (153, 62, 60)


def test_tint_moves_toward_white():
    out = _apply_mods((192, 80, 77), {"tint": 40000})
    assert all(c > base for c, base in zip(out, (192, 80, 77)))


def test_identity_modifiers_return_same_color():
    assert _apply_mods((79, 129, 189), {}) == (79, 129, 189)


# --------------------------------------------------------------- 快照/恢复
@pytest.mark.parametrize("inner,label", [
    ('<a:srgbClr val="FF0000"/>', "rgb"),
    ('<a:schemeClr val="accent1"/>', "scheme"),
    ('<a:schemeClr val="accent1"><a:lumMod val="75000"/>'
     '<a:lumOff val="15000"/></a:schemeClr>', "scheme+mods"),
    ('<a:schemeClr val="accent2"><a:shade val="60000"/></a:schemeClr>',
     "scheme+shade"),
])
def test_snapshot_restore_is_lossless(empty_prs, inner, label):
    """核心保证：清空 rPr 后从快照恢复，颜色子树字节级不变。"""
    tb = make_box(empty_prs, 1, 1, 4, 1, "原文", size=18)
    run = tb.text_frame.paragraphs[0].runs[0]
    set_solid_fill(run, inner)

    before = color_signature(run)
    snap = snapshot_rpr(run)

    # 模拟"重建 run"：清掉所有格式
    from pptx.oxml.ns import qn
    rPr = run._r.get_or_add_rPr()
    for el in list(rPr):
        rPr.remove(el)

    assert color_signature(run) != before      # 确实丢了
    restore_rpr(run, snap)
    assert color_signature(run) == before      # 恢复后完全一致


def test_restore_keeps_translation_lang(empty_prs):
    """恢复格式时不应覆盖译文侧的语言标记。"""
    tb = make_box(empty_prs, 1, 1, 4, 1, "原文", size=18)
    run = tb.text_frame.paragraphs[0].runs[0]
    set_solid_fill(run, '<a:schemeClr val="accent1"/>')
    snap = snapshot_rpr(run)

    rPr = run._r.get_or_add_rPr()
    rPr.set("lang", "zh-CN")
    restore_rpr(run, snap)
    assert rPr.get("lang") == "zh-CN"


# --------------------------------------------------------------- 主题色解析
def test_resolve_explicit_rgb(empty_prs):
    tb = make_box(empty_prs, 1, 1, 4, 1, "x", size=18)
    run = tb.text_frame.paragraphs[0].runs[0]
    set_solid_fill(run, '<a:srgbClr val="00B050"/>')
    info = resolve_run_color(run, {}, {})
    assert info["kind"] == "rgb"
    assert info["rgb"] == (0, 176, 80)


def test_resolve_scheme_through_clr_map(empty_prs):
    """bg1/tx1 必须经 clrMap 映射到 lt1/dk1 才能取到颜色。"""
    tb = make_box(empty_prs, 1, 1, 4, 1, "x", size=18)
    run = tb.text_frame.paragraphs[0].runs[0]
    set_solid_fill(run, '<a:schemeClr val="tx1"/>')

    theme = {"dk1": (0, 0, 0), "lt1": (255, 255, 255)}
    clr_map = {"bg1": "lt1", "tx1": "dk1"}
    info = resolve_run_color(run, theme, clr_map)
    assert info["rgb"] == (0, 0, 0)


def test_load_theme_and_clr_map(tmp_path):
    """从真实 pptx 包中读出 clrScheme 与 clrMap。"""
    from pptx import Presentation
    prs = Presentation()
    make_box(prs, 1, 1, 4, 1, "x", size=18)
    p = tmp_path / "t.pptx"
    prs.save(p)

    with zipfile.ZipFile(p) as zf:
        theme = load_theme(zf)
        clr_map = load_clr_map(zf, "ppt/slides/slide1.xml")

    assert "accent1" in theme and len(theme["accent1"]) == 3
    assert clr_map.get("tx1") == "dk1"
    assert clr_map.get("bg1") == "lt1"
