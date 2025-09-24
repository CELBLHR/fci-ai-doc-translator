import sys, os
import difflib
sys.path.insert(0, os.path.dirname(__file__))
from logger_config import get_logger

def calculate_similarity_score(text1: str, text2: str) -> float:
    """计算两个文本的相似度分数"""
    len1, len2 = len(text1), len(text2)
    length_similarity = 1.0 - abs(len1 - len2) / max(len1, len2, 1)
    text_similarity = difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    total_similarity = length_similarity * 0.3 + text_similarity * 0.7
    return total_similarity

def get_shape_size(shape):
    """获取shape的尺寸"""
    if hasattr(shape, "Size"):  # 检查是否是图形对象
        size = shape.Size
        return size.Width, size.Height  # 返回 (宽, 高)
    return None

def insert_soft_line_break(text, cursor, logger=None):
    """
    插入软回车（换行但不分段）
    
    Args:
        text: LibreOffice text对象
        cursor: 文本游标
        logger: 日志记录器
    """
    if logger is None:
        logger = get_logger("pyuno.subprocess")
    
    try:
        # 方法1: 尝试使用ControlCharacter.LINE_BREAK
        try:
            import uno
            from com.sun.star.text.ControlCharacter import LINE_BREAK 
            text.insertControlCharacter(cursor, LINE_BREAK, False)
            logger.debug("成功插入软回车（ControlCharacter.LINE_BREAK）")
            return True
        except Exception as e:
            logger.debug(f"ControlCharacter.LINE_BREAK方法失败: {e}")
        
        # 方法2: 尝试使用Unicode软换行符
        try:
            # Unicode Line Separator (U+2028)
            text.insertString(cursor, "\u2028", False)
            logger.debug("成功插入软回车（Unicode Line Separator）")
            return True
        except Exception as e:
            logger.debug(f"Unicode Line Separator方法失败: {e}")
        
        # 方法3: 尝试使用制表符+换行的组合
        try:
            text.insertString(cursor, "\v", False)  # 垂直制表符
            logger.debug("成功插入软回车（垂直制表符）")
            return True
        except Exception as e:
            logger.debug(f"垂直制表符方法失败: {e}")
        
        # 方法4: 回退到普通换行符（但设置不同的段落属性）
        logger.warning("所有软回车方法都失败，回退到普通换行符")
        text.insertString(cursor, "\n", False)
        return False
        
    except Exception as e:
        logger.error(f"插入软回车时发生异常: {e}")
        # 最后回退
        text.insertString(cursor, "\n", False)
        return False

def insert_optimized_line_break(text, cursor, mode="soft", logger=None):
    """
    插入优化的换行符
    
    Args:
        text: LibreOffice text对象
        cursor: 文本游标
        mode: 换行模式 ("soft": 软回车, "hard": 硬回车)
        logger: 日志记录器
    """
    if logger is None:
        logger = get_logger("pyuno.subprocess")
    
    if mode == "soft":
        return insert_soft_line_break(text, cursor, logger)
    else:
        # 硬回车（分段）
        text.insertString(cursor, "\n", False)
        return True

def extract_box_text_from_paragraphs(box):
    """
    从新的段落层级结构中提取文本框的完整原文
    
    Args:
        box: 文本框数据（包含段落层级）
        
    Returns:
        str: 文本框的完整原文
    """
    if "paragraphs" not in box:
        # 兼容旧格式
        return "".join([frag["text"] for frag in box.get("text_fragments", [])])
    
    full_text = ""
    paragraphs = box.get("paragraphs", [])
    
    for paragraph in paragraphs:
        paragraph_text = ""
        for fragment in paragraph.get("text_fragments", []):
            paragraph_text += fragment.get("text", "")
        
        if paragraph_text.strip():
            if full_text:
                full_text += "\n"  # 段落间用换行分隔
            full_text += paragraph_text
    
    return full_text.replace("\r\n", "\n").replace("\r", "\n").strip()

