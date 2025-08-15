'''
read_ppt_page_uno.py
读取PPT单页面的文本内容及属性，使用改进后的数据结构，添加paragraph层级
'''
import uno # type: ignore
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from logger_config import get_logger
import math

# 连接到本地运行的LibreOffice（需要先启动监听服务）
def connect_to_libreoffice():
    logger = get_logger("pyuno.subprocess")
    logger.debug("开始连接到LibreOffice...")
    
    try:
        local_ctx = uno.getComponentContext()
        resolver = local_ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local_ctx)
        context = resolver.resolve(
            "uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
        logger.info("成功连接到LibreOffice")
        return context
    except Exception as e:
        logger.error(f"连接LibreOffice失败: {e}", exc_info=True)
        raise

# 提取文本框中每个字符的内容及其字体属性，并按属性分片，同时记录段落分割信息
def extract_text_and_attrs(shape):
    logger = get_logger("pyuno.subprocess")
    logger.debug("开始提取文本框内容和属性...")
    
    text = shape.getText()  # 获取文本对象
    cursor = text.createTextCursor()  # 创建文本游标
    cursor.gotoStart(False)  # 游标移到开头
    content_queue = []  # 存储文本片段
    attr_queue = []     # 存储对应属性
    paragraph_breaks = []  # 存储段落分割位置
    text_str = text.getString()  # 获取全部文本内容
    
    if not text_str:
        logger.debug("文本框为空，跳过处理")
        return [], [], []  # 没有文本直接返回空队列

    logger.debug(f"文本框内容长度: {len(text_str)} 字符")
    last_attrs = None  # 上一个片段的属性
    buffer = ''        # 当前片段内容缓冲
    current_fragment_index = 0  # 当前片段索引
    
    # 遍历每一个字
    for idx, char in enumerate(text_str):
        cursor.gotoStart(False)  # 游标回到开头
        cursor.goRight(idx, False)  # 向右移动到第idx个字符
        cursor.goRight(1, True)     # 选中当前字符
        
        # 提取字体属性
        font_color = cursor.CharColor  # 字体颜色（RGB整数）
        underline = cursor.CharUnderline != 0  # 是否有下划线
        bold = cursor.CharWeight > 100         # 是否加粗
        escapement = cursor.CharEscapement     # 上下标（正数为上标，负数为下标，0为正常）
        font_size = cursor.CharHeight          # 字体大小
        attrs = (font_color, underline, bold, escapement, font_size)
        
        # 检查是否为换行符
        is_line_break = char in ['\n', '\r']
        
        # 判断属性是否与上一个片段一致
        if last_attrs is None:
            last_attrs = attrs
            if not is_line_break:  # 跳过换行符本身
                buffer = char
        elif attrs == last_attrs and not is_line_break:
            buffer += char
        else:
            # 属性变化或遇到换行符，保存上一个片段
            if buffer.strip():  # 只保存非空内容
                content_queue.append(buffer)
                attr_queue.append(last_attrs)
                current_fragment_index = len(content_queue) - 1
            
            # 如果是换行符，记录段落分割位置
            if is_line_break:
                if content_queue:  # 确保有内容才记录分割
                    paragraph_breaks.append(current_fragment_index)
                buffer = ''
                # 换行符后继续使用当前属性
                last_attrs = attrs
            else:
                buffer = char
                last_attrs = attrs
    
    # 保存最后一个片段
    if buffer.strip():
        content_queue.append(buffer)
        attr_queue.append(last_attrs)
    
    # 过滤掉内容为空或全是空格的片段
    filtered_content = []
    filtered_attr = []
    filtered_breaks = []
    
    # 重新映射段落分割位置
    old_to_new_mapping = {}
    new_index = 0
    
    for old_index, (frag, attr) in enumerate(zip(content_queue, attr_queue)):
        if frag.strip():
            filtered_content.append(frag)
            filtered_attr.append(attr)
            old_to_new_mapping[old_index] = new_index
            new_index += 1
    
    # 更新段落分割位置
    for break_pos in paragraph_breaks:
        if break_pos in old_to_new_mapping:
            filtered_breaks.append(old_to_new_mapping[break_pos])
    
    if not filtered_content or not filtered_attr:
        logger.debug("过滤后没有有效文本片段")
        return [], [], []
    
    logger.debug(f"提取到 {len(filtered_content)} 个文本片段，{len(filtered_breaks)} 个段落分割")
    return filtered_content, filtered_attr, filtered_breaks

# 将文本片段和属性转换为新的段落结构数据
def convert_to_structured_data_with_paragraphs(content_queue, attr_queue, paragraph_breaks, box_index):
    """
    将文本片段和属性转换为包含段落层级的结构化数据格式
    """
    logger = get_logger("pyuno.subprocess")
    logger.debug(f"转换文本框 {box_index} 的数据结构（包含段落层级）...")
    
    if not content_queue:
        return []
    
    paragraphs = []
    current_paragraph_fragments = []
    paragraph_index = 0
    
    # 添加一个虚拟的结束位置，确保最后一个段落被处理
    break_positions = set(paragraph_breaks + [len(content_queue) - 1])
    
    for i, (text, attrs) in enumerate(zip(content_queue, attr_queue)):
        color, underline, bold, escapement, font_size = attrs
        
        fragment = {
            "fragment_id": f"frag_{box_index}_{paragraph_index}_{len(current_paragraph_fragments)}",
            "text": text,
            "color": color,
            "underline": underline,
            "bold": bold,
            "escapement": escapement,
            "font_size": font_size
        }
        current_paragraph_fragments.append(fragment)
        
        # 如果当前位置是段落分割点，结束当前段落
        if i in break_positions:
            if current_paragraph_fragments:
                paragraph = {
                    "paragraph_index": paragraph_index,
                    "paragraph_id": f"para_{box_index}_{paragraph_index}",
                    "text_fragments": current_paragraph_fragments
                }
                paragraphs.append(paragraph)
                logger.debug(f"创建段落 {paragraph_index}，包含 {len(current_paragraph_fragments)} 个片段")
                
                paragraph_index += 1
                current_paragraph_fragments = []
    
    # 处理剩余的片段（如果有的话）
    if current_paragraph_fragments:
        paragraph = {
            "paragraph_index": paragraph_index,
            "paragraph_id": f"para_{box_index}_{paragraph_index}",
            "text_fragments": current_paragraph_fragments
        }
        paragraphs.append(paragraph)
        logger.debug(f"创建最后段落 {paragraph_index}，包含 {len(current_paragraph_fragments)} 个片段")
    
    logger.debug(f"文本框 {box_index} 转换为 {len(paragraphs)} 个段落")
    return paragraphs

# 保持向后兼容的旧函数（不包含段落层级）
def convert_to_structured_data(content_queue, attr_queue, box_index, fragment_start_id=0):
    """
    将文本片段和属性转换为结构化的数据格式（旧版本，保持向后兼容）
    """
    logger = get_logger("pyuno.subprocess")
    logger.debug(f"转换文本框 {box_index} 的数据结构（兼容模式）...")
    
    text_fragments = []
    
    for i, (text, attrs) in enumerate(zip(content_queue, attr_queue)):
        color, underline, bold, escapement, font_size = attrs
        
        fragment = {
            "fragment_id": f"frag_{box_index}_{fragment_start_id + i}",
            "text": text,
            "color": color,
            "underline": underline,
            "bold": bold,
            "escapement": escapement,
            "font_size": font_size
        }
        text_fragments.append(fragment)
    
    logger.debug(f"文本框 {box_index} 转换为 {len(text_fragments)} 个结构化片段")
    return text_fragments

# 读取指定幻灯片页的所有文本框内容及属性，返回包含段落层级的改进数据结构
def read_slide_texts_improved(context, ppt_path, page_index=0):
    """
    读取指定页面的文本内容，返回包含段落层级的改进数据结构
    """
    logger = get_logger("pyuno.subprocess")
    logger.info(f"开始读取第 {page_index + 1} 页的文本内容...")
    
    try:
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context)
        file_url = uno.systemPathToFileUrl(os.path.abspath(ppt_path))  # 转为UNO文件URL
        properties = ()
        
        logger.debug(f"打开PPT文件: {file_url}")
        presentation = desktop.loadComponentFromURL(file_url, "_blank", 0, properties)  # 打开PPT
        slides = presentation.getDrawPages()  # 获取所有幻灯片
        
        # 调用新的函数处理页面
        page_data = read_slide_from_presentation(context, slides, page_index)
        
        presentation.close(True)
        return page_data
        
    except Exception as e:
        logger.error(f"读取第 {page_index + 1} 页时出错: {e}", exc_info=True)
        raise

