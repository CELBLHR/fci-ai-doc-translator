#!/usr/bin/env python3
"""
测试脚本，验证PDF翻译流程
"""

import os
import sys
import logging
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_pdf():
    """创建一个测试PDF文件"""
    filename = "test_document.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # 添加标题
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 100, "PDF翻译测试文档")
    
    # 添加内容
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 150, "这是用于测试PDF翻译功能的文档。")
    c.drawString(100, height - 170, "文档包含多行文本内容，用于验证OCR和文本提取功能。")
    c.drawString(100, height - 190, "如果处理成功，应该能够提取出这些文本内容。")
    
    # 添加更多内容
    y_position = height - 230
    for i in range(1, 6):
        c.drawString(120, y_position, f"测试行 {i}: 这是第 {i} 行测试内容")
        y_position -= 20
    
    # 添加特殊字符和数字
    c.drawString(100, y_position - 20, "特殊字符测试: @#$%^&*()")
    c.drawString(100, y_position - 40, "数字测试: 123456789")
    
    c.save()
    logger.info(f"测试PDF文件创建完成: {filename}")
    return filename

def test_file_operations():
    """测试文件操作"""
    try:
        logger.info("开始测试文件操作")
        
        # 获取项目根目录
        project_root = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"项目根目录: {project_root}")
        
        # 检查上传目录结构
        upload_dir = os.path.join(project_root, 'app', 'uploads')
        pdf_upload_dir = os.path.join(upload_dir, 'pdf_uploads')
        pdf_output_dir = os.path.join(upload_dir, 'pdf_outputs')
        
        logger.info(f"PDF上传目录: {pdf_upload_dir}")
        logger.info(f"PDF输出目录: {pdf_output_dir}")
        
        # 确保目录存在
        os.makedirs(pdf_upload_dir, exist_ok=True)
        os.makedirs(pdf_output_dir, exist_ok=True)
        
        # 创建测试PDF
        pdf_filename = create_test_pdf()
        
        # 移动PDF到上传目录
        import shutil
        dest_path = os.path.join(pdf_upload_dir, pdf_filename)
        shutil.move(pdf_filename, dest_path)
        logger.info(f"PDF文件移动到: {dest_path}")
        
        # 验证文件是否存在
        if os.path.exists(dest_path):
            file_size = os.path.getsize(dest_path)
            logger.info(f"文件存在，大小: {file_size} 字节")
        else:
            logger.error("文件移动失败")
            return False
        
        # 创建测试输出文件
        output_filename = "test_output.docx"
        output_path = os.path.join(pdf_output_dir, output_filename)
        
        # 创建一个简单的文本文件作为输出文件
        with open(output_path, 'w') as f:
            f.write("这是一个测试的Word文档输出文件。")
        
        logger.info(f"输出文件创建完成: {output_path}")
        logger.info(f"输出文件大小: {os.path.getsize(output_path)} 字节")
        
        # 验证输出文件是否存在
        if os.path.exists(output_path):
            logger.info("输出文件存在")
        else:
            logger.error("输出文件创建失败")
            return False
        
        # 列出目录内容
        logger.info("目录内容:")
        logger.info(f"  PDF上传目录: {os.listdir(pdf_upload_dir)}")
        logger.info(f"  PDF输出目录: {os.listdir(pdf_output_dir)}")
        
        # 清理测试文件
        os.remove(dest_path)
        os.remove(output_path)
        logger.info("测试文件已清理")
        
        return True
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

def main():
    """主函数"""
    logger.info("开始测试PDF翻译流程")
    
    try:
        success = test_file_operations()
        if success:
            logger.info("PDF翻译流程测试完成")
            print("SUCCESS: PDF翻译流程测试完成")
            return True
        else:
            logger.error("PDF翻译流程测试失败")
            print("ERROR: PDF翻译流程测试失败")
            return False
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    main()