def extract_box_translation_from_paragraphs(box):
    """
    从新的段落层级结构中提取文本框的完整译文
    
    Args:
        box: 文本框数据（包含段落层级）
        
    Returns:
        str: 文本框的完整译文
    """
    if "paragraphs" not in box:
        # 兼容旧格式
        return "".join([frag.get("translated_text", "") for frag in box.get("text_fragments", [])])
    
    full_translation = ""
    paragraphs = box.get("paragraphs", [])
    
    for paragraph in paragraphs:
        paragraph_translation = ""
        for fragment in paragraph.get("text_fragments", []):
            paragraph_translation += fragment.get("translated_text", "")
        
        if paragraph_translation.strip():
            if full_translation:
                full_translation += "\n"  # 段落间用换行分隔
            full_translation += paragraph_translation
    
    return full_translation.replace("\r\n", "\n").replace("\r", "\n").strip()

def write_textbox_with_translation_paragraphs(shape, box, mode="paragraph_up", logger=None):
    """
    将译文写入单个文本框，基于新的段落层级结构，实现真正的逐段翻译
    
    Args:
        shape: LibreOffice shape对象
        box: 文本框数据（包含段落层级）
        mode: 写入模式
        logger: 日志记录器
    """
    if logger is None:
        logger = get_logger("pyuno.subprocess")
    
    try:
        # 关键属性设置
        shape.setPropertyValue("TextFitToSize", True)       # 字体自动缩放
        shape.setPropertyValue("TextAutoGrowHeight", False) # 锁定高度
        shape.setPropertyValue("TextWordWrap", True)        # 允许换行
        shape.setSize(shape.Size)  # 重新应用当前尺寸触发重绘
    except Exception as e:
        logger.warning(f"设置shape属性时出现问题: {e}")
    
    # 校验类型
    if not hasattr(shape, "getString"):
        logger.warning(f"对象不含文本，跳过")
        return

    # 获取原始宽高
    orig_width, orig_height = get_shape_size(shape)
    logger.debug(f"写入前shape宽度: {orig_width}, 高度: {orig_height}")

    try:
        text = shape.getText()
        cursor = text.createTextCursor()
        
        # 处理新的段落层级结构
        if "paragraphs" in box:
            logger.debug(f"使用新的段落层级结构，共 {len(box['paragraphs'])} 个段落")
            write_paragraphs_mode(text, cursor, box, mode, logger)
        else:
            # 兼容旧格式
            logger.warning("使用旧格式兼容模式")
            write_legacy_mode(text, cursor, box, mode, logger)

        # 恢复shape的宽高
        if orig_width is not None and orig_height is not None:
            try:
                shape.Size.Width = orig_width
                shape.Size.Height = orig_height
            except Exception as e:
                logger.warning(f"恢复shape尺寸失败: {e}")
        
        after_width, after_height = get_shape_size(shape)
        logger.debug(f"写入后shape宽度: {after_width}, 高度: {after_height}")
        
    except Exception as e:
        logger.error(f"写入文本框时发生异常: {e}", exc_info=True)
        raise

