"""
PPTX格式转换工具模块
提供格式转换、文本相似度匹配、上下标处理等工具函数
"""
import logging
import difflib
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

def rgb_to_pptx_color(rgb_value):
    """
    将RGB值转换为python-pptx的颜色格式
    
    Args:
        rgb_value: RGB值，可能的格式:
                  - int: 0xRRGGBB 格式
                  - tuple: (R, G, B)
                  - list: [R, G, B]
    
    Returns:
        RGBColor: python-pptx的RGBColor对象
    """
    try:
        if isinstance(rgb_value, int):
            # 处理 0xRRGGBB 格式
            r = (rgb_value >> 16) & 0xFF
            g = (rgb_value >> 8) & 0xFF
            b = rgb_value & 0xFF
        elif isinstance(rgb_value, (tuple, list)) and len(rgb_value) >= 3:
            # 处理 (R, G, B) 或 [R, G, B] 格式
            r, g, b = rgb_value[0], rgb_value[1], rgb_value[2]
        else:
            # 默认黑色
            r, g, b = 0, 0, 0
        
        # 确保值在有效范围内
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        
        return RGBColor(r, g, b)
        
    except Exception as e:
        logging.warning(f"转换RGB颜色失败: {rgb_value}, 错误: {str(e)}, 使用默认黑色")
        return RGBColor(0, 0, 0)

def apply_superscript_subscript(run, escapement):
    """
    应用上下标格式
    使用您提供的 run.font._element.set('baseline', value) 方法
    
    Args:
        run: python-pptx的Run对象
        is_superscript: 是否为上标
        is_subscript: 是否为下标
    """
    try:
        if escapement != 0:
            # 设置上标，baseline值为正数
            run.font._element.set('baseline', '30000')
            logging.debug("应用上标格式")
        else:
            # 清除上下标，恢复基线
            run.font._element.set('baseline', '0')
            
    except Exception as e:
        logging.error(f"设置上下标失败: {str(e)}")

def set_font_properties(run, font_size, color, bold, italic, underline):
    """
    设置字体属性的统一接口
    
    Args:
        run: python-pptx的Run对象
        font_size: 字体大小（磅值）
        color: 字体颜色（RGB值）
        bold: 是否粗体
        italic: 是否斜体
        underline: 是否下划线
    """
    try:
        font = run.font
        
        # 设置字体大小
        if font_size and font_size > 0:
            font.size = Pt(font_size)
        
        # 设置字体颜色
        if color is not None:
            try:
                pptx_color = rgb_to_pptx_color(color)
                font.color.rgb = pptx_color
            except Exception as e:
                logging.warning(f"设置字体颜色失败: {color}, 错误: {str(e)}")
        
        # 设置粗体
        if bold is not None:
            font.bold = bool(bold)
        
        # 设置斜体
        if italic is not None:
            font.italic = bool(italic)
        
        # 设置下划线
        if underline is not None:
            font.underline = bool(underline)
            
        logging.debug(f"字体属性设置完成: 大小={font_size}, 粗体={bold}, 斜体={italic}")
        
    except Exception as e:
        logging.error(f"设置字体属性失败: {str(e)}")

def calculate_text_similarity(text1, text2):
    """
    计算文本相似度（复用原有算法）
    
    Args:
        text1: 第一个文本
        text2: 第二个文本
    
    Returns:
        float: 相似度值 (0.0 - 1.0)
    """
    try:
        if not text1 and not text2:
            return 1.0
        
        if not text1 or not text2:
            return 0.0
        
        # 标准化文本（去除空白字符）
        text1_clean = ''.join(text1.split())
        text2_clean = ''.join(text2.split())
        
        if text1_clean == text2_clean:
            return 1.0
        
        # 使用difflib计算相似度
        similarity = difflib.SequenceMatcher(None, text1_clean, text2_clean).ratio()
        
        # 考虑长度差异的惩罚因子
        length_diff = abs(len(text1_clean) - len(text2_clean))
        max_length = max(len(text1_clean), len(text2_clean))
        
        if max_length > 0:
            length_penalty = 1.0 - (length_diff / max_length) * 0.3  # 最大30%的长度惩罚
            similarity *= max(0.7, length_penalty)  # 最低保持70%的相似度
        
        return similarity
        
    except Exception as e:
        logging.error(f"计算文本相似度失败: {str(e)}")
        return 0.0

def normalize_text_for_matching(text):
    """
    标准化文本用于匹配
    
    Args:
        text: 原始文本
    
    Returns:
        str: 标准化后的文本
    """
    try:
        if not text:
            return ""
        
        # 去除多余空白字符
        normalized = ' '.join(text.split())
        
        # 转换为小写（可选，根据需要调整）
        # normalized = normalized.lower()
        
        return normalized
        
    except Exception as e:
        logging.error(f"标准化文本失败: {str(e)}")
        return text or ""

def parse_font_size(size_value):
    """
    解析字体大小值
    
    Args:
        size_value: 字体大小值，可能是字符串或数字
    
    Returns:
        int: 解析后的字体大小（磅值）
    """
    try:
        if isinstance(size_value, (int, float)):
            return max(1, int(size_value))
        
        if isinstance(size_value, str):
            # 尝试提取数字
            import re
            numbers = re.findall(r'\d+', size_value)
            if numbers:
                return max(1, int(numbers[0]))
        
        # 默认字体大小
        return 12
        
    except Exception as e:
        logging.warning(f"解析字体大小失败: {size_value}, 错误: {str(e)}, 使用默认值12")
        return 12

