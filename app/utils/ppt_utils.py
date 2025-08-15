"""
PPT处理相关工具函数
从ppt_translate.py中提取的通用工具函数
"""
import re
import difflib
import logging
from typing import Optional, Tuple, Any
from pptx.dml.color import RGBColor

logger = logging.getLogger(__name__)


def get_font_color(run) -> Optional[Tuple[int, int, int]]:
    """
    获取字体颜色
    
    Args:
        run: 文本运行对象
        
    Returns:
        RGB颜色元组或None
    """
    try:
        if run.font.color.type == 1:  # RGB颜色
            color = run.font.color.rgb
            return (color.r, color.g, color.b)
        elif run.font.color.type == 2:  # 主题颜色
            # 对于主题颜色，返回None，表示使用默认颜色
            return None
        else:
            return None
    except Exception:
        return None


def apply_font_color(run, color_info):
    """
    应用字体颜色
    
    Args:
        run: 文本运行对象
        color_info: 颜色信息（RGB元组或None）
    """
    try:
        if color_info and len(color_info) == 3:
            r, g, b = color_info
            run.font.color.rgb = RGBColor(r, g, b)
    except Exception as e:
        logger.warning(f"应用字体颜色失败: {str(e)}")


def compare_strings_ignore_spaces(str1: str, str2: str) -> bool:
    """
    比较两个字符串，忽略空格和换行符
    
    Args:
        str1: 第一个字符串
        str2: 第二个字符串
        
    Returns:
        是否相等
    """
    if not str1 or not str2:
        return str1 == str2
    
    # 移除所有空白字符并转换为小写进行比较
    clean_str1 = re.sub(r'\s+', '', str1.lower())
    clean_str2 = re.sub(r'\s+', '', str2.lower())
    
    return clean_str1 == clean_str2


def find_most_similar(target: str, candidates: list, threshold: float = 0.6) -> str:
    """
    在候选列表中找到与目标字符串最相似的字符串
    
    Args:
        target: 目标字符串
        candidates: 候选字符串列表
        threshold: 相似度阈值
        
    Returns:
        最相似的字符串，如果没有超过阈值的则返回目标字符串
    """
    if not target or not candidates:
        return target
    
    best_match = target
    best_ratio = 0
    
    for candidate in candidates:
        if not candidate:
            continue
        
        # 使用序列匹配器计算相似度
        ratio = difflib.SequenceMatcher(None, target.lower(), candidate.lower()).ratio()
        
        if ratio > best_ratio and ratio >= threshold:
            best_ratio = ratio
            best_match = candidate
    
    return best_match


def remove_invalid_utf8_chars(text: str) -> str:
    """
    移除无效的UTF-8字符
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    if not text:
        return text
    
    try:
        # 编码为UTF-8然后解码，忽略错误
        return text.encode('utf-8', errors='ignore').decode('utf-8')
    except Exception:
        return text


def is_valid_reference(text: str) -> bool:
    """
    判断文本是否为有效的引用（如页码、图表编号等）
    
    Args:
        text: 待判断的文本
        
    Returns:
        是否为有效引用
    """
    if not text or len(text.strip()) == 0:
        return False
    
    text = text.strip()
    
    # 检查是否为纯数字
    if text.isdigit():
        return True
    
    # 检查是否为常见的引用格式
    reference_patterns = [
        r'^\d+$',  # 纯数字
        r'^[A-Za-z]\d+$',  # 字母+数字
        r'^\d+[A-Za-z]$',  # 数字+字母
        r'^[A-Za-z]+\s*\d+$',  # 字母+空格+数字
        r'^\d+\s*[A-Za-z]+$',  # 数字+空格+字母
        r'^[IVXivx]+$',  # 罗马数字
    ]
    
    for pattern in reference_patterns:
        if re.match(pattern, text):
            return True
    
    return False


def is_page_number(text: str) -> bool:
    """
    判断文本是否为页码
    
    Args:
        text: 待判断的文本
        
    Returns:
        是否为页码
    """
    if not text:
        return False
    
    text = text.strip()
    
    # 检查是否为纯数字且在合理范围内
    if text.isdigit():
        num = int(text)
        return 1 <= num <= 9999  # 合理的页码范围
    
    # 检查是否为罗马数字
    roman_pattern = r'^[IVXivx]+$'
    if re.match(roman_pattern, text):
        return True
    
    return False


def normalize_text_for_comparison(text: str) -> str:
    """
    标准化文本用于比较
    
    Args:
        text: 原始文本
        
    Returns:
        标准化后的文本
    """
    if not text:
        return ""
    
    # 转换为小写
    text = text.lower()
    
    # 移除多余的空白字符
    text = re.sub(r'\s+', ' ', text)
    
    # 移除标点符号
    text = re.sub(r'[^\w\s]', '', text)
    
    # 去除首尾空格
    text = text.strip()
    
    return text


def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的相似度
    
    Args:
        text1: 第一个文本
        text2: 第二个文本
        
    Returns:
        相似度分数（0-1之间）
    """
    if not text1 or not text2:
        return 0.0
    
    # 标准化文本
    norm_text1 = normalize_text_for_comparison(text1)
    norm_text2 = normalize_text_for_comparison(text2)
    
    if not norm_text1 or not norm_text2:
        return 0.0
    
    # 使用序列匹配器计算相似度
    return difflib.SequenceMatcher(None, norm_text1, norm_text2).ratio()


def is_translatable_text(text: str, min_length: int = 2) -> bool:
    """
    判断文本是否需要翻译
    
    Args:
        text: 待判断的文本
        min_length: 最小长度要求
        
    Returns:
        是否需要翻译
    """
    if not text or len(text.strip()) < min_length:
        return False
    
    text = text.strip()
    
    # 排除纯数字
    if text.isdigit():
        return False
    
    # 排除纯符号
    if re.match(r'^[^\w\s]+$', text):
        return False
    
    # 排除页码和引用
    if is_page_number(text) or is_valid_reference(text):
        return False
    
    # 排除URL
    if re.match(r'https?://', text):
        return False
    
    # 排除邮箱
    if re.match(r'\S+@\S+\.\S+', text):
        return False
    
    return True


def extract_meaningful_text(text: str) -> str:
    """
    提取有意义的文本内容
    
    Args:
        text: 原始文本
        
    Returns:
        提取的有意义文本
    """
    if not text:
        return ""
    
    # 移除多余的空白字符
    text = re.sub(r'\s+', ' ', text)
    
    # 移除首尾空格
    text = text.strip()
    
    # 如果文本太短或不需要翻译，返回空字符串
    if not is_translatable_text(text):
        return ""
    
    return text


def split_text_into_sentences(text: str) -> list:
    """
    将文本分割成句子
    
    Args:
        text: 原始文本
        
    Returns:
        句子列表
    """
    if not text:
        return []
    
    # 使用正则表达式分割句子
    sentence_pattern = r'[.!?。！？]+\s*'
    sentences = re.split(sentence_pattern, text)
    
    # 过滤空句子并清理
    result = []
    for sentence in sentences:
        cleaned = sentence.strip()
        if cleaned and is_translatable_text(cleaned):
            result.append(cleaned)
    
    return result