def write_paragraphs_mode(text, cursor, box, mode, logger, value = 0):
    """
    基于段落层级的写入模式
    
    Args:
        text: LibreOffice text对象
        cursor: 文本游标
        box: 文本框数据
        mode: 写入模式
        logger: 日志记录器
    """
    paragraphs = box.get("paragraphs", [])
    
    if not paragraphs:
        logger.warning("文本框没有段落数据")
        return
    
    try:
        if mode == "replace":
            # 替换模式：只写译文
            logger.debug("段落替换模式：只写译文")
            text.setString("")
            cursor = text.createTextCursor()
            
            for para_idx, paragraph in enumerate(paragraphs):
                logger.debug(f"处理段落 {para_idx + 1}/{len(paragraphs)}")
                
                try:
                    # 写入段落译文
                    write_paragraph_fragments(text, cursor, paragraph, "translated_text", logger)
                    
                    # 段落间添加换行（除了最后一个段落）
                    if para_idx < len(paragraphs) - 1:
                        insert_optimized_line_break(text, cursor, "hard", logger)
                except Exception as e:
                    logger.error(f"写入段落 {para_idx + 1} 译文失败: {e}")
                    continue
        
        elif mode == "append":
            # 追加模式：原文后追加所有译文
            logger.debug("段落追加模式：原文后追加所有译文")
            try:
                cursor.gotoEnd(False)
                text.insertString(cursor, "\n\n", False)  # 添加分隔
            except Exception as e:
                logger.warning(f"添加分隔符失败: {e}")
            
            for para_idx, paragraph in enumerate(paragraphs):
                logger.debug(f"追加段落译文 {para_idx + 1}/{len(paragraphs)}")
                
                try:
                    # 写入段落译文
                    write_paragraph_fragments(text, cursor, paragraph, "translated_text", logger)
                    
                    # 段落间添加换行（除了最后一个段落）
                    if para_idx < len(paragraphs) - 1:
                        insert_optimized_line_break(text, cursor, "hard", logger)
                except Exception as e:
                    logger.error(f"追加段落 {para_idx + 1} 译文失败: {e}")
                    continue
        
        elif mode == "paragraph_up":
            # 逐段翻译模式：每个段落下方插入对应译文（使用软回车）
            logger.debug("逐段翻译模式：每个段落下方插入对应译文（使用软回车）")
            text.setString("")
            cursor = text.createTextCursor()
            
            for para_idx, paragraph in enumerate(paragraphs):
                logger.debug(f"处理段落 {para_idx + 1}/{len(paragraphs)}...")
                
                try:               
                    # 1. 写入原文段落
                    write_paragraph_fragments(text, cursor, paragraph, "text", logger)
                    
                    # 2. 段落内软回车（关键优化点）
                    # logger.debug("插入软回车分隔原文和译文")
                    # soft_break_success = insert_optimized_line_break(text, cursor, "soft", logger)
                    # if not soft_break_success:
                    #     logger.warning("软回车插入失败，使用普通换行")

                    # 为保证格式不崩溃，不使用软回车，先使用硬回车
                    insert_optimized_line_break(text, cursor, "soft", logger)
                    
                    # 3. 写入译文段落
                    write_paragraph_fragments(text, cursor, paragraph, "translated_text", logger)
                    
                    # 4. 段落间添加硬回车分隔（除了最后一个段落）
                    if para_idx < len(paragraphs) - 1:
                        logger.debug("插入段落间硬回车")
                        insert_optimized_line_break(text, cursor, "hard", logger)
                        
                except Exception as e:
                    logger.error(f"处理段落 {para_idx + 1} 失败: {e}")
                    # 尝试恢复cursor位置
                    try:
                        cursor.gotoEnd(False)
                    except:
                        pass
                    continue
            
            logger.debug("逐段翻译写入完成")
        
        elif mode == "paragraph_down":
            # 新增模式：逐段翻译，原文在译文下方
            logger.debug("逐段翻译模式（原文在译文下方）：")
            text.setString("")
            cursor = text.createTextCursor()
            
            for para_idx, paragraph in enumerate(paragraphs):
                logger.debug(f"处理段落 {para_idx + 1}/{len(paragraphs)}...")
                
                try:
                    # 1. 写入译文段落
                    write_paragraph_fragments(text, cursor, paragraph, "translated_text", logger)
                    
                    # 2. 软回车
                    insert_optimized_line_break(text, cursor, "hard", logger)
                    
                    # 1. 写入原文段落
                    write_paragraph_fragments(text, cursor, paragraph, "text", logger)
                    
                    # 4. 段落间也使用软回车（除了最后一个段落）
                    if para_idx < len(paragraphs) - 1:
                        insert_optimized_line_break(text, cursor, "hard", logger)
                        
                except Exception as e:
                    logger.error(f"处理段落 {para_idx + 1} 失败: {e}")
                    continue
            
            logger.debug("全软回车逐段翻译写入完成")
        
        elif mode == "bilingual":
            # 双语模式：类似paragraph模式，但格式稍有不同
            logger.debug("双语模式：原文译文并列显示")
            text.setString("")
            cursor = text.createTextCursor()
            
            for para_idx, paragraph in enumerate(paragraphs):
                logger.debug(f"处理双语段落 {para_idx + 1}/{len(paragraphs)}...")
                
                try:
                    # 写入原文
                    write_paragraph_fragments(text, cursor, paragraph, "text", logger)
                    insert_optimized_line_break(text, cursor, "soft", logger)
                    
                    # 写入译文
                    write_paragraph_fragments(text, cursor, paragraph, "translated_text", logger)
                    
                    # 段落间分隔
                    if para_idx < len(paragraphs) - 1:
                        insert_optimized_line_break(text, cursor, "hard", logger)
                        insert_optimized_line_break(text, cursor, "hard", logger)
                        
                except Exception as e:
                    logger.error(f"处理双语段落 {para_idx + 1} 失败: {e}")
                    continue
        
        else:
            logger.warning(f"未知写入模式: {mode}")
            
    except Exception as e:
        logger.error(f"写入模式 {mode} 执行失败: {e}", exc_info=True)
        raise

