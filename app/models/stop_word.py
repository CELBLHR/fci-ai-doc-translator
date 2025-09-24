from datetime import datetime
from app import db

class StopWord(db.Model):
    __tablename__ = 'stop_words'

    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('stop_words', lazy=True))

    # 添加复合唯一约束：同一用户不能有重复的停翻词
    __table_args__ = (
        db.UniqueConstraint('word', 'user_id', name='unique_word_per_user'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'word': self.word,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': self.user_id
        } 