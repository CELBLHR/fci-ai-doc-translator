"""
文件存储管理器
处理文件存储、目录结构和配额管理
"""
import os
import shutil
from typing import Dict, Set, Optional, Tuple
from datetime import datetime, timedelta
import logging
from werkzeug.utils import secure_filename
import uuid

from flask import current_app
from ..models import User, UploadRecord, db

logger = logging.getLogger(__name__)

class StorageManager:
    """文件存储管理器"""
    
    def __init__(self, user_id: int):
        """
        初始化存储管理器
        
        Args:
            user_id: 用户ID
        """
        self.user_id = user_id
        self.base_path = current_app.config['UPLOAD_FOLDER']
        self.user_path = os.path.join(self.base_path, f"user_{user_id}")
        
        # 确保用户目录结构存在
        self._ensure_user_directories()
    
    def _ensure_user_directories(self) -> None:
        """确保用户的所有必要目录都存在"""
        subdirs = current_app.config['UPLOAD_SUBDIRS']
        for subdir in subdirs.values():
            dir_path = os.path.join(self.user_path, subdir)
            os.makedirs(dir_path, exist_ok=True)
    
    def _get_subdir_path(self, file_type: str) -> str:
        """
        获取指定类型文件的存储目录
        
        Args:
            file_type: 文件类型 ('ppt', 'pdf', 'annotation', 'temp')
            
        Returns:
            目录路径
        """
        subdirs = current_app.config['UPLOAD_SUBDIRS']
        if file_type not in subdirs:
            raise ValueError(f"不支持的文件类型: {file_type}")
        
        return os.path.join(self.user_path, subdirs[file_type])
    
    def _check_file_type(self, filename: str, file_type: str) -> bool:
        """
        检查文件类型是否允许
        
        Args:
            filename: 文件名
            file_type: 文件类型
            
        Returns:
            是否允许
        """
        allowed_extensions = current_app.config['ALLOWED_EXTENSIONS'].get(file_type, set())
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
    
    def _check_quota(self, file_size: int) -> bool:
        """
        检查是否超出存储配额
        
        Args:
            file_size: 要添加的文件大小
            
        Returns:
            是否允许
        """
        quota = current_app.config['USER_STORAGE_QUOTA']
        current_usage = self.get_storage_usage()
        return (current_usage + file_size) <= quota
    
    def get_storage_usage(self) -> int:
        """
        获取当前存储使用量
        
        Returns:
            使用的字节数
        """
        total_size = 0
        for root, _, files in os.walk(self.user_path):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
        return total_size
    
    def store_file(self, file, file_type: str, original_filename: str = None) -> Tuple[str, str]:
        """
        存储文件
        
        Args:
            file: 文件对象
            file_type: 文件类型
            original_filename: 原始文件名
            
        Returns:
            (存储文件名, 存储路径)
        """
        if original_filename is None:
            original_filename = file.filename
            
        # 检查文件类型
        if not self._check_file_type(original_filename, file_type):
            raise ValueError(f"不支持的文件类型: {original_filename}")
        
        # 获取文件大小
        file.seek(0, 2)  # 移动到文件末尾
        file_size = file.tell()
        file.seek(0)  # 重置文件指针
        
        # 检查配额
        if not self._check_quota(file_size):
            raise ValueError("存储空间不足")
        
        # 生成安全的文件名
        filename = secure_filename(original_filename)
        stored_filename = f"{uuid.uuid4().hex}_{filename}"
        
        # 获取存储目录
        store_dir = self._get_subdir_path(file_type)
        file_path = os.path.join(store_dir, stored_filename)
        
        # 保存文件
        file.save(file_path)
        
        # 创建记录
        record = UploadRecord(
            user_id=self.user_id,
            filename=original_filename,
            stored_filename=stored_filename,
            file_path=store_dir,
            file_size=file_size,
            status='pending'
        )
        
        db.session.add(record)
        db.session.commit()
        
        return stored_filename, store_dir
    
    def get_file_path(self, stored_filename: str, file_type: str) -> Optional[str]:
        """
        获取文件完整路径
        
        Args:
            stored_filename: 存储的文件名
            file_type: 文件类型
            
        Returns:
            文件路径或None
        """
        store_dir = self._get_subdir_path(file_type)
        file_path = os.path.join(store_dir, stored_filename)
        return file_path if os.path.exists(file_path) else None
    
    def delete_file(self, stored_filename: str, file_type: str) -> bool:
        """
        删除文件
        
        Args:
            stored_filename: 存储的文件名
            file_type: 文件类型
            
        Returns:
            是否成功
        """
        file_path = self.get_file_path(stored_filename, file_type)
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    
    def cleanup_expired_files(self) -> Tuple[int, int]:
        """
        清理过期文件
        
        Returns:
            (清理成功数量, 失败数量)
        """
        success_count = 0
        fail_count = 0
        
        # 清理临时文件
        temp_expire_time = datetime.now() - timedelta(
            hours=current_app.config['TEMP_FILE_CLEANUP_HOURS']
        )
        
        # 清理正常文件
        expire_time = datetime.now() - timedelta(
            days=current_app.config['FILE_CLEANUP_DAYS']
        )
        
        # 获取过期记录
        expired_records = UploadRecord.query.filter(
            UploadRecord.user_id == self.user_id,
            UploadRecord.upload_time < expire_time,
            UploadRecord.status.in_(['completed', 'failed'])
        ).all()
        
        for record in expired_records:
            try:
                file_path = os.path.join(record.file_path, record.stored_filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    success_count += 1
                
                db.session.delete(record)
                
            except Exception as e:
                logger.error(f"清理文件失败 {file_path}: {str(e)}")
                fail_count += 1
        
        db.session.commit()
        return success_count, fail_count

# 创建存储管理器工厂函数
def create_storage_manager(user_id: int) -> StorageManager:
    """
    创建存储管理器实例
    
    Args:
        user_id: 用户ID
        
    Returns:
        StorageManager实例
    """
    return StorageManager(user_id) 