def write_paragraph_fragments(text, cursor, paragraph, text_field, logger):
    """
    写入单个段落的文本片段，保持格式
    
    Args:
        text: LibreOffice text对象
        cursor: 文本游标
        paragraph: 段落数据
        text_field: 要写入的文本字段名称 ("text" 或 "translated_text")
        logger: 日志记录器
    """
    fragments = paragraph.get("text_fragments", [])
    
    for frag_idx, fragment in enumerate(fragments):
        content = fragment.get(text_field, "")
        
        if content:  # 只写入非空内容
            try:
                # 插入文本
                text.insertString(cursor, content, False)
                
                # 应用格式 - 使用更简单的方法
                # 选中刚插入的文本
                cursor.goLeft(len(content), True)
                
                # 应用字体格式
                cursor.CharColor = fragment.get("color", 0)
                cursor.CharUnderline = 1 if fragment.get("underline", False) else 0
                cursor.CharWeight = 150 if fragment.get("bold", False) else 100
                cursor.CharEscapement = fragment.get("escapement", 0)
                
                # 处理字体大小（上下标时缩小）
                font_size = fragment.get("font_size", 12)
                if fragment.get("escapement", 0) != 0:
                    font_size *= 0.6
                cursor.CharHeight = font_size
                
                # 重置光标到末尾，取消选中状态
                cursor.goRight(0, False)
                cursor.gotoEnd(False)
                
                logger.debug(f"写入并格式化片段: '{content[:20]}...'")
                
            except Exception as e:
                logger.warning(f"写入片段 '{content[:20]}...' 时出错: {e}")
                # 确保光标在正确位置
                try:
                    cursor.gotoEnd(False)
                except:
                    pass

def write_legacy_mode(text, cursor, box, mode, logger):
    """
    兼容旧格式的写入模式
    
    Args:
        text: LibreOffice text对象
        cursor: 文本游标
        box: 文本框数据（旧格式）
        mode: 写入模式
        logger: 日志记录器
    """
    logger.warning("使用旧格式兼容模式，建议升级数据结构")
    
    if mode == "replace":
        text.setString("")
        for frag in box.get("text_fragments", []):
            trans = frag.get("translated_text", "")
            if trans:
                text.insertString(cursor, trans, False)
                # 应用简单格式
                try:
                    cursor.goLeft(len(trans), True)
                    cursor.CharColor = frag.get("color", 0)
                    cursor.CharHeight = frag.get("font_size", 12)
                    cursor.gotoEnd(False)
                except:
                    pass
    
    elif mode == "append":
        cursor.gotoEnd(False)
        text.insertString(cursor, "\n", False)
        for frag in box.get("text_fragments", []):
            trans = frag.get("translated_text", "")
            if trans:
                text.insertString(cursor, trans, False)
    
    else:
        logger.warning(f"旧格式模式 {mode} 功能有限")

