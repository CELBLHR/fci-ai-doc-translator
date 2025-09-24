#!/usr/bin/env python3
"""
本地PDF处理模块
使用PyMuPDF进行PDF内容提取，不依赖外部服务
"""
import os
import logging
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class LocalPDFProcessor:
    """本地PDF处理器"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix='pdf_processor_')
        logger.info(f"本地PDF处理器初始化，临时目录: {self.temp_dir}")
    
    def process_pdf(self, file_path):
        """处理PDF文件，返回类似MinerU的格式"""
        try:
            logger.info(f"开始处理PDF文件: {file_path}")
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return None
            
            # 生成任务ID
            task_id = f"local_{int(datetime.now().timestamp())}"
            logger.info(f"生成任务ID: {task_id}")
            
            # 提取PDF内容
            content = self._extract_pdf_content(file_path)
            if not content:
                logger.error("PDF内容提取失败")
                return None
            
            # 创建markdown文件
            md_file = self._create_markdown_file(task_id, content)
            if not md_file:
                logger.error("创建markdown文件失败")
                return None
            
            # 创建ZIP文件
            zip_file = self._create_zip_file(task_id, md_file)
            if not zip_file:
                logger.error("创建ZIP文件失败")
                return None
            
            # 返回类似MinerU的格式
            result = {
                'code': 0,
                'msg': 'success',
                'data': {
                    'task_id': task_id,
                    'state': 'done',
                    'full_zip_url': f'file://{zip_file}',
                    'extract_progress': {
                        'extracted_pages': 1,
                        'total_pages': 1
                    }
                }
            }
            
            logger.info(f"PDF处理完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"PDF处理失败: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return None
    
    def _extract_pdf_content(self, file_path):
        """提取PDF内容"""
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(file_path)
            content = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                if text.strip():
                    content.append(f"# 第 {page_num + 1} 页\n\n{text}\n")
            
            doc.close()
            
            if content:
                full_content = "\n".join(content)
                logger.info(f"提取到 {len(content)} 页内容，总长度: {len(full_content)} 字符")
                return full_content
            else:
                logger.warning("PDF中没有提取到文本内容")
                return None
                
        except ImportError:
            logger.error("PyMuPDF未安装，无法提取PDF内容")
            return None
        except Exception as e:
            logger.error(f"PDF内容提取失败: {e}")
            return None
    
    def _create_markdown_file(self, task_id, content):
        """创建markdown文件"""
        try:
            md_filename = f"{task_id}.md"
            md_path = os.path.join(self.temp_dir, md_filename)
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"创建markdown文件: {md_path}")
            return md_path
            
        except Exception as e:
            logger.error(f"创建markdown文件失败: {e}")
            return None
    
    def _create_zip_file(self, task_id, md_file):
        """创建ZIP文件"""
        try:
            zip_filename = f"mineru_result_{task_id}.zip"
            zip_path = os.path.join(self.temp_dir, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(md_file, os.path.basename(md_file))
            
            logger.info(f"创建ZIP文件: {zip_path}")
            return zip_path
            
        except Exception as e:
            logger.error(f"创建ZIP文件失败: {e}")
            return None
    
    def cleanup(self):
        """清理临时文件"""
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"清理临时目录: {self.temp_dir}")
        except Exception as e:
            logger.error(f"清理临时文件失败: {e}")
