"""
load_ppt_functions.py
从load_ppt.py提取的核心功能，用于直接调用（非子进程）
"""
import uno # type: ignore
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import os
from datetime import datetime
from read_ppt_page_uno import connect_to_libreoffice, read_slide_texts_improved, read_slide_from_presentation
from logger_config import get_logger, log_function_call, log_execution_time

def load_entire_ppt_direct(ppt_path, page_indices=None):
    """
    直接读入整个PPT文件，返回指定页面的内容（包含段落层级）
    
    Args:
        ppt_path: PPT文件路径（支持PPTX和ODP）
        page_indices: 要处理的页面索引列表（0-based），None表示处理所有页面
        
    Returns:
        dict: PPT数据结构，失败时返回None
    """
    start_time = datetime.now()
    logger = get_logger("pyuno.main")
    
    log_function_call(logger, "load_entire_ppt_direct", 
                     ppt_path=ppt_path, page_indices=page_indices)
    
    logger.info(f"开始直接加载PPT文件: {ppt_path}")
    
    try:
        logger.debug("连接到LibreOffice...")
        context = connect_to_libreoffice()
        logger.info("成功连接到LibreOffice")
        
        # 打开PPT文件
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context)

        # 确保使用绝对路径
        abs_ppt_path = os.path.abspath(ppt_path)
        if not os.path.exists(abs_ppt_path):
            logger.error(f"PPT文件不存在: {abs_ppt_path}")
            return None

        file_url = uno.systemPathToFileUrl(abs_ppt_path)

        # 设置加载属性（关键修复）
        properties = []

        # 隐藏窗口
        hidden_prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        hidden_prop.Name = "Hidden"
        hidden_prop.Value = True
        properties.append(hidden_prop)

        # 只读模式
        readonly_prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        readonly_prop.Name = "ReadOnly"
        readonly_prop.Value = True
        properties.append(readonly_prop)

        # 关键：指定文件格式过滤器
        filter_prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        filter_prop.Name = "FilterName"
        file_ext = os.path.splitext(abs_ppt_path.lower())[1]
        if file_ext == ".odp":
            filter_prop.Value = "impress8"
            logger.info("设置ODP文件过滤器: impress8")
        elif file_ext == ".pptx":
            filter_prop.Value = "Impress MS PowerPoint 2007 XML"
            logger.info("设置PPTX文件过滤器: Impress MS PowerPoint 2007 XML")
        else:
            filter_prop.Value = "impress8"
            logger.warning(f"未知文件格式{file_ext}，使用默认过滤器: impress8")
        properties.append(filter_prop)

        logger.debug(f"打开PPT文件: {file_url}")
        presentation = desktop.loadComponentFromURL(file_url, "_blank", 0, tuple(properties))
        slides = presentation.getDrawPages()
        
        # 获取总页数
        total_slides = slides.getCount()
        logger.info(f"PPT总页数: {total_slides}")
        
        # 确定要处理的页面
        if page_indices is None:
            # 处理所有页面
            page_indices = list(range(total_slides))
            logger.info(f"将处理所有 {total_slides} 页")
        else:
            # 验证页面索引
            valid_indices = [i for i in page_indices if 0 <= i < total_slides]
            if len(valid_indices) != len(page_indices):
                invalid_indices = [i for i in page_indices if i < 0 or i >= total_slides]
                logger.warning(f"无效的页面索引 {invalid_indices} 将被忽略")
            page_indices = valid_indices
            logger.info(f"将处理指定页面: {page_indices}")
        
        # 存储指定页面的内容
        pages_data = []
        total_boxes = 0
        total_paragraphs = 0
        
        # 遍历指定页面
        for page_index in page_indices:
            logger.info(f"正在处理第 {page_index + 1} 页...")
            page_start_time = datetime.now()
            
            # 使用现有的读取函数
            page_data = read_slide_from_presentation(context, slides, page_index=page_index)
            pages_data.append(page_data)
            
            # 统计信息
            page_boxes = page_data["total_boxes"]
            page_paragraphs = page_data["total_paragraphs"]
            total_boxes += page_boxes
            total_paragraphs += page_paragraphs
            
            # 计算总文本片段数
            total_fragments_in_page = sum(
                len(paragraph["text_fragments"]) 
                for text_box in page_data["text_boxes"] 
                for paragraph in text_box["paragraphs"]
            )
            
            logger.info(f"第 {page_index + 1} 页包含 {page_boxes} 个文本框，{page_paragraphs} 个段落，{total_fragments_in_page} 个文本片段")
            
            # 记录页面处理时间
            log_execution_time(logger, f"处理第{page_index + 1}页", page_start_time)
            
            # 可选：显示当前页的详细内容
            if page_data["text_boxes"]:
                logger.debug(f"{'文本框':<10} | {'段落数':<6} | {'片段数':<6} | {'内容预览'}")
                logger.debug('-'*60)
                for text_box in page_data["text_boxes"]:
                    total_fragments_in_box = sum(len(para["text_fragments"]) for para in text_box["paragraphs"])
                    # 获取前几个片段的文本作为预览
                    preview_texts = []
                    for paragraph in text_box["paragraphs"]:
                        for fragment in paragraph["text_fragments"]:
                            preview_texts.append(fragment["text"])
                            if len(preview_texts) >= 3:  # 只显示前3个片段
                                break
                        if len(preview_texts) >= 3:
                            break
                    preview = ", ".join(preview_texts)
                    if len(preview) > 30:
                        preview = preview[:30] + "..."
                    
                    logger.debug(f"{text_box['box_id']:<10} | {text_box['total_paragraphs']:<6} | {total_fragments_in_box:<6} | {preview}")
        
        # 计算总的文本片段数
        total_fragments = sum(
            len(paragraph["text_fragments"]) 
            for page_data in pages_data 
            for text_box in page_data["text_boxes"] 
            for paragraph in text_box["paragraphs"]
        )
        
        logger.info(f"处理完成：共 {len(pages_data)} 页，{total_boxes} 个文本框，{total_paragraphs} 个段落，{total_fragments} 个文本片段")
        log_execution_time(logger, "load_entire_ppt_direct", start_time)
        
        # 关闭文档
        presentation.close(True)
        
        # 构建返回数据结构
        result = {
            'presentation_path': ppt_path,
            'statistics': {
                'total_pages': len(pages_data),
                'total_boxes': total_boxes,
                'total_paragraphs': total_paragraphs,
                'total_fragments': total_fragments
            },
            'pages': pages_data
        }
        
        return result
        
    except Exception as e:
        logger.error(f"直接加载PPT时出错: {e}", exc_info=True)
        logger.error("\n请确保LibreOffice正在运行并启用了监听服务。")
        logger.error("启动LibreOffice监听服务的命令：")
        logger.error("soffice --headless --accept=\"socket,host=localhost,port=2002;urp;StarOffice.ComponentContext\"")
        return None

