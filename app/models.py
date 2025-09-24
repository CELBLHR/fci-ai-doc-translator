from datetime import datetime
import pytz

from app import db


class UploadRecord(db.Model):
    __tablename__ = 'upload_records'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer)
    upload_time = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))
    status = db.Column(db.String(20), default='pending')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    user = db.relationship('User', backref=db.backref('upload_records', lazy=True))
    
    def __repr__(self):
        return f'<UploadRecord {self.filename}>' 