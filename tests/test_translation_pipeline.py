# -*- coding: utf-8 -*-
"""翻译链路测试：完整性、回填对齐、降级行为。

模型调用一律 mock，不触网、不花钱、结果确定。
被测模块按**合成包**加载，绕开 `app/__init__.py` 的 Flask 依赖。
"""
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNC_DIR = os.path.join(ROOT, "app", "function")

PKG = "_app_function"


def _ensure_pkg():
    if PKG not in sys.modules:
        pkg = types.ModuleType(PKG)
        pkg.__path__ = [FUNC_DIR]
        sys.modules[PKG] = pkg
    return sys.modules[PKG]


def load(name: str):
    """把 app/function/<name>.py 作为合成包下的子模块加载。"""
    _ensure_pkg()
    full = f"{PKG}.{name}"
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(
        full, os.path.join(FUNC_DIR, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


pbt = load("page_based_translation")


# ------------------------------------------------------------ 测试脚手架
@pytest.fixture
def stub_model(monkeypatch):
    """注入假的 translate_async；返回一个可设置的响应容器。"""
    state = {"calls": 0, "response": {}, "error": None}

    async def fake_translate_async(text, field=None, stop_words=None,
                                   custom_translations=None,
                                   source_language="en", target_language="zh",
                                   **kw):
        state["calls"] += 1
        if state["error"]:
            raise state["error"]
        return state["response"]

    mod = types.ModuleType(f"{PKG}.local_qwen_async")
    mod.translate_async = fake_translate_async
    sys.modules[f"{PKG}.local_qwen_async"] = mod
    yield state
    sys.modules.pop(f"{PKG}.local_qwen_async", None)


@pytest.fixture
def slide_with_table_and_text():
    """一页幻灯片：1 个普通文本框 + 1 个 2x2 表格。"""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
    tb.name = "plain_textbox"
    tb.text_frame.text = "A normal textbox paragraph."
    tbl = s.shapes.add_table(2, 2, Inches(1), Inches(3),
                             Inches(4), Inches(1.2)).table
    tbl.cell(0, 0).text = "Header A"
    tbl.cell(0, 1).text = "Header B"
    tbl.cell(1, 0).text = "Value 1"
    tbl.cell(1, 1).text = "Value 2"
    return prs, s


def make_para(text, idx, translatable=True, shape_type="textbox"):
    return pbt.ParagraphInfo(
        text=text, slide_index=0, shape_index=0, paragraph_index=idx,
        shape_type=shape_type, is_translatable=translatable)


# ------------------------------------------------------------ 完整性
def test_collect_includes_all_table_cells(slide_with_table_and_text):
    """表格每个单元格都必须被收集（历史上的表格漏译 bug）。"""
    _, s = slide_with_table_and_text
    paras = pbt.PageBasedTranslator().collect_slide_paragraphs(s, 0)
    texts = {p.text for p in paras}
    assert {"Header A", "Header B", "Value 1", "Value 2"} <= texts
    assert all(p.shape_type == "table" for p in paras)


@pytest.mark.xfail(
    strict=True,
    reason="collect_slide_paragraphs 里收集普通文本框的代码被整段注释掉了"
           "（page_based_translation.py:82-101），只剩表格。"
           "修复后本用例会 XPASS，届时请去掉 xfail 标记。")
def test_collect_includes_textbox_paragraphs(slide_with_table_and_text):
    """普通文本框也必须被收集，否则文本框内容永远不会被翻译。"""
    _, s = slide_with_table_and_text
    paras = pbt.PageBasedTranslator().collect_slide_paragraphs(s, 0)
    assert any("A normal textbox paragraph." == p.text for p in paras)


def test_prepare_wraps_only_translatable():
    """拼给模型的文本只包含可翻译段落，且用【】标记边界。"""
    tr = pbt.PageBasedTranslator()
    paras = [make_para("Hello world", 0),
             make_para("123", 1, translatable=False),
             make_para("Second line", 2)]
    text = tr.prepare_translation_text(paras)
    assert "Hello world" in text and "Second line" in text
    assert "123" not in text
    assert "【" in text and "】" in text
    assert text.count("\n") == 1          # 两段 → 一个换行


@pytest.mark.parametrize("text,expected", [
    ("", False),
    ("   ", False),
    ("123", False),
    ("45.6%", False),
    ("---", False),
    ("A", False),
    ("Hello", True),
    ("你好", True),
])
def test_is_translatable_text(text, expected):
    tr = pbt.PageBasedTranslator()
    assert tr.is_translatable_text(text) is expected


# ------------------------------------------------------------ 回填对齐
def test_exact_match_maps_back():
    tr = pbt.PageBasedTranslator()
    paras = [make_para("Alpha", 0), make_para("Beta", 1)]
    matches = tr.match_translations_to_paragraphs_precise(
        paras, {"Alpha": "阿尔法", "Beta": "贝塔"})
    assert matches == {0: "阿尔法", 1: "贝塔"}


def test_normalized_match_handles_punctuation_drift():
    """模型改了个标点/空格时，标准化匹配应仍能对上。"""
    tr = pbt.PageBasedTranslator()
    paras = [make_para("Quarterly Metrics", 0)]
    matches = tr.match_translations_to_paragraphs_precise(
        paras, {"Quarterly  metrics.": "季度指标"})
    assert matches.get(0) == "季度指标"


def test_extra_translations_are_ignored():
    tr = pbt.PageBasedTranslator()
    paras = [make_para("Alpha", 0)]
    matches = tr.match_translations_to_paragraphs_precise(
        paras, {"Alpha": "阿尔法", "Ghost": "多余"})
    assert matches == {0: "阿尔法"}


def test_missing_translation_leaves_paragraph_unmatched():
    """模型漏段时，该段不出现在结果里——调用方应保留原文。"""
    tr = pbt.PageBasedTranslator()
    paras = [make_para("Alpha", 0), make_para("Beta", 1)]
    matches = tr.match_translations_to_paragraphs_precise(
        paras, {"Alpha": "阿尔法"})
    assert 0 in matches
    assert 1 not in matches


def test_untranslatable_paragraphs_are_skipped():
    tr = pbt.PageBasedTranslator()
    paras = [make_para("123", 0, translatable=False),
             make_para("Real text", 1)]
    matches = tr.match_translations_to_paragraphs_precise(
        paras, {"123": "一二三", "Real text": "真文本"})
    assert matches == {1: "真文本"}


def test_duplicate_paragraphs_collapse_today():
    """现状记录：两段完全相同的文字只会产出一个匹配。

    原因是 `paragraphs.index(para)` 依赖 dataclass 默认 __eq__，
    重复段落会命中同一个索引。这是真实风险（同一页出现两次同样的句子）。
    """
    tr = pbt.PageBasedTranslator()
    paras = [make_para("Same sentence", 0), make_para("Same sentence", 1)]
    matches = tr.match_translations_to_paragraphs_precise(
        paras, {"Same sentence": "同一句话"})
    assert len(matches) == 1


@pytest.mark.xfail(strict=True,
                   reason="重复段落目前会塌缩成一个匹配（dataclass 相等性 + "
                          "paragraphs.index），修复后本用例会 XPASS")
def test_duplicate_paragraphs_each_get_translation():
    tr = pbt.PageBasedTranslator()
    paras = [make_para("Same sentence", 0), make_para("Same sentence", 1)]
    matches = tr.match_translations_to_paragraphs_precise(
        paras, {"Same sentence": "同一句话"})
    assert len(matches) == 2


def test_similarity_score_bounds():
    tr = pbt.PageBasedTranslator()
    assert tr.calculate_similarity_score("abc", "abc") == pytest.approx(1.0)
    assert 0.0 <= tr.calculate_similarity_score("abc", "xyz") <= 1.0
    assert tr.calculate_similarity_score("", "") == pytest.approx(1.0)


# ------------------------------------------------------------ 降级行为
def test_api_error_returns_empty_without_crashing(stub_model,
                                                 slide_with_table_and_text):
    """模型抛异常时必须返回空结果，而不是把异常抛给上层。"""
    import asyncio
    stub_model["error"] = RuntimeError("429 Too Many Requests")
    prs, s = slide_with_table_and_text
    tr = pbt.PageBasedTranslator()
    result = asyncio.run(tr.translate_slide_paragraphs(s, 0, "en", "zh"))
    assert result == {}
    assert stub_model["calls"] == 1


def test_partial_model_response_is_tolerated(stub_model,
                                            slide_with_table_and_text):
    """模型只返回一部分段落时，已返回的照常回填。"""
    import asyncio
    stub_model["response"] = {"Header A": "表头甲"}
    prs, s = slide_with_table_and_text
    tr = pbt.PageBasedTranslator()
    result = asyncio.run(tr.translate_slide_paragraphs(s, 0, "en", "zh"))
    assert list(result.values()) == ["表头甲"]


def test_empty_model_response_yields_empty(stub_model,
                                          slide_with_table_and_text):
    import asyncio
    stub_model["response"] = {}
    prs, s = slide_with_table_and_text
    tr = pbt.PageBasedTranslator()
    assert asyncio.run(tr.translate_slide_paragraphs(s, 0, "en", "zh")) == {}