def get_all_text_fragments(pages_data):
    """
    从所有页面数据中提取所有文本片段（包含段落层级）
    """
    logger = get_logger("pyuno.main")
    logger.debug("提取所有文本片段...")
    
    all_fragments = []
    for page_data in pages_data:
        for text_box in page_data["text_boxes"]:
            for paragraph in text_box["paragraphs"]:
                for fragment in paragraph["text_fragments"]:
                    all_fragments.append(fragment["text"])
    
    logger.debug(f"总共提取了 {len(all_fragments)} 个文本片段")
    return all_fragments

def get_all_paragraphs_text(pages_data):
    """
    从所有页面数据中提取所有段落的完整文本
    """
    logger = get_logger("pyuno.main")
    logger.debug("提取所有段落文本...")
    
    all_paragraphs = []
    for page_data in pages_data:
        for text_box in page_data["text_boxes"]:
            for paragraph in text_box["paragraphs"]:
                paragraph_text = "".join([fragment["text"] for fragment in paragraph["text_fragments"]])
                all_paragraphs.append({
                    "page_index": page_data["page_index"],
                    "box_index": text_box["box_index"],
                    "paragraph_index": paragraph["paragraph_index"],
                    "paragraph_id": paragraph["paragraph_id"],
                    "text": paragraph_text
                })
    
    logger.debug(f"总共提取了 {len(all_paragraphs)} 个段落")
    return all_paragraphs

def calculate_statistics(pages_data):
    """
    计算PPT统计信息
    """
    total_pages = len(pages_data)
    total_boxes = sum(page["total_boxes"] for page in pages_data)
    total_paragraphs = sum(page["total_paragraphs"] for page in pages_data)
    total_fragments = sum(
        len(paragraph["text_fragments"]) 
        for page_data in pages_data 
        for text_box in page_data["text_boxes"] 
        for paragraph in text_box["paragraphs"]
    )
    
    return {
        "total_pages": total_pages,
        "total_boxes": total_boxes,
        "total_paragraphs": total_paragraphs,
        "total_fragments": total_fragments
    }