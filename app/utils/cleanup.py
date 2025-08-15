"""
import os
import time
from datetime import datetime, timedelta
import logging
from typing import List, Tuple
from ..models import UploadRecord, db
from flask import current_app

logger = logging.getLogger(__name__)

class FileCleanup:
    """文件清理管理器"""
    
    def __init__(self, max_age_days: int = 7):
        """
        初始化清理管理器
        
        Args:
            max_age_days: 文件保留的最大天数
        """
        self.max_age_days = max_age_days
    
    def get_expired_files(self) -> List[Tuple[str, UploadRecord]]:
        """获取过期文件列表"""
        expired_time = datetime.utcnow() - timedelta(days=self.max_age_days)
        expired_records = UploadRecord.query.filter(
            UploadRecord.upload_time < expired_time,
            UploadRecord.status.in_(['completed', 'failed'])
        ).all()
        
        expired_files = []
        for record in expired_records:
            file_path = os.path.join(record.file_path, record.stored_filename)
            if os.path.exists(file_path):
                expired_files.append((file_path, record))
        
        return expired_files
    
    def cleanup_files(self) -> Tuple[int, int]:
        """
        清理过期文件
        
        Returns:
            (成功清理数量, 失败清理数量)
        """
        success_count = 0
        fail_count = 0
        
        try:
            expired_files = self.get_expired_files()
            
            for file_path, record in expired_files:
                try:
                    # 删除文件
                    os.remove(file_path)
                    
                    # 检查是否有关联的注释文件
                    annotation_path = os.path.join(
                        record.file_path,
                        f"annotation_{record.stored_filename}.json"
                    )
                    if os.path.exists(annotation_path):
                        os.remove(annotation_path)
                    
                    # 删除数据库记录
                    db.session.delete(record)
                    success_count += 1
                    
                    logger.info(f"已清理过期文件: {file_path}")
                except Exception as e:
                    logger.error(f"清理文件失败 {file_path}: {str(e)}")
                    fail_count += 1
            
            # 提交数据库更改
            db.session.commit()
            
            # 清理空的用户目录
            self.cleanup_empty_dirs()
            
            return success_count, fail_count
            
        except Exception as e:
            logger.error(f"文件清理过程出错: {str(e)}")
            db.session.rollback()
            return success_count, fail_count
    
    def cleanup_empty_dirs(self):
        """清理空的用户上传目录"""
        upload_folder = current_app.config['UPLOAD_FOLDER']
        
        try:
            for dir_name in os.listdir(upload_folder):
                if dir_name.startswith('user_'):
                    dir_path = os.path.join(upload_folder, dir_name)
                    if os.path.isdir(dir_path) and not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        logger.info(f"已删除空目录: {dir_path}")
        except Exception as e:
            logger.error(f"清理空目录失败: {str(e)}")

# 创建默认的清理管理器实例
file_cleanup = FileCleanup()
""" 