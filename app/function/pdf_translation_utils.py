#!/usr/bin/env python3
"""
PDF翻译工具模块
提供改进的段落匹配、译文写入和翻译处理功能
独立模块，不依赖其它项目文件
"""

import re
import logging
import asyncio
import difflib
import time
from typing import Dict, List, Tuple, Optional, Any, Callable, Union
from dataclasses import dataclass
from collections import defaultdict
import threading
from enum import Enum

logger = logging.getLogger(__name__)


class MatchStrategy(Enum):
    """匹配策略枚举"""
    EXACT = "exact"          # 精确匹配
    NORMALIZED = "normalized"  # 标准化匹配
    SIMILARITY = "similarity"   # 相似度匹配
    CONTEXT = "context"      # 上下文匹配


class TranslationStatus(Enum):
    """翻译状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class PDFParagraph:
    """PDF段落信息数据结构"""
    text: str                    # 段落文本
    page_num: int               # 页码 (1-基索引)
    bbox: Optional[Tuple[int, int, int, int]] = None  # 边界框 (left, top, right, bottom)
    region_id: Optional[str] = None  # 区域ID
    confidence: float = 1.0     # OCR置信度
    is_translatable: bool = True # 是否需要翻译
    length: int = 0             # 文本长度

    def __post_init__(self):
        self.length = len(self.text)


@dataclass
class TranslationResult:
    """翻译结果数据结构"""
    original_text: str          # 原文
    translated_text: str        # 译文
    strategy: MatchStrategy     # 匹配策略
    confidence: float           # 匹配置信度
    processing_time: float      # 处理时间(秒)
    status: TranslationStatus   # 翻译状态
    error_message: Optional[str] = None  # 错误信息
    retry_count: int = 0        # 重试次数


class ProgressTracker:
    """进度跟踪器"""

    def __init__(self, total_items: int = 0):
        self.total_items = total_items
        self.processed_items = 0
        self.failed_items = 0
        self.start_time = time.time()
        self._lock = threading.Lock()
        self.callback: Optional[Callable[[int, int, str], None]] = None
        self.current_stage = "初始化"

    def set_callback(self, callback: Callable[[int, int, str], None]):
        """设置进度回调函数"""
        self.callback = callback

    def update_progress(self, processed: int = 1, failed: int = 0, stage: Optional[str] = None):
        """更新进度"""
        with self._lock:
            self.processed_items += processed
            self.failed_items += failed
            if stage:
                self.current_stage = stage

            if self.callback:
                self.callback(self.processed_items, self.total_items, self.current_stage)

    def get_progress_info(self) -> Dict[str, Any]:
        """获取进度信息"""
        elapsed = time.time() - self.start_time
        return {
            "processed": self.processed_items,
            "total": self.total_items,
            "failed": self.failed_items,
            "success_rate": (self.processed_items / max(self.total_items, 1)) * 100,
            "elapsed_seconds": elapsed,
            "current_stage": self.current_stage,
            "estimated_remaining": self._estimate_remaining_time()
        }

    def _estimate_remaining_time(self) -> Optional[float]:
        """估算剩余时间"""
        if self.processed_items == 0:
            return None

        elapsed = time.time() - self.start_time()
        avg_time_per_item = elapsed / self.processed_items
        remaining_items = self.total_items - self.processed_items

        return avg_time_per_item * remaining_items

    def reset(self, total_items: Optional[int] = None):
        """重置进度跟踪器"""
        with self._lock:
            self.processed_items = 0
            self.failed_items = 0
            self.start_time = time.time()
            if total_items is not None:
                self.total_items = total_items
            self.current_stage = "初始化"


class PDFTranslationUtils:
    """
    PDF翻译工具类
    提供段落匹配、译文写入和翻译处理功能
    """

    def __init__(self,
                 max_retries: int = 3,
                 similarity_threshold: float = 0.7,
                 processing_timeout: int = 300):
        """
        初始化PDF翻译工具

        Args:
            max_retries: 最大重试次数
            similarity_threshold: 相似度匹配阈值
            processing_timeout: 处理超时时间(秒)
        """
        self.max_retries = max_retries
        self.similarity_threshold = similarity_threshold
        self.processing_timeout = processing_timeout

        # 初始化进度跟踪器
        self.progress_tracker = ProgressTracker()

        # 缓存区域匹配结果
        self._match_cache = {}

        # 支持的文本格式正则表达式
        self._format_patterns = {
            'brackets': r'【([^】]*)】',  # 中括号内内容
            'parentheses': r'\(([^)]*)\)',  # 圆括号内内容
            'quotes': r'[""]([^""]*)[""]',  # 引号内内容
        }

        logger.info("PDF翻译工具初始化完成")

    @staticmethod
    def normalize_text(text: str,
                      remove_punctuation: bool = True,
                      remove_spaces: bool = False,
                      to_lowercase: bool = True) -> str:
        """
        段落文本标准化函数

        Args:
            text: 输入文本
            remove_punctuation: 是否移除标点符号
            remove_spaces: 是否移除空格
            to_lowercase: 是否转换为小写

        Returns:
            标准化后的文本
        """
        if not text:
            return ""

        normalized = text

        # 转换为小写
        if to_lowercase:
            normalized = normalized.lower()

        # 移除标点符号
        if remove_punctuation:
            # 保留字母、数字、空格
            normalized = re.sub(r'[^\w\s]', '', normalized)

        # 移除空格（可选）
        if remove_spaces:
            normalized = normalized.replace(' ', '')

        # 移除多余的空白字符
        normalized = ' '.join(normalized.split())

        return normalized.strip()

    @staticmethod
    def is_translatable_text(text: str) -> bool:
        """
        判断文本是否需要翻译

        Args:
            text: 输入文本

        Returns:
            是否需要翻译
        """
        if not text or len(text.strip()) == 0:
            return False

        text = text.strip()

        # 跳过图片标记
        if text.startswith('![') and '](' in text and text.endswith(')'):
            logger.debug(f"跳过图片标记: '{text}'")
            return False

        # 跳过纯数字（包括小数点、百分号、连字符等）
        if re.match(r'^[\d\s\.,\-%/]+$', text):
            logger.debug(f"跳过纯数字: '{text}'")
            return False

        # 跳过纯标点符号
        if re.match(r'^[^\w\s]+$', text):
            logger.debug(f"跳过纯标点: '{text}'")
            return False

        # 跳过纯空格或特殊字符
        if re.match(r'^[\s\-_=+\*#@$%^&()<>[\]{}|\\;:,.!?]+$', text):
            logger.debug(f"跳过特殊字符: '{text}'")
            return False

        # 跳过英文或混合字符（简单检测）
        # 如果多于60%的字符是英文或其他语言，认为是不可翻译
        non_ascii_chars = sum(1 for c in text if ord(c) > 127)
        if len(text) > 0 and (non_ascii_chars / len(text)) > 0.6:
            logger.debug(f"跳过非中文文本: '{text[:50]}'")
            return False

        # 跳过单个字符
        if len(text) <= 1:
            logger.debug(f"跳过单字符: '{text}'")
            return False

        return True

    @staticmethod
    def _strip_inline_markdown(text: str) -> str:
        """
        移除常见的 Markdown 行内语法，确保发送到翻译API的文本与匹配时使用的文本一致
        - 粗体/斜体: **text**, __text__, *text*, _text_
        - 行内代码: `code`
        - 链接: [text](url) -> text
        - 图片标记: ![alt](path) -> alt
        - 引用残留的转义符号
        """
        try:
            original_text = text or ""
            s = original_text
            
            # 如果是纯图片标记，直接返回空字符串
            if s.strip().startswith('![') and '](' in s and s.strip().endswith(')'):
                # 检查是否只有图片标记，没有其他内容
                if s.strip() == s:
                    logger.debug(f"检测到纯图片标记，跳过清理: '{s[:50]}...'")
                    return ""
            
            # 图片: ![alt](path) -> alt
            s = re.sub(r"!\[([^\]]*)\]\([^\)]*\)", r"\1", s)
            # 链接: [text](url) -> text
            s = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", s)
            # 粗体/斜体包裹: **text** 或 __text__ 或 *text* 或 _text_
            s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
            s = re.sub(r"__([^_]+)__", r"\1", s)
            s = re.sub(r"\*([^*]+)\*", r"\1", s)
            s = re.sub(r"_([^_]+)_", r"\1", s)
            # 行内代码: `code`
            s = re.sub(r"`([^`]+)`", r"\1", s)
            # 数学: $...$ / \( ... \) / \[ ... \] -> 去除包裹符，只保留内部内容
            s = re.sub(r"\$\s*([^$]+?)\s*\$", r"\1", s)
            s = re.sub(r"\\\(\s*([^)]*?)\s*\\\)", r"\1", s)
            s = re.sub(r"\\\[\s*([^\\]]*?)\s*\\\]", r"\1", s)
            # 常见 LaTeX 语法清理: ^{...} / _{...} 去掉标记，保留内容
            s = re.sub(r"\^\s*\{\s*([^}]*)\s*\}", r"\1", s)
            s = re.sub(r"_\s*\{\s*([^}]*)\s*\}", r"\1", s)
            # 特定数学符号替换: 改进对 \prime、\cdot、\mathsf 等命令的处理
            # 处理带空格的命令，如 { \prime } 和 { \cdot }
            s = re.sub(r"\\prime\s*", "′", s)  # 将 \prime 替换为 Unicode 撇号
            s = re.sub(r"\{\s*\\prime\s*\}", "′", s)  # 将 { \prime } 替换为 Unicode 撇号
            s = re.sub(r"\\cdot\s*", "·", s)   # 将 \cdot 替换为 Unicode 中点
            s = re.sub(r"\{\s*\\cdot\s*\}", "·", s)   # 将 { \cdot } 替换为 Unicode 中点
            s = re.sub(r"\\times\s*", "×", s)  # 将 \times 替换为 Unicode 乘号
            s = re.sub(r"\\leq\s*", "≤", s)    # 将 \leq 替换为 Unicode 小于等于号
            s = re.sub(r"\\geq\s*", "≥", s)    # 将 \geq 替换为 Unicode 大于等于号
            s = re.sub(r"\\mathsf\s*\{?\s*([^}]*)\s*\}?", r"\1", s)  # 处理 \mathsf{L} 等格式
            s = re.sub(r"\\mathrm\s*\{?\s*([^}]*)\s*\}?", r"\1", s)  # 处理 \mathrm{R} 等格式
            # 处理更复杂的带空格花括号情况
            s = re.sub(r"\{\s*′\s*\}", "′", s)   # 将 { ′ } 替换为 ′
            s = re.sub(r"\{\s*·\s*\}", "·", s)   # 将 { · } 替换为 ·
            # 处理单独的 ^ 和 _ 符号
            s = re.sub(r"\^\s*", "", s)  # 去除单独的 ^ 符号
            s = re.sub(r"_\s*", "", s)   # 去除单独的 _ 符号
            # 去除多余的反斜杠和花括号空格
            s = s.replace("\\{", "{").replace("\\}", "}").replace("\\ ", " ")
            # 规范连字符与空格: 避免 ' - ' 残留空格
            s = re.sub(r"\s*-\s*", "-", s)
            # 特别处理百分号前的反斜杠，如30 \%
            s = re.sub(r"\\%", "%", s)
            # 折叠多空格
            s = re.sub(r"\s+", " ", s).strip()
            # 剩余的转义反斜杠
            s = s.replace("\\*", "*").replace("\\_", "_").replace("\\#", "#").replace("\\`", "`")
            
            # 记录文本清理操作
            if s != original_text:
                logger.debug(f"文本清理完成: '{original_text[:30]}...' -> '{s[:30]}...'")
            
            return s
        except Exception as e:
            logger.error(f"文本清理过程中出错: {e}")
            return text or ""

    def calculate_similarity_score(self,
                                  text1: str,
                                  text2: str,
                                  weight_length: float = 0.3,
                                  weight_content: float = 0.7) -> float:
        """
        计算两个文本的相似度分数

        Args:
            text1: 第一个文本
            text2: 第二个文本
            weight_length: 长度相似度权重
            weight_content: 内容相似度权重

        Returns:
            相似度分数 (0-1之间)
        """
        if not text1 or not text2:
            return 0.0

        # 长度相似度
        len1, len2 = len(text1), len(text2)
        length_similarity = 1.0 - abs(len1 - len2) / max(len1, len2, 1)

        # 内容相似度 (使用序列匹配)
        content_similarity = difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

        # 综合相似度
        total_similarity = length_similarity * weight_length + content_similarity * weight_content

        return min(total_similarity, 1.0)

    def match_translation_to_paragraph(self,
                                       paragraph: PDFParagraph,
                                       translation_dict: Dict[str, str],
                                       used_translations: set = None) -> Optional[TranslationResult]:
        """
        将翻译结果匹配到段落
        支持多策略匹配：精确 -> 标准化 -> 相似度 -> 上下文

        Args:
            paragraph: 段落信息
            translation_dict: 翻译字典 {原文: 译文}
            used_translations: 已使用的翻译原文集合

        Returns:
            翻译结果，如果匹配失败则返回None
        """
        if used_translations is None:
            used_translations = set()

        start_time = time.time()
        # 始终使用清理后的文本来进行匹配
        original_text = self._strip_inline_markdown(paragraph.text.strip())
        
        logger.debug(f"尝试匹配段落: '{original_text[:50]}...'")

        # 策略1: 精确匹配
        if original_text in translation_dict and original_text not in used_translations:
            translation = translation_dict[original_text]
            processing_time = time.time() - start_time
            logger.debug(f"精确匹配成功: '{original_text[:30]}...' -> '{translation[:30]}...'")
            return TranslationResult(
                original_text=original_text,
                translated_text=translation,
                strategy=MatchStrategy.EXACT,
                confidence=1.0,
                processing_time=processing_time,
                status=TranslationStatus.COMPLETED
            )

        # 策略2: 标准化匹配
        normalized_original = self.normalize_text(original_text, remove_punctuation=True)
        if normalized_original:
            # 查找所有标准化后匹配的翻译
            for orig_text, trans_text in translation_dict.items():
                if orig_text in used_translations:
                    continue

                # 标准化原文后匹配
                normalized_dict_text = self.normalize_text(orig_text, remove_punctuation=True)
                if normalized_dict_text == normalized_original:
                    processing_time = time.time() - start_time
                    logger.debug(f"标准化匹配成功: '{original_text[:30]}...' -> '{trans_text[:30]}...'")
                    return TranslationResult(
                        original_text=original_text,
                        translated_text=trans_text,
                        strategy=MatchStrategy.NORMALIZED,
                        confidence=0.9,  # 标准化匹配给较低置信度
                        processing_time=processing_time,
                        status=TranslationStatus.COMPLETED
                    )

        # 策略3: 相似度匹配（增强版）
        best_score = 0.0
        best_translation = None
        best_orig_text = None
        
        # 创建一个候选列表，用于后续的详细比较
        candidates = []
        
        for orig_text, trans_text in translation_dict.items():
            if orig_text in used_translations:
                continue
                
            # 使用多种相似度算法计算得分
            score1 = self.calculate_similarity_score(original_text, orig_text)
            score2 = self.calculate_normalized_similarity(original_text, orig_text)
            score3 = self.calculate_token_similarity(original_text, orig_text)
            
            # 综合得分（可以根据需要调整权重）
            combined_score = (score1 * 0.4 + score2 * 0.3 + score3 * 0.3)
            
            if combined_score >= self.similarity_threshold:
                candidates.append({
                    'orig_text': orig_text,
                    'trans_text': trans_text,
                    'score1': score1,
                    'score2': score2,
                    'score3': score3,
                    'combined_score': combined_score
                })
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_translation = trans_text
                    best_orig_text = orig_text

        # 从候选列表中选择最佳匹配
        if candidates:
            # 按综合得分排序
            candidates.sort(key=lambda x: x['combined_score'], reverse=True)
            
            # 选择得分最高的作为最佳匹配
            best_candidate = candidates[0]
            best_translation = best_candidate['trans_text']
            best_orig_text = best_candidate['orig_text']
            best_score = best_candidate['combined_score']
            
            processing_time = time.time() - start_time
            confidence = best_score
            logger.debug(f"相似度匹配成功 (score={best_score:.2f}): '{original_text[:30]}...' -> '{best_translation[:30]}...'")
            return TranslationResult(
                original_text=original_text,
                translated_text=best_translation,
                strategy=MatchStrategy.SIMILARITY,
                confidence=confidence,
                processing_time=processing_time,
                status=TranslationStatus.COMPLETED
            )

        # 策略4: 上下文匹配（保留给将来扩展）
        # TODO: 实现基于上下文的匹配算法

        processing_time = time.time() - start_time
        logger.debug(f"所有匹配策略失败: '{original_text[:30]}...'")
        return TranslationResult(
            original_text=original_text,
            translated_text="",
            strategy=MatchStrategy.CONTEXT,
            confidence=0.0,
            processing_time=processing_time,
            status=TranslationStatus.FAILED,
            error_message="未找到匹配的翻译"
        )

    def match_bulk_translations(self,
                                paragraphs: List[PDFParagraph],
                                translation_dict: Dict[str, str],
                                cleaned_text_mapping: Optional[Dict[str, str]] = None) -> Dict[int, TranslationResult]:
        """
        批量匹配段落的翻译结果

        Args:
            paragraphs: 段落列表
            translation_dict: 翻译字典 {原文: 译文}
            cleaned_text_mapping: 清理后的文本到原始文本的映射 {清理后: 原始}

        Returns:
            匹配结果字典 {段落实例ID: 翻译结果}
        """
        if not paragraphs:
            logger.warning("没有需要匹配的段落")
            return {}

        logger.info(f"开始批量匹配: {len(paragraphs)} 个段落 vs {len(translation_dict)} 条翻译")

        matches = {}
        used_translations = set()

        # 初始化进度跟踪
        self.progress_tracker.reset(len(paragraphs))
        self.progress_tracker.update_progress(0, 0, "开始匹配翻译")

        # 创建反向映射，从原始文本到清理后文本
        original_to_cleaned_mapping = {}
        if cleaned_text_mapping:
            original_to_cleaned_mapping = {v: k for k, v in cleaned_text_mapping.items()}

        for i, paragraph in enumerate(paragraphs):
            try:
                # 使用清理后的文本来进行匹配
                cleaned_paragraph_text = self._strip_inline_markdown(paragraph.text)
                
                # 创建一个临时段落，使用清理后的文本
                temp_paragraph = PDFParagraph(
                    text=cleaned_paragraph_text,
                    page_num=paragraph.page_num,
                    bbox=paragraph.bbox,
                    region_id=paragraph.region_id,
                    confidence=paragraph.confidence,
                    is_translatable=paragraph.is_translatable,
                    length=paragraph.length
                )
                
                result = self.match_translation_to_paragraph(
                    temp_paragraph,
                    translation_dict,
                    used_translations
                )

                if result and result.status == TranslationStatus.COMPLETED:
                    # 使用段落在列表中的索引作为键
                    matches[i] = result
                    # 只对成功的精确和标准化匹配标记为已使用
                    if result.strategy in [MatchStrategy.EXACT, MatchStrategy.NORMALIZED]:
                        used_translations.add(result.original_text)
                else:
                    # 匹配失败时的处理
                    if result:
                        result.status = TranslationStatus.FAILED
                        matches[i] = result

                # 更新进度
                if result and result.status == TranslationStatus.COMPLETED:
                    self.progress_tracker.update_progress(1, 0, f"匹配段落 {i+1}/{len(paragraphs)}")
                else:
                    self.progress_tracker.update_progress(1, 1, f"段落 {i+1} 匹配失败")

            except Exception as e:
                logger.error(f"段落 {i} 匹配时出错: {str(e)}")
                # 创建失败的结果
                failed_result = TranslationResult(
                    original_text=paragraph.text,
                    translated_text="",
                    strategy=MatchStrategy.CONTEXT,
                    confidence=0.0,
                    processing_time=0.0,
                    status=TranslationStatus.FAILED,
                    error_message=str(e)
                )
                matches[i] = failed_result
                self.progress_tracker.update_progress(1, 1, f"段落 {i+1} 错误")

        # 输出统计信息
        success_count = len([m for m in matches.values() if m.status == TranslationStatus.COMPLETED])
        logger.info(f"批量匹配完成: {success_count}/{len(paragraphs)} 个段落成功匹配")

        return matches

    async def write_translation_to_paragraph(self,
                                           paragraph: PDFParagraph,
                                           translation_result: TranslationResult,
                                           write_strategy: str = "replace",
                                           backup_original: bool = True) -> bool:
        """
        安全而健壮的译文写入方法

        Args:
            paragraph: 段落信息
            translation_result: 翻译结果
            write_strategy: 写入策略 ("replace", "append", "prepend")
            backup_original: 是否备份原文

        Returns:
            是否写入成功
        """
        try:
            logger.debug(f"开始写入翻译: 策略={write_strategy}, 段落={paragraph.text[:50]}...")

            # 验证输入
            if not translation_result or translation_result.status != TranslationStatus.COMPLETED:
                logger.error("翻译结果无效或未完成")
                return False

            # 根据策略准备新文本
            new_text = ""

            if write_strategy == "replace":
                # 完全替换
                new_text = translation_result.translated_text
            elif write_strategy == "append":
                # 添加到末尾
                if backup_original:
                    new_text = f"{paragraph.text}\n{translation_result.translated_text}"
                else:
                    new_text = translation_result.translated_text
            elif write_strategy == "prepend":
                # 添加到开头
                if backup_original:
                    new_text = f"{translation_result.translated_text}\n{paragraph.text}"
                else:
                    new_text = translation_result.translated_text
            else:
                logger.error(f"不支持的写入策略: {write_strategy}")
                return False

            # 基本文本验证
            if not self._validate_translation_text(paragraph.text, new_text):
                logger.error("翻译文本验证失败")
                return False

            # TODO: 在实际使用中，这里需要集成PDF处理库来写入翻译
            # 例如使用PyMuPDF (fitz) 来修改PDF内容
            # 这里只是框架，实际写入需要根据具体的PDF处理需求实现

            logger.info(f"翻译写入完成: {write_strategy} 策略")
            return True

        except Exception as e:
            logger.error(f"写入翻译时出错: {str(e)}")
            return False

    def _validate_translation_text(self, original_text: str, translated_text: str) -> bool:
        """
        验证翻译文本的基本有效性

        Args:
            original_text: 原文
            translated_text: 译文

        Returns:
            是否有效
        """
        if not translated_text:
            return False

        # 检查译文长度相对原文是否合理
        if len(translated_text) > len(original_text) * 5:
            logger.warning("译文过长，可能存在问题")
            return False

        if len(translated_text) < len(original_text) * 0.1:
            logger.warning("译文过短，可能存在问题")
            return False

        return True

    async def process_translation_with_retry(self,
                                           translate_func: Callable,
                                           text: str,
                                           *args,
                                           **kwargs) -> Optional[Dict[str, Any]]:
        """
        带有重试机制的翻译处理

        Args:
            translate_func: 翻译函数
            text: 要翻译的文本
            *args: 翻译函数的额外位置参数
            **kwargs: 翻译函数的额外关键字参数

        Returns:
            翻译结果字典，失败时返回None
        """
        retry_count = 0
        last_error = None

        while retry_count <= self.max_retries:
            try:
                logger.info(f"翻译尝试 {retry_count + 1}/{self.max_retries + 1}: {text[:50]}...")

                # 创建翻译任务
                if asyncio.iscoroutinefunction(translate_func):
                    result = await asyncio.wait_for(
                        translate_func(text, *args, **kwargs),
                        timeout=self.processing_timeout
                    )
                else:
                    # 如果不是协程函数，在线程池中执行
                    loop = asyncio.get_event_loop()
                    from concurrent.futures import ThreadPoolExecutor
                    executor = ThreadPoolExecutor(max_workers=1)
                    result = await asyncio.wait_for(
                        loop.run_in_executor(executor, translate_func, text, *args, **kwargs),
                        timeout=self.processing_timeout
                    )
                    executor.shutdown(wait=True)

                # 验证结果
                if result and isinstance(result, dict) and result.get('text'):
                    logger.info("翻译成功完成")
                    return result
                else:
                    logger.warning(f"翻译结果无效: {result}")
                    retry_count += 1
                    continue

            except asyncio.TimeoutError:
                last_error = "翻译超时"
                logger.warning(f"翻译超时 (尝试 {retry_count + 1})")
            except Exception as e:
                last_error = str(e)
                logger.error(f"翻译失败: {last_error}")

            retry_count += 1

            # 如果还有重试次数，等待一段时间
            if retry_count <= self.max_retries:
                wait_time = 2 ** retry_count  # 指数退避
                logger.info(f"等待 {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)

        logger.error(f"翻译失败，已达到最大重试次数: {last_error}")
        return None



# 便捷函数
def normalize_pdf_text(text: str) -> str:
    """
    便捷函数：标准化PDF文本

    Args:
        text: 输入文本

    Returns:
        标准化后的文本
    """
    return PDFTranslationUtils.normalize_text(text)


def is_pdf_text_translatable(text: str) -> bool:
    """
    便捷函数：判断PDF文本是否需要翻译

    Args:
        text: 输入文本

    Returns:
        是否需要翻译
    """
    return PDFTranslationUtils.is_translatable_text(text)


# 全局实例
pdf_translator = PDFTranslationUtils()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    # 测试段落标准化
    test_text = "这是一段测试文本（Test）！@#$%^"
    normalized = normalize_pdf_text(test_text)
    print(f"原文本: {test_text}")
    print(f"标准化: {normalized}")

    # 测试可翻译性
    print(f"需要翻译: {is_pdf_text_translatable('这是一段中文文本')}")
    print(f"需要翻译: {is_pdf_text_translatable('123.45%')}")