def read_slide_from_presentation(context, slides, page_index=0):
    """
    从已打开的presentation中读取指定页面的文本内容
    这是优化版本，不需要重新打开PPT文件，包含段落层级
    
    Args:
        context: LibreOffice上下文
        slides: 已打开的slides对象
        page_index: 页面索引
        
    Returns:
        dict: 页面数据结构（包含段落层级）
    """
    logger = get_logger("pyuno.subprocess")
    logger.info(f"从已打开的presentation中读取第 {page_index + 1} 页...")
    
    try:
        # 初始化页面数据结构
        page_data = {
            "page_index": page_index,
            "total_boxes": 0,
            "total_paragraphs": 0,
            "text_boxes": []
        }
        
        if 0 <= page_index < slides.getCount():
            slide = slides.getByIndex(page_index)
            box_index = 0
            total_paragraphs = 0
            
            logger.debug(f"第 {page_index + 1} 页包含 {slide.getCount()} 个形状")
            
            for j in range(slide.getCount()):
                shape = slide.getByIndex(j)
                # 检查是否为文本框（有getString方法）
                if hasattr(shape, 'getString'):
                    text = shape.getString()
                    if text.strip():
                        logger.debug(f"处理文本框 {box_index}: 长度 {len(text)} 字符")
                        
                        # 提取文本片段、属性和段落分割信息
                        content_queue, attr_queue, paragraph_breaks = extract_text_and_attrs(shape)
                        
                        if content_queue and attr_queue:
                            # 转换为包含段落的结构化数据
                            paragraphs = convert_to_structured_data_with_paragraphs(
                                content_queue, attr_queue, paragraph_breaks, box_index
                            )
                            
                            # 创建文本框数据
                            text_box = {
                                "box_index": box_index,
                                "box_id": f"textbox_{box_index}",
                                "box_type": "text",
                                "total_paragraphs": len(paragraphs),
                                "paragraphs": paragraphs
                            }
                            
                            page_data["text_boxes"].append(text_box)
                            total_paragraphs += len(paragraphs)
                            box_index += 1
                            
                            # 统计信息
                            total_fragments = sum(len(para["text_fragments"]) for para in paragraphs)
                            logger.debug(f"文本框 {box_index-1}: {len(paragraphs)} 个段落，{total_fragments} 个片段")
                        else:
                            logger.debug(f"文本框 {box_index} 没有有效内容，跳过")
                    else:
                        logger.debug(f"文本框 {box_index} 内容为空，跳过")
                else:
                    logger.debug(f"形状 {j} 不是文本框，跳过")
            
            # 更新总计数
            page_data["total_boxes"] = len(page_data["text_boxes"])
            page_data["total_paragraphs"] = total_paragraphs
            logger.info(f"第 {page_index + 1} 页读取完成，包含 {page_data['total_boxes']} 个文本框，{total_paragraphs} 个段落")
        else:
            logger.warning(f"页面索引 {page_index} 超出范围，总页数: {slides.getCount()}")
        
        return page_data
        
    except Exception as e:
        logger.error(f"读取第 {page_index + 1} 页时出错: {e}", exc_info=True)
        raise

