from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.models.stop_word import StopWord
from app import db

bp = Blueprint('stop_words', __name__)

@bp.route('/api/stop-words', methods=['GET'])
@login_required
def get_stop_words():
    stop_words = StopWord.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        'stop_words': [word.to_dict() for word in stop_words]
    })

@bp.route('/api/stop-words', methods=['POST'])
@login_required
def add_stop_word():
    data = request.get_json()
    word = data.get('word')

    if not word:
        return jsonify({'error': '停翻词不能为空'}), 400

    # 检查是否已存在
    existing_word = StopWord.query.filter_by(word=word, user_id=current_user.id).first()
    if existing_word:
        return jsonify({'error': '该停翻词已存在'}), 400

    new_word = StopWord(word=word, user_id=current_user.id)
    db.session.add(new_word)
    
    try:
        db.session.commit()
        return jsonify(new_word.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '添加失败'}), 500

@bp.route('/api/stop-words/<int:id>', methods=['DELETE'])
@login_required
def delete_stop_word(id):
    word = StopWord.query.filter_by(id=id, user_id=current_user.id).first()
    
    if not word:
        return jsonify({'error': '停翻词不存在'}), 404

    db.session.delete(word)
    
    try:
        db.session.commit()
        return jsonify({'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '删除失败'}), 500

@bp.route('/api/stop-words/stats', methods=['GET'])
@login_required
def get_stats():
    total_stop_words = StopWord.query.filter_by(user_id=current_user.id).count()
    return jsonify({
        'total_stop_words': total_stop_words
    }) 