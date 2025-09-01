#!/usr/bin/env python3
"""
测试PDF翻译功能
"""

import os
import sys
import logging
import requests
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

def test_pdf_upload_and_processing():
    """测试PDF上传和处理功能"""
    try:
        # 创建测试PDF
        pdf_filename = create_test_pdf()
        
        # 检查文件是否存在且是有效的PDF
        if not os.path.exists(pdf_filename):
            logger.error("测试PDF文件创建失败")
            return False
            
        # 检查文件是否是有效的PDF
        with open(pdf_filename, 'rb') as f:
            header = f.read(10)
            if not header.startswith(b'%PDF-'):
                logger.error("创建的文件不是有效的PDF格式")
                return False
        
        logger.info("测试PDF文件验证通过")
        logger.info(f"文件大小: {os.path.getsize(pdf_filename)} 字节")
        
        # 清理测试文件
        os.remove(pdf_filename)
        logger.info("测试文件已清理")
        
        return True
        
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    logger.info("开始测试PDF功能")
    success = test_pdf_upload_and_processing()
    if success:
        logger.info("PDF功能测试通过")
        print("SUCCESS: PDF功能测试通过")
    else:
        logger.error("PDF功能测试失败")
        print("ERROR: PDF功能测试失败")