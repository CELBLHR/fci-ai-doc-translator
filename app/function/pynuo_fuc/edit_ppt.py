import uno  #type: ignore
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import json
import argparse
from logger_config import setup_subprocess_logging, get_logger
from write_ppt_page_uno import write_from_presentation, validate_paragraph_structure

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

def write_entire_ppt(input_ppt, output_ppt, translated_json, mode='paragraph_up'):
    """
    将翻译后的内容写入PPT文件，支持段落层级结构
    
    Args:
        input_ppt: 输入PPT文件路径
        output_ppt: 输出PPT文件路径  
        translated_json: 翻译JSON文件路径
        mode: 写入模式
    """
    logger = get_logger("pyuno.subprocess")
    logger.info(f"开始写入PPT（段落层级支持）: {input_ppt} -> {output_ppt}，模式: {mode}")
    
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
        
        presentation = desktop.loadComponentFromURL(file_url, "_blank", 0, ())
        slides = presentation.getDrawPages()
        logger.info(f"PPT总页数: {slides.getCount()}")
        
        # 3. 读取翻译JSON
        logger.info(f"读取翻译JSON: {translated_json}")
        with open(translated_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 4. 验证JSON结构
        is_valid, structure_type, stats = validate_translated_json_structure(data, logger)
        
        if not is_valid:
            logger.error("JSON结构验证失败，无法继续处理")
            presentation.close(True)
            return
        
        if structure_type == "legacy_only":
            logger.warning("检测到旧格式JSON结构，建议升级到段落层级格式")
        elif structure_type == "mixed":
            logger.warning("检测到混合格式JSON结构，将尽力兼容处理")
        
        logger.info(f"JSON读取完成，包含 {len(data.get('pages', []))} 页数据")
        
        # 5. 逐页处理
        pages = data.get("pages", [])
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
        
        # 6. 保存文件
        file_url_save = uno.systemPathToFileUrl(output_ppt)
        logger.info(f"保存PPT到: {file_url_save}")
        
        presentation.storeToURL(file_url_save, ())
        logger.info(f"已保存到 {output_ppt}")
        
        # 7. 关闭文件
        presentation.close(True)
        
        # 8. 显示处理统计
        logger.info("PPT写入完成统计:")
        logger.info(f"  - 成功处理页数: {processed_pages}")
        logger.info(f"  - 错误页数: {error_pages}")
        logger.info(f"  - 处理成功率: {(processed_pages / len(pages) * 100):.1f}%")
        
        if error_pages > 0:
            logger.warning(f"有 {error_pages} 页处理失败，请检查日志")
        
    except ConnectionError as e:
        logger.error(f"LibreOffice连接错误: {e}")
        logger.error("请确保LibreOffice服务正在运行:")
        logger.error("soffice --headless --accept=\"socket,host=localhost,port=2002;urp;StarOffice.ComponentContext\"")
    except FileNotFoundError as e:
        logger.error(f"文件不存在: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析错误: {e}")
    except Exception as e:
        logger.error(f"写入PPT流程发生异常: {e}", exc_info=True)

def main():
    """主程序入口"""
    # 设置日志
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_dir, "logs")
    
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    log_file = os.path.join(logs_dir, "edit_ppt.log")
    logger = setup_subprocess_logging(log_file)
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='将译文写入PPT并生成新文件（支持段落层级）')
    parser.add_argument('--input', required=True, help='原始PPT文件路径')
    parser.add_argument('--output', required=True, help='输出PPT文件路径')
    parser.add_argument('--json', required=True, help='包含译文的JSON文件路径')
    parser.add_argument('--mode', default='paragraph', 
                       choices=['bilingual', 'replace', 'append', 'paragraph_up', 'paragraph_down'], 
                       help='写入模式')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("edit_ppt子进程启动（段落层级支持）")
    logger.info("=" * 60)
    logger.info(f"参数: input={args.input}, output={args.output}, json={args.json}, mode={args.mode}")
    
    # 路径处理
    try:
        # 获取项目根目录（往上退三层）
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        
        # 处理输入路径
        if os.path.isabs(args.input):
            ppt_path = args.input
        else:
            ppt_path = os.path.abspath(os.path.join(project_root, args.input))
        
        # 处理输出路径
        if os.path.isabs(args.output):
            ppt_output_path = args.output
        else:
            ppt_output_path = os.path.abspath(os.path.join(project_root, args.output))
        
        # JSON文件路径通常是绝对路径
        json_path = args.json
        
        logger.info(f"处理后的路径:")
        logger.info(f"  输入PPT: {ppt_path}")
        logger.info(f"  输出PPT: {ppt_output_path}")
        logger.info(f"  翻译JSON: {json_path}")
        
        # 验证输入文件
        if not os.path.exists(ppt_path):
            logger.error(f"输入PPT文件不存在: {ppt_path}")
            return 1
        
        if not os.path.exists(json_path):
            logger.error(f"翻译JSON文件不存在: {json_path}")
            return 1
        
        # 确保输出目录存在
        output_dir = os.path.dirname(ppt_output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"创建输出目录: {output_dir}")
        
        # 执行PPT写入
        write_entire_ppt(ppt_path, ppt_output_path, json_path, args.mode)
        
        logger.info("=" * 60)
        logger.info("edit_ppt子进程正常结束")
        logger.info("=" * 60)
        
        return 0
        
    except Exception as e:
        logger.error(f"程序执行异常: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
