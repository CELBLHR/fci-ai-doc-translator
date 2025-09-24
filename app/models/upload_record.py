"""
文件上传记录模型
"""
from datetime import datetime
from app import db
from app.utils.timezone_helper import now_with_timezone, datetime_to_isoformat, format_datetime

class UploadRecord(db.Model):
    """文件上传记录"""
    __tablename__ = 'upload_records'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)  # 原始文件名
    stored_filename = db.Column(db.String(255), nullable=False)  # 存储的文件名
    file_path = db.Column(db.String(255), nullable=False)  # 存储路径
    file_size = db.Column(db.Integer, nullable=False)  # 文件大小(字节)
    upload_time = db.Column(db.DateTime(timezone=True), default=now_with_timezone)  # 上传时间
    status = db.Column(db.String(20), default='pending')  # 状态: pending, completed, failed
    error_message = db.Column(db.String(255))  # 错误信息
    # 注意：以下字段在旧版本数据库中可能不存在
    # file_type = db.Column(db.String(50))  # 文件类型: pdf_translation, ppt_translation等
    # original_filename = db.Column(db.String(255))  # 原始上传文件名

    def __repr__(self):
        return f'<UploadRecord {self.filename}>'

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'filename': self.filename,
            'stored_filename': self.stored_filename,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'upload_time': format_datetime(self.upload_time),
            'status': self.status,
            'error_message': self.error_message
            # 注意：以下字段在旧版本数据库中可能不存在
            # 'file_type': self.file_type,
            # 'original_filename': self.original_filename
        }