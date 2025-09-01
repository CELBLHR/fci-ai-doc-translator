#!/usr/bin/env python3
"""
测试MinerU API文件上传功能
"""

import os
import sys
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_mineru_upload():
    """测试MinerU文件上传功能"""
    try:
        # 导入必要的模块
        from app.function.image_ocr.ocr_api import MinerUAPI
        
        # 初始化MinerU API
        logger.info("初始化MinerU API")
        mineru_api = MinerUAPI()
        logger.info("MinerU API初始化成功")
        
        # 创建一个测试PDF文件
        test_pdf_path = "test_upload.pdf"
        logger.info(f"创建测试PDF文件: {test_pdf_path}")
        
        # 创建一个简单的PDF文件用于测试
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        c = canvas.Canvas(test_pdf_path, pagesize=letter)
        c.setFont("Helvetica", 12)
        c.drawString(100, 750, "这是一个测试PDF文件")
        c.drawString(100, 730, "用于测试MinerU API文件上传功能")
        c.drawString(100, 710, "如果上传成功，MinerU应该能正确识别此内容")
        c.save()
        
        logger.info("测试PDF文件创建完成")
        logger.info(f"文件大小: {os.path.getsize(test_pdf_path)} 字节")
        
        # 测试上传文件
        logger.info("开始测试文件上传")
        uploaded_url = mineru_api.upload_file(test_pdf_path)
        
        if uploaded_url:
            logger.info(f"文件上传成功: {uploaded_url}")
            print(f"SUCCESS: 文件上传成功，URL: {uploaded_url}")
            return True
        else:
            logger.error("文件上传失败")
            print("ERROR: 文件上传失败")
            return False
            
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        print(f"ERROR: 测试过程中出错: {e}")
        return False
    finally:
        # 清理测试文件
        if os.path.exists("test_upload.pdf"):
            os.remove("test_upload.pdf")
            logger.info("测试文件已清理")

if __name__ == "__main__":
    test_mineru_upload()