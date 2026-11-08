# -*- coding: utf-8 -*-
"""保真性测试：处理前后，非文本属性必须完全一致。

这是本项目的核心业务不变量——翻译错了用户能看出来，版式坏了直接不可用。
"""
import hashlib
import os
import sys
import zipfile

import pytest

from conftest import text_autofit as ta
from conftest import color_fidelity as cf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "fixtures"))
import builders  # noqa: E402

SENSITIVE_PREFIX = ("ppt/theme/", "ppt/slideMasters/",
                    "ppt/slideLayouts/", "ppt/media/")


# ------------------------------------------------------------------ 工具
def iter_shapes(shapes):
    """递归展开组合形状，逐个产出叶子形状。"""
    for sh in shapes:
        if sh.shape_type == 6:                 # GROUP
            yield from iter_shapes(sh.shapes)
        else:
            yield sh


def iter_frames(prs, include_cells=True):
    """产出 (名称, text_frame)，覆盖普通文本框与表格单元格。"""
    for slide in prs.slides:
        for sh in iter_shapes(slide.shapes):
            if getattr(sh, "has_text_frame", False):
                yield sh.name, sh.text_frame
            if include_cells and getattr(sh, "has_table", False):
                for ri, row in enumerate(sh.table.rows):
                    for ci, cell in enumerate(row.cells):
                        yield f"{sh.name}[{ri},{ci}]", cell.text_frame


def iter_runs(prs, include_cells=True):
    """产出 (名称, 序号, run)。"""
    for name, tf in iter_frames(prs, include_cells):
        for pi, para in enumerate(tf.paragraphs):
            for ri, run in enumerate(para.runs):
                yield name, f"p{pi}r{ri}", run


def part_hashes(path):
    out = {}
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if n.startswith(SENSITIVE_PREFIX):
                out[n] = hashlib.sha256(z.read(n)).hexdigest()
    return out


def shape_geometry(path):
    """每个叶子形状的 (名称, 左, 上, 宽, 高)。"""
    from pptx import Presentation
    prs = Presentation(path)
    rows = []
    for slide in prs.slides:
        for sh in iter_shapes(slide.shapes):
            rows.append((sh.name, int(sh.left), int(sh.top),
                         int(sh.width), int(sh.height)))
    return rows


def run_signatures(path):
    from pptx import Presentation
    prs = Presentation(path)
    return [(n, k, cf.color_signature(r), cf.rpr_signature(r))
            for n, k, r in iter_runs(prs)]


def text_of(path):
    from pptx import Presentation
    prs = Presentation(path)
    return [(n, tf.text) for n, tf in iter_frames(prs)]


def simulate_translation(prs):
    """
    模拟真正的翻译回填：只改文本，格式从 rPr 快照恢复。
    这正是 `color_fidelity` 要保证的用法。
    """
    for _, _, run in iter_runs(prs):
        snap = cf.snapshot_rpr(run)
        run.text = f"[译]{run.text}"
        cf.restore_rpr(run, snap)


# ------------------------------------------------------------------ 测试
def test_fixture_has_expected_elements(tmp_path):
    """先自检样本本身具备多样性，否则后面的断言没有意义。"""
    p = builders.build_mixed(str(tmp_path / "mixed.pptx"))
    names = [g[0] for g in shape_geometry(p)]
    assert "title" in names
    assert "themed" in names and "explicit_rgb" in names
    assert "grouped_text" in names, "组合形状未被展开"
    assert "overflow_box" in names


def test_theme_and_media_parts_untouched(tmp_path):
    """主题 / 母版 / 版式 / 媒体 必须字节级不变。"""
    src = builders.build_mixed(str(tmp_path / "src.pptx"))
    before = part_hashes(src)
    assert before, "样本应包含 theme/slideMaster 等 part"

    from pptx import Presentation
    prs = Presentation(src)
    ta.autofit_presentation(prs)
    dst = str(tmp_path / "dst.pptx")
    prs.save(dst)

    assert part_hashes(dst) == before, "主题/母版/媒体被改动"


def test_shape_geometry_unchanged(tmp_path):
    """形状位置与尺寸必须完全不变（autofit 只该改字号，不该改框）。"""
    src = builders.build_mixed(str(tmp_path / "src.pptx"))
    before = shape_geometry(src)

    from pptx import Presentation
    prs = Presentation(src)
    ta.autofit_presentation(prs)
    dst = str(tmp_path / "dst.pptx")
    prs.save(dst)

    assert shape_geometry(dst) == before


def test_run_formatting_preserved(tmp_path):
    """翻译回填后，每个 run 的颜色签名必须与原文一致。"""
    src = builders.build_mixed(str(tmp_path / "src.pptx"))
    before = run_signatures(src)

    from pptx import Presentation
    prs = Presentation(src)
    simulate_translation(prs)
    dst = str(tmp_path / "dst.pptx")
    prs.save(dst)

    after = run_signatures(dst)
    assert len(after) == len(before)

    bad = [(b[0], b[1]) for b, a in zip(before, after) if b[2] != a[2]]
    assert not bad, f"颜色被改动的 run: {bad}"


def test_text_actually_changed(tmp_path):
    """防止"什么都没做也算通过"：文本必须确实变化。"""
    src = builders.build_mixed(str(tmp_path / "src.pptx"))
    before = text_of(src)

    from pptx import Presentation
    prs = Presentation(src)
    simulate_translation(prs)
    dst = str(tmp_path / "dst.pptx")
    prs.save(dst)

    after = dict(text_of(dst))
    changed = sum(1 for n, t in before if t.strip() and after.get(n) != t)
    assert changed >= 10, f"只有 {changed} 个文本元素被改动"


def test_edge_cases_do_not_crash(tmp_path):
    """空文本框 / 不换行 / 极端溢出，处理不得抛异常。"""
    src = builders.build_edge(str(tmp_path / "edge.pptx"))
    from pptx import Presentation
    prs = Presentation(src)
    report = ta.autofit_presentation(prs)
    assert all("error" not in r for r in report), report
    dst = str(tmp_path / "edge-out.pptx")
    prs.save(dst)
    assert os.path.getsize(dst) > 0