# 保持向后兼容的旧函数
def read_slide_texts(context, ppt_path, page_index=0):
    """
    保持向后兼容的旧函数，返回原有的嵌套结构
    """
    logger = get_logger("pyuno.subprocess")
    logger.debug("使用兼容模式读取页面文本...")
    
    page_data = read_slide_texts_improved(context, ppt_path, page_index)
    
    # 转换为旧格式
    all_content_attrs = []
    slide_content_attrs = []
    
    for text_box in page_data["text_boxes"]:
        # 将段落中的所有片段合并
        all_fragments = []
        for paragraph in text_box["paragraphs"]:
            all_fragments.extend(paragraph["text_fragments"])
        
        content_queue = [frag["text"] for frag in all_fragments]
        attr_queue = [
            (frag["color"], frag["underline"], frag["bold"], 
             frag["escapement"], frag["font_size"]) 
            for frag in all_fragments
        ]
        slide_content_attrs.append((content_queue, attr_queue))
    
    all_content_attrs.append(slide_content_attrs)
    logger.debug("兼容模式转换完成")
    return all_content_attrs

# 主程序入口
def main():
    """
    主程序入口，演示新的段落层级数据结构
    """
    logger = get_logger("pyuno.subprocess")
    logger.info("=" * 60)
    logger.info("启动read_ppt_page_uno演示（包含段落层级）")
    logger.info("=" * 60)
    
    try:
        # 使用新的改进函数
        context = connect_to_libreoffice()
        page_data = read_slide_texts_improved(context, "F:/pptxTest/pyuno/abc.pptx", page_index=0)
        
        logger.info(f"页面 {page_data['page_index']} 包含 {page_data['total_boxes']} 个文本框，{page_data['total_paragraphs']} 个段落")
        logger.info("=" * 60)
        
        for text_box in page_data["text_boxes"]:
            logger.info(f"文本框 {text_box['box_index']} ({text_box['box_id']}):")
            logger.info(f"  包含 {text_box['total_paragraphs']} 个段落")
            
            for paragraph in text_box["paragraphs"]:
                logger.info(f"  段落 {paragraph['paragraph_index']} ({paragraph['paragraph_id']}):")
                logger.info(f"    包含 {len(paragraph['text_fragments'])} 个文本片段")
                
                for fragment in paragraph["text_fragments"]:
                    logger.info(f"      {fragment['fragment_id']}: '{fragment['text']}' "
                              f"(颜色:{fragment['color']}, 加粗:{fragment['bold']}, 字号:{fragment['font_size']})")
            logger.info("")
            
    except Exception as e:
        logger.error(f"演示程序执行失败: {e}", exc_info=True)

def write_to_translate_txt(ppt_path, page_index=0, filename="pyuno/to_translate.txt"):
    """
    将页面文本写入翻译文件，使用新的段落层级数据结构
    """
    logger = get_logger("pyuno.subprocess")
    logger.info(f"将第 {page_index + 1} 页文本写入翻译文件: {filename}")
    
    try:
        context = connect_to_libreoffice()
        page_data = read_slide_texts_improved(context, ppt_path, page_index)
        
        text_queue = []
        for text_box in page_data["text_boxes"]:
            for paragraph in text_box["paragraphs"]:
                for fragment in paragraph["text_fragments"]:
                    text_queue.append(fragment["text"])
        
        text_full = "[block]".join(text_queue)
        
        # 确保目录存在
        file_dir = os.path.dirname(filename)
        if file_dir and not os.path.exists(file_dir):
            os.makedirs(file_dir)
            logger.debug(f"创建目录: {file_dir}")
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(text_full)
        
        logger.info(f"已写入待翻译文本到 {filename}，共 {len(text_queue)} 个片段")
        
    except Exception as e:
        logger.error(f"写入翻译文件失败: {e}", exc_info=True)

if __name__ == "__main__":
    main()