def convert_color_format(color_value):
    """
    转换各种颜色格式为标准RGB值
    
    Args:
        color_value: 颜色值，支持多种格式
    
    Returns:
        int: RGB颜色值 (0xRRGGBB格式)
    """
    try:
        if isinstance(color_value, int):
            return color_value
        
        if isinstance(color_value, (tuple, list)) and len(color_value) >= 3:
            r, g, b = int(color_value[0]), int(color_value[1]), int(color_value[2])
            return (r << 16) | (g << 8) | b
        
        if isinstance(color_value, str):
            # 尝试解析十六进制颜色
            if color_value.startswith('#'):
                hex_color = color_value[1:]
                if len(hex_color) == 6:
                    return int(hex_color, 16)
        
        # 默认黑色
        return 0x000000
        
    except Exception as e:
        logging.warning(f"转换颜色格式失败: {color_value}, 错误: {str(e)}, 使用默认黑色")
        return 0x000000

def validate_format_data(fragment_data):
    """
    验证和修正格式数据
    
    Args:
        fragment_data: 文本片段格式数据
    
    Returns:
        dict: 验证后的格式数据
    """
    try:
        validated_data = {}
        
        # 验证字体大小
        validated_data['font_size'] = parse_font_size(fragment_data.get('font_size', 12))
        
        # 验证颜色
        validated_data['color'] = convert_color_format(fragment_data.get('color', 0))
        
        # 验证布尔值
        validated_data['bold'] = bool(fragment_data.get('bold', False))
        validated_data['italic'] = bool(fragment_data.get('italic', False))
        validated_data['underline'] = bool(fragment_data.get('underline', False))
        validated_data['escapement'] = bool(fragment_data.get('escapement', 0))
        
        # 验证文本内容
        validated_data['text'] = str(fragment_data.get('text', ''))
        validated_data['translated_text'] = str(fragment_data.get('translated_text', ''))
        
        return validated_data
        
    except Exception as e:
        logging.error(f"验证格式数据失败: {str(e)}")
        return {
            'font_size': 12,
            'color': 0,
            'bold': False,
            'italic': False,
            'underline': False,
            'escapement': 0,
            'text': '',
            'translated_text': ''
        }

def extract_run_properties(run):
    """
    提取Run对象的属性信息（调试用）
    
    Args:
        run: python-pptx的Run对象
    
    Returns:
        dict: 属性信息
    """
    try:
        properties = {
            'text': run.text,
            'font_size': run.font.size.pt if run.font.size else None,
            'bold': run.font.bold,
            'italic': run.font.italic,
            'underline': run.font.underline,
        }
        
        # 尝试获取颜色信息
        try:
            if run.font.color.rgb:
                color = run.font.color.rgb
                properties['color'] = f"RGB({color.r}, {color.g}, {color.b})"
        except:
            properties['color'] = "未知"
        
        return properties
        
    except Exception as e:
        return {'error': str(e)}

def compare_format_properties(expected, actual_run):
    """
    比较期望的格式属性和实际Run对象的属性（调试用）
    
    Args:
        expected: 期望的格式属性字典
        actual_run: 实际的Run对象
    
    Returns:
        dict: 比较结果
    """
    try:
        actual_props = extract_run_properties(actual_run)
        
        comparison = {
            'matches': {},
            'mismatches': {}
        }
        
        # 比较字体大小
        expected_size = expected.get('font_size')
        actual_size = actual_props.get('font_size')
        if expected_size == actual_size:
            comparison['matches']['font_size'] = expected_size
        else:
            comparison['mismatches']['font_size'] = {'expected': expected_size, 'actual': actual_size}
        
        # 比较粗体
        expected_bold = expected.get('bold', False)
        actual_bold = actual_props.get('bold', False)
        if expected_bold == actual_bold:
            comparison['matches']['bold'] = expected_bold
        else:
            comparison['mismatches']['bold'] = {'expected': expected_bold, 'actual': actual_bold}
        
        return comparison
        
    except Exception as e:
        return {'error': str(e)}

# 测试函数
def test_format_utils():
    """测试格式工具函数"""
    logging.basicConfig(level=logging.DEBUG)
    
    # 测试RGB颜色转换
    test_colors = [
        0xFF0000,  # 红色
        (255, 0, 0),  # 红色元组
        [0, 255, 0],  # 绿色列表
        "#0000FF",  # 蓝色字符串
    ]
    
    print("测试RGB颜色转换:")
    for color in test_colors:
        pptx_color = rgb_to_pptx_color(color)
        print(f"  {color} -> RGB({pptx_color.r}, {pptx_color.g}, {pptx_color.b})")
    
    # 测试文本相似度
    test_texts = [
        ("Hello World", "Hello World"),  # 完全相同
        ("Hello World", "Hello world"),  # 大小写不同
        ("Hello", "Hi"),  # 完全不同
        ("The quick brown fox", "The brown fox"),  # 部分相同
    ]
    
    print("\n测试文本相似度:")
    for text1, text2 in test_texts:
        similarity = calculate_text_similarity(text1, text2)
        print(f"  '{text1}' vs '{text2}': {similarity:.2f}")
    
    # 测试格式数据验证
    test_fragment = {
        'font_size': '14',
        'color': (255, 0, 0),
        'bold': 1,
        'text': 'Test text'
    }
    
    print("\n测试格式数据验证:")
    validated = validate_format_data(test_fragment)
    print(f"  原始: {test_fragment}")
    print(f"  验证后: {validated}")

if __name__ == "__main__":
    test_format_utils()