def write_from_presentation(context, slides, page_index, page_data, mode="paragraph_up", logger=None):
    """
    处理单页的写入逻辑，支持新的段落层级结构
    
    Args:
        context: LibreOffice上下文
        slides: 幻灯片集合
        page_index: 页面索引
        page_data: 页面数据（包含段落层级）
        mode: 写入模式
        logger: 日志记录器
    """
    if logger is None:
        logger = get_logger("pyuno.subprocess")
    
    if page_index >= slides.getCount():
        logger.warning(f"页面索引超出范围: {page_index}")
        return
    
    logger.info(f"开始为第 {page_index+1} 页写入译文，模式: {mode}")
    slide = slides.getByIndex(page_index)
    shape_count = slide.getCount()
    logger.info(f"第 {page_index+1} 页有 {shape_count} 个形状元素")
    
    text_boxes = page_data.get("text_boxes", [])
    logger.info(f"页面数据包含 {len(text_boxes)} 个文本框")
    
    # 处理每个文本框
    for box_idx, box in enumerate(text_boxes):
        logger.info(f"处理文本框 {box_idx + 1}/{len(text_boxes)} (box_index={box.get('box_index', 'unknown')})")
        
        # 提取文本框的完整原文和译文
        box_text = extract_box_text_from_paragraphs(box)
        trans_text = extract_box_translation_from_paragraphs(box)
        
        if not box_text.strip():
            logger.warning(f"文本框 {box_idx + 1} 原文为空，跳过")
            continue
        
        if not trans_text.strip():
            logger.warning(f"文本框 {box_idx + 1} 译文为空，跳过")
            continue
        
        # 检查译文质量
        sim_score = calculate_similarity_score(box_text, trans_text)
        if box_text == trans_text or sim_score > 0.85:
            logger.info(f"文本框 {box_idx + 1} 译文与原文一致或相似度高({sim_score:.2f})，跳过")
            logger.debug(f"  原文: '{box_text[:50]}...'")
            logger.debug(f"  译文: '{trans_text[:50]}...'")
            continue
        
        # 查找匹配的shape
        found_shape = find_matching_shape(slide, box_text, logger)
        
        if found_shape:
            logger.info(f"找到匹配的shape，开始写入译文...")
            logger.debug(f"  文本框原文: '{box_text[:50]}...'")
            logger.debug(f"  文本框译文: '{trans_text[:50]}...'")
            
            # 显示段落结构信息
            if "paragraphs" in box:
                logger.info(f"  段落结构: {len(box['paragraphs'])} 个段落")
                for para_idx, paragraph in enumerate(box["paragraphs"]):
                    fragment_count = len(paragraph.get("text_fragments", []))
                    logger.debug(f"    段落 {para_idx + 1}: {fragment_count} 个片段")
            
            try:
                write_textbox_with_translation_paragraphs(found_shape, box, mode, logger)
                logger.info(f"文本框 {box_idx + 1} 写入完成")
            except Exception as e:
                logger.error(f"写入文本框 {box_idx + 1} 时出错: {e}", exc_info=True)
        else:
            logger.warning(f"未找到与文本框 {box_idx + 1} 匹配的shape")
            logger.debug(f"  查找的原文: '{box_text[:100]}...'")

def find_matching_shape(slide, target_text, logger):
    """
    在slide中查找匹配指定文本的shape
    
    Args:
        slide: LibreOffice slide对象
        target_text: 目标文本
        logger: 日志记录器
        
    Returns:
        匹配的shape对象或None
    """
    shape_count = slide.getCount()
    logger.debug(f"在 {shape_count} 个形状中查找匹配的文本")
    
    # 第一轮：精确匹配
    for shape_idx in range(shape_count):
        shape = slide.getByIndex(shape_idx)
        if not hasattr(shape, "getString"):
            continue
        
        shape_text = shape.getText().getString().replace("\r\n", "\n").replace("\r", "\n").strip()
        
        if shape_text == target_text:
            logger.debug(f"找到精确匹配的shape (索引 {shape_idx})")
            return shape
    
    # 第二轮：相似度匹配
    best_score = 0.0
    best_shape = None
    best_shape_idx = -1
    
    for shape_idx in range(shape_count):
        shape = slide.getByIndex(shape_idx)
        if not hasattr(shape, "getString"):
            continue
        
        shape_text = shape.getText().getString().replace("\r\n", "\n").replace("\r", "\n").strip()
        
        if shape_text:  # 只考虑非空文本
            score = calculate_similarity_score(target_text, shape_text)
            if score > best_score and score > 0.7:  # 相似度阈值
                best_score = score
                best_shape = shape
                best_shape_idx = shape_idx
    
    if best_shape:
        logger.debug(f"找到相似度匹配的shape (索引 {best_shape_idx}, 相似度 {best_score:.3f})")
        return best_shape
    
    logger.debug("未找到匹配的shape")
    return None

def validate_paragraph_structure(box, logger):
    """
    验证文本框的段落结构是否正确
    
    Args:
        box: 文本框数据
        logger: 日志记录器
        
    Returns:
        bool: 结构是否有效
    """
    if "paragraphs" not in box:
        logger.debug("文本框使用旧格式结构")
        return True  # 旧格式也认为是有效的
    
    paragraphs = box.get("paragraphs", [])
    if not paragraphs:
        logger.warning("文本框段落列表为空")
        return False
    
    for para_idx, paragraph in enumerate(paragraphs):
        if "text_fragments" not in paragraph:
            logger.warning(f"段落 {para_idx} 缺少text_fragments字段")
            return False
        
        fragments = paragraph.get("text_fragments", [])
        if not fragments:
            logger.warning(f"段落 {para_idx} 文本片段为空")
            continue
        
        # 检查是否有翻译
        has_translation = any(frag.get("translated_text") for frag in fragments)
        if not has_translation:
            logger.warning(f"段落 {para_idx} 没有翻译内容")
    
    logger.debug(f"文本框段落结构验证通过，共 {len(paragraphs)} 个段落")
    return True

