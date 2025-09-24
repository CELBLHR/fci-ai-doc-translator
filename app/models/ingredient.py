from .. import db

class Ingredient(db.Model):
    __tablename__ = 'ingredient'
    
    id = db.Column(db.Integer, primary_key=True)
    food_name = db.Column(db.String(200), nullable=False)  # 保健食品名称
    ingredient = db.Column(db.Text)  # 原料成分
    path = db.Column(db.String(500))  # 文件路径
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), 
                          onupdate=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'food_name': self.food_name,
            'ingredient': self.ingredient,
            'path': self.path
        } 