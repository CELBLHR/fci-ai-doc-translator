"""
edit_ppt_functions.py
从edit_ppt.py提取的核心功能，用于直接调用（非子进程）
"""
import uno  #type: ignore
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from logger_config import get_logger, log_function_call, log_execution_time
from write_ppt_page_uno import write_from_presentation, validate_paragraph_structure
from datetime import datetime

def connect_to_libreoffice():
    """连接本地soffice服务"""
    try:
        localContext = uno.getComponentContext()
        resolver = localContext.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", localContext)
        context = resolver.resolve(
            "uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
        return context
    except Exception as e:
        raise ConnectionError(f"无法连接到LibreOffice服务: {e}")

def validate_translated_json_structure(data, logger):
    """
    验证翻译后的JSON数据结构是否支持段落层级
    
    Args:
        data: JSON数据
        logger: 日志记录器
        
    Returns:
        tuple: (is_valid, structure_type, statistics)
    """
    logger.info("验证翻译JSON数据结构...")
    
    try:
        # 基本结构检查
        if not isinstance(data, dict):
            logger.error("JSON数据不是字典格式")
            return False, "invalid", {}
        
        pages = data.get("pages", [])
        if not isinstance(pages, list):
            logger.error("pages字段不是列表格式")
            return False, "invalid", {}
        
        # 统计信息
        stats = {
            "total_pages": len(pages),
            "total_text_boxes": 0,
            "total_paragraphs": 0,
            "total_fragments": 0,
            "paragraph_structure_pages": 0,
            "legacy_structure_pages": 0
        }
        
        structure_type = "unknown"
        
        for page_idx, page in enumerate(pages):
            text_boxes = page.get("text_boxes", [])
            stats["total_text_boxes"] += len(text_boxes)
            
            page_has_paragraphs = False
            page_has_legacy = False
            
            for box in text_boxes:
                # 检查是否有段落结构
                if "paragraphs" in box:
                    page_has_paragraphs = True
                    paragraphs = box.get("paragraphs", [])
                    stats["total_paragraphs"] += len(paragraphs)
                    
                    for paragraph in paragraphs:
                        fragments = paragraph.get("text_fragments", [])
                        stats["total_fragments"] += len(fragments)
                        
                        # 验证每个段落的结构
                        if not validate_paragraph_structure({"paragraphs": [paragraph]}, logger):
                            logger.warning(f"页面 {page_idx + 1} 文本框 {box.get('box_index', '?')} 段落结构验证失败")
                
                elif "text_fragments" in box:
                    page_has_legacy = True
                    fragments = box.get("text_fragments", [])
                    stats["total_fragments"] += len(fragments)
            
            if page_has_paragraphs:
                stats["paragraph_structure_pages"] += 1
            if page_has_legacy:
                stats["legacy_structure_pages"] += 1
        
        # 确定结构类型
        if stats["paragraph_structure_pages"] > 0 and stats["legacy_structure_pages"] == 0:
            structure_type = "paragraph_only"
        elif stats["paragraph_structure_pages"] == 0 and stats["legacy_structure_pages"] > 0:
            structure_type = "legacy_only"
        elif stats["paragraph_structure_pages"] > 0 and stats["legacy_structure_pages"] > 0:
            structure_type = "mixed"
        else:
            structure_type = "empty"
        
        logger.info("JSON结构验证完成:")
        logger.info(f"  - 结构类型: {structure_type}")
        logger.info(f"  - 总页数: {stats['total_pages']}")
        logger.info(f"  - 总文本框数: {stats['total_text_boxes']}")
        logger.info(f"  - 总段落数: {stats['total_paragraphs']}")
        logger.info(f"  - 总文本片段数: {stats['total_fragments']}")
        logger.info(f"  - 段落结构页数: {stats['paragraph_structure_pages']}")
        logger.info(f"  - 旧结构页数: {stats['legacy_structure_pages']}")
        
        return True, structure_type, stats
        
    except Exception as e:
        logger.error(f"验证JSON结构时出错: {e}", exc_info=True)
        return False, "error", {}

def write_entire_ppt_direct(input_ppt, output_ppt, translated_data, mode='paragraph_up'):
    """
    直接将翻译后的内容写入PPT文件，支持段落层级结构
    
    Args:
        input_ppt: 输入PPT文件路径
        output_ppt: 输出PPT文件路径  
        translated_data: 翻译数据字典（而不是JSON文件路径）
        mode: 写入模式
        
    Returns:
        bool: 写入是否成功
    """
    start_time = datetime.now()
    logger = get_logger("pyuno.main")
    
    log_function_call(logger, "write_entire_ppt_direct", 
                     input_ppt=input_ppt, output_ppt=output_ppt, mode=mode)
    
    logger.info(f"开始直接写入PPT（段落层级支持）: {input_ppt} -> {output_ppt}，模式: {mode}")
    
    try:
        # 1. 连接LibreOffice服务
        logger.info("连接LibreOffice服务...")
        context = connect_to_libreoffice()
        logger.info("已连接到LibreOffice服务")
        
        # 2. 打开PPT文件
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context)
        file_url = uno.systemPathToFileUrl(input_ppt)
        logger.info(f"打开PPT文件: {file_url}")
        
                # 设置加载属性（添加过滤器）
        abs_input_ppt = os.path.abspath(input_ppt)
        file_url = uno.systemPathToFileUrl(abs_input_ppt)

        load_props = []

        hidden_prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        hidden_prop.Name = "Hidden"
        hidden_prop.Value = True
        load_props.append(hidden_prop)

        # 指定文件过滤器
        filter_prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        filter_prop.Name = "FilterName"
        filter_prop.Value = "impress8"  # 因为我们处理的是ODP文件
        load_props.append(filter_prop)

        presentation = desktop.loadComponentFromURL(file_url, "_blank", 0, tuple(load_props))
        slides = presentation.getDrawPages()
        logger.info(f"PPT总页数: {slides.getCount()}")
        
        # 3. 验证翻译数据结构
        logger.info(f"验证翻译数据结构...")
        is_valid, structure_type, stats = validate_translated_json_structure(translated_data, logger)
        
        if not is_valid:
            logger.error("翻译数据结构验证失败，无法继续处理")
            presentation.close(True)
            return False
        
        if structure_type == "legacy_only":
            logger.warning("检测到旧格式数据结构，建议升级到段落层级格式")
        elif structure_type == "mixed":
            logger.warning("检测到混合格式数据结构，将尽力兼容处理")
        
        logger.info(f"翻译数据包含 {len(translated_data.get('pages', []))} 页数据")
        
        # 4. 逐页处理
        pages = translated_data.get("pages", [])
        processed_pages = 0
        error_pages = 0
        
        for page in pages:
            page_idx = page.get("page_index", -1)
            
            if page_idx < 0 or page_idx >= slides.getCount():
                logger.warning(f"页面索引 {page_idx} 无效，跳过")
                error_pages += 1
                continue
            
            logger.info(f"开始处理第 {page_idx+1} 页...")
            
            try:
                # 显示页面统计信息
                text_boxes = page.get("text_boxes", [])
                if text_boxes:
                    total_paragraphs = 0
                    total_fragments = 0
                    
                    for box in text_boxes:
                        if "paragraphs" in box:
                            paragraphs = box.get("paragraphs", [])
                            total_paragraphs += len(paragraphs)
                            for paragraph in paragraphs:
                                total_fragments += len(paragraph.get("text_fragments", []))
                        else:
                            total_fragments += len(box.get("text_fragments", []))
                    
                    logger.info(f"  第 {page_idx+1} 页包含 {len(text_boxes)} 个文本框，{total_paragraphs} 个段落，{total_fragments} 个文本片段")
                else:
                    logger.info(f"  第 {page_idx+1} 页没有文本框")
                
                # 调用写入函数
                write_from_presentation(
                    context=context,
                    slides=slides,
                    page_index=page_idx,
                    page_data=page,
                    mode=mode,
                    logger=logger
                )
                
                processed_pages += 1
                logger.info(f"第 {page_idx+1} 页处理完成")
                
            except Exception as e:
                logger.error(f"处理第 {page_idx+1} 页时出错: {e}", exc_info=True)
                error_pages += 1
        
        # 5. 保存文件
        # 确保使用绝对路径
        abs_output_ppt = os.path.abspath(output_ppt)

        # 确保输出目录存在
        output_dir = os.path.dirname(abs_output_ppt)
        os.makedirs(output_dir, exist_ok=True)

        file_url_save = uno.systemPathToFileUrl(abs_output_ppt)
        logger.info(f"保存PPT到: {file_url_save}")

        # 设置保存属性（关键修复）
        save_props = []

        # 指定ODP格式过滤器
        filter_prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        filter_prop.Name = "FilterName"
        filter_prop.Value = "impress8"  # ODP格式
        save_props.append(filter_prop)

        # 允许覆盖现有文件
        overwrite_prop = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
        overwrite_prop.Name = "Overwrite"
        overwrite_prop.Value = True
        save_props.append(overwrite_prop)

        # 保存文件（使用正确的参数）
        presentation.storeToURL(file_url_save, tuple(save_props))
        logger.info(f"已保存到 {abs_output_ppt}")
        
        # 6. 关闭文件
        presentation.close(True)
        
        # 7. 显示处理统计
        logger.info("PPT写入完成统计:")
        logger.info(f"  - 成功处理页数: {processed_pages}")
        logger.info(f"  - 错误页数: {error_pages}")
        logger.info(f"  - 处理成功率: {(processed_pages / len(pages) * 100):.1f}%")
        
        if error_pages > 0:
            logger.warning(f"有 {error_pages} 页处理失败，请检查日志")
        
        log_execution_time(logger, "write_entire_ppt_direct", start_time)
        
        return processed_pages > 0  # 只要有页面成功处理就算成功
        
    except ConnectionError as e:
        logger.error(f"LibreOffice连接错误: {e}")
        logger.error("请确保LibreOffice服务正在运行:")
        logger.error("soffice --headless --accept=\"socket,host=localhost,port=2002;urp;StarOffice.ComponentContext\"")
        return False
    except FileNotFoundError as e:
        logger.error(f"文件不存在: {e}")
        return False
    except Exception as e:
        logger.error(f"直接写入PPT流程发生异常: {e}", exc_info=True)
        return False