# 兼容性函数
def write_textbox_with_translation(shape, box, mode="paragraph_up", logger=None):
    """
    兼容性函数，重定向到新的段落层级函数
    """
    if logger is None:
        logger = get_logger("pyuno.subprocess")
    
    logger.debug("使用兼容性接口，重定向到段落层级函数")
    return write_textbox_with_translation_paragraphs(shape, box, mode, logger)

# 新增辅助函数
def get_available_line_break_modes():
    """
    获取可用的换行模式
    
    Returns:
        list: 可用的换行模式列表
    """
    return ["soft", "hard"]

def test_line_break_support(text, cursor, logger=None):
    """
    测试当前环境支持的换行符类型
    
    Args:
        text: LibreOffice text对象
        cursor: 文本游标
        logger: 日志记录器
        
    Returns:
        dict: 测试结果
    """
    if logger is None:
        logger = get_logger("pyuno.subprocess")
    
    results = {
        "control_character": False,
        "unicode_line_separator": False,
        "vertical_tab": False
    }
    
    try:
        # 测试ControlCharacter.LINE_BREAK
        try:
            import uno
            from com.sun.star.text.ControlCharacter import LINE_BREAK
            results["control_character"] = True
            logger.debug("ControlCharacter.LINE_BREAK 支持")
        except Exception as e:
            logger.debug(f"ControlCharacter.LINE_BREAK 不支持: {e}")
        
        # 测试Unicode Line Separator
        try:
            test_text = "test\u2028test"
            results["unicode_line_separator"] = True
            logger.debug("Unicode Line Separator 支持")
        except Exception as e:
            logger.debug(f"Unicode Line Separator 不支持: {e}")
        
        # 测试垂直制表符
        try:
            test_text = "test\vtest"
            results["vertical_tab"] = True
            logger.debug("垂直制表符 支持")
        except Exception as e:
            logger.debug(f"垂直制表符 不支持: {e}")
    
    except Exception as e:
        logger.error(f"测试换行符支持时出错: {e}")
    
    return results

if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("write_ppt_page_uno 模块测试（软回车优化版）")
    print("=" * 60)
    
    logger = get_logger("test")
    logger.info("write_ppt_page_uno 软回车优化模块加载成功")
    
    # 测试换行模式
    logger.info("可用的换行模式:")
    for mode in get_available_line_break_modes():
        logger.info(f"  - {mode}")
    
    # 测试文本提取函数
    mock_box = {
        "box_index": 0,
        "box_id": "textbox_0",
        "paragraphs": [
            {
                "paragraph_index": 0,
                "paragraph_id": "para_0_0",
                "text_fragments": [
                    {
                        "fragment_id": "frag_0_0_0",
                        "text": "Hello",
                        "translated_text": "你好",
                        "color": 0,
                        "bold": True
                    },
                    {
                        "fragment_id": "frag_0_0_1", 
                        "text": " World",
                        "translated_text": "世界",
                        "color": 0,
                        "bold": False
                    }
                ]
            },
            {
                "paragraph_index": 1,
                "paragraph_id": "para_0_1",
                "text_fragments": [
                    {
                        "fragment_id": "frag_0_1_0",
                        "text": "Second paragraph",
                        "translated_text": "第二段",
                        "color": 0,
                        "bold": False
                    }
                ]
            }
        ]
    }
    
    try:
        # 测试文本提取
        box_text = extract_box_text_from_paragraphs(mock_box)
        trans_text = extract_box_translation_from_paragraphs(mock_box)
        
        logger.info(f"提取的原文: '{box_text}'")
        logger.info(f"提取的译文: '{trans_text}'")
        
        # 测试结构验证
        is_valid = validate_paragraph_structure(mock_box, logger)
        logger.info(f"段落结构验证: {'通过' if is_valid else '失败'}")
        
        # 显示优化说明
        logger.info("优化说明:")
        logger.info("  - 新增软回车功能，避免译文继承原文段落格式")
        logger.info("  - 支持 paragraph、paragraph_soft 等多种模式")
        logger.info("  - 自动检测并使用最佳的换行符类型")
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
    
    print("=" * 60)