import uno # type: ignore
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import os
import json
import argparse
from datetime import datetime
from read_ppt_page_uno import connect_to_libreoffice, read_slide_texts_improved, read_slide_from_presentation
from logger_config import setup_subprocess_logging, get_logger, log_function_call, log_execution_time

def load_entire_ppt(ppt_path, page_indices=None):
    """
    读入整个PPT文件，返回指定页面的内容（包含段落层级）
    Args:
        ppt_path: PPT文件路径
        page_indices: 要处理的页面索引列表，None表示处理所有页面
    """
    start_time = datetime.now()
    log_function_call(get_logger("pyuno.subprocess"), "load_entire_ppt", 
                     ppt_path=ppt_path, page_indices=page_indices)
    
    logger = get_logger("pyuno.subprocess")
    logger.info(f"开始加载PPT文件: {ppt_path}")
    
    try:
        logger.debug("连接到LibreOffice...")
        context = connect_to_libreoffice()
        logger.info("成功连接到LibreOffice")
        
        # 只打开一次PPT文件
        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context)
        file_url = uno.systemPathToFileUrl(ppt_path)
        properties = ()
        
        logger.debug(f"打开PPT文件: {file_url}")
        presentation = desktop.loadComponentFromURL(file_url, "_blank", 0, properties)
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
        
        # 遍历指定页面，使用优化版本
        for page_index in page_indices:
            logger.info(f"正在处理第 {page_index + 1} 页...")
            page_start_time = datetime.now()
            
            # 使用优化版本，直接传递slides对象
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
        log_execution_time(logger, "load_entire_ppt", start_time)
        presentation.close(True)
        return pages_data
        
    except Exception as e:
        logger.error(f"连接LibreOffice时出错: {e}", exc_info=True)
        logger.error("\n请确保LibreOffice正在运行并启用了监听服务。")
        logger.error("启动LibreOffice监听服务的步骤：")
        logger.error("1. 打开LibreOffice")
        logger.error("2. 在终端中运行以下命令启动监听服务：")
        logger.error("   soffice --headless --accept=\"socket,host=localhost,port=2002;urp;StarOffice.ComponentContext\"")
        logger.error("3. 保持该终端窗口打开")
        logger.error("4. 在另一个终端中运行您的Python脚本")
        return []

def get_all_text_fragments(pages_data):
    """
    从所有页面数据中提取所有文本片段（包含段落层级）
    """
    logger = get_logger("pyuno.subprocess")
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
    logger = get_logger("pyuno.subprocess")
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

def main():
    """
    主程序入口
    """
    # 设置子进程日志
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_dir, "logs")
    
    # 确保logs目录存在
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    log_file = os.path.join(logs_dir, "subprocess.log")
    logger = setup_subprocess_logging(log_file)
    
    logger.info("=" * 60)
    logger.info("启动load_ppt子进程（包含段落层级）")
    logger.info("=" * 60)
    
    parser = argparse.ArgumentParser(description='加载PPT文件并提取内容（包含段落层级）')
    parser.add_argument('--input', required=True, help='输入PPT文件路径')
    parser.add_argument('--output', help='输出JSON文件路径')
    parser.add_argument('--pages', nargs='+', type=int, help='指定要处理的页面索引（从0开始）')
    
    args = parser.parse_args()
    
    logger.info("开始加载PPT文件...")
    logger.info(f"输入文件: {args.input}")
    logger.info(f"输出文件: {args.output}")
    logger.info(f"指定页面: {args.pages}")
      
    # 获取项目根目录（load_ppt.py 往上退三层）
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    ppt_path = os.path.abspath(os.path.join(project_root, args.input))
    if not os.path.exists(ppt_path):
        logger.error(f"输入文件不存在: {ppt_path}")
        return
    
    # 处理页面参数
    page_indices = None
    if args.pages:
        page_indices = args.pages
        logger.info(f"指定处理页面: {page_indices}")
    
    pages_data = load_entire_ppt(ppt_path, page_indices)
    
    if not pages_data:
        logger.error("PPT加载失败")
        return
    
    logger.info(f"PPT加载完成！总共处理 {len(pages_data)} 页")
    
    # 计算统计信息
    stats = calculate_statistics(pages_data)
    logger.info(f"统计信息：{stats['total_pages']} 页，{stats['total_boxes']} 个文本框，{stats['total_paragraphs']} 个段落，{stats['total_fragments']} 个文本片段")
    
    # 保存结果到JSON文件
    if args.output:
        logger.info(f"保存结果到JSON文件: {args.output}")
        result = {
            'presentation_path': args.input,
            'statistics': stats,
            'pages': pages_data
        }
        
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(args.output)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                logger.debug(f"创建输出目录: {output_dir}")
            
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"结果已保存到: {args.output}")
        except Exception as e:
            logger.error(f"保存JSON文件失败: {e}", exc_info=True)
    
    # 可选：保存所有段落文本到文件
    # save_all_paragraphs_to_file(pages_data, "all_paragraphs_text.txt")
    
    logger.info("load_ppt子进程执行完成")

def save_all_paragraphs_to_file(pages_data, filename):
    """
    将所有段落文本保存到文件
    """
    logger = get_logger("pyuno.subprocess")
    logger.info(f"保存所有段落文本到文件: {filename}")
    
    try:
        paragraphs = get_all_paragraphs_text(pages_data)
        
        with open(filename, "w", encoding="utf-8") as f:
            for para in paragraphs:
                f.write(f"[页面{para['page_index']+1}][文本框{para['box_index']}][段落{para['paragraph_index']}] {para['text']}\n")
        
        logger.info(f"已保存 {len(paragraphs)} 个段落到 {filename}")
        
    except Exception as e:
        logger.error(f"保存段落文件失败: {e}", exc_info=True)

if __name__ == "__main__":
    main()
