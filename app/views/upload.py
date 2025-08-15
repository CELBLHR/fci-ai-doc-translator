"""
文件上传视图
"""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from ..utils.storage_manager import create_storage_manager
from ..models import UploadRecord, db

bp = Blueprint('upload', __name__)

@bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """
    文件上传接口
    
    请求参数:
    - file: 文件对象
    - file_type: 文件类型 (ppt, pdf, annotation, temp)
    
    返回:
    {
        'code': 0,  # 0成功，非0失败
        'message': '上传成功',
        'data': {
            'filename': '原始文件名',
            'stored_filename': '存储的文件名',
            'file_path': '存储路径',
            'file_size': 文件大小
        }
    }
    """
    try:
        # 检查文件是否存在
        if 'file' not in request.files:
            return jsonify({
                'code': 1,
                'message': '没有上传文件'
            }), 400
            
        file = request.files['file']
        if not file.filename:
            return jsonify({
                'code': 2,
                'message': '文件名为空'
            }), 400
            
        # 检查文件类型
        file_type = request.form.get('file_type')
        if not file_type:
            return jsonify({
                'code': 3,
                'message': '未指定文件类型'
            }), 400
            
        # 创建存储管理器
        storage = create_storage_manager(current_user.id)
        
        # 存储文件
        stored_filename, store_dir = storage.store_file(file, file_type)
        
        # 获取记录
        record = UploadRecord.query.filter_by(
            user_id=current_user.id,
            stored_filename=stored_filename
        ).first()
        
        if not record:
            return jsonify({
                'code': 4,
                'message': '文件上传失败'
            }), 500
            
        # 更新状态
        record.status = 'completed'
        db.session.commit()
        
        return jsonify({
            'code': 0,
            'message': '上传成功',
            'data': record.to_dict()
        })
        
    except ValueError as e:
        return jsonify({
            'code': 5,
            'message': str(e)
        }), 400
        
    except Exception as e:
        current_app.logger.error(f"文件上传失败: {str(e)}")
        return jsonify({
            'code': 6,
            'message': '服务器错误'
        }), 500

@bp.route('/files', methods=['GET'])
@login_required
def get_user_files():
    """
    获取用户文件列表
    
    请求参数:
    - file_type: 文件类型 (可选)
    - status: 状态 (可选)
    - page: 页码 (可选，默认1)
    - per_page: 每页数量 (可选，默认20)
    
    返回:
    {
        'code': 0,
        'message': '获取成功',
        'data': {
            'total': 总数,
            'items': [
                {
                    'id': ID,
                    'filename': '文件名',
                    ...
                }
            ]
        }
    }
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        file_type = request.args.get('file_type')
        status = request.args.get('status')
        
        # 构建查询
        query = UploadRecord.query.filter_by(user_id=current_user.id)
        
        if file_type:
            query = query.filter(UploadRecord.file_path.like(f"%/{file_type}/%"))
            
        if status:
            query = query.filter_by(status=status)
            
        # 分页
        pagination = query.order_by(UploadRecord.upload_time.desc()).paginate(
            page=page,
            per_page=per_page
        )
        
        return jsonify({
            'code': 0,
            'message': '获取成功',
            'data': {
                'total': pagination.total,
                'items': [item.to_dict() for item in pagination.items]
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"获取文件列表失败: {str(e)}")
        return jsonify({
            'code': 1,
            'message': '服务器错误'
        }), 500

@bp.route('/files/<int:file_id>', methods=['DELETE'])
@login_required
def delete_file(file_id):
    """
    删除文件
    
    参数:
    - file_id: 文件ID
    
    返回:
    {
        'code': 0,
        'message': '删除成功'
    }
    """
    try:
        # 获取记录
        record = UploadRecord.query.filter_by(
            id=file_id,
            user_id=current_user.id
        ).first()
        
        if not record:
            return jsonify({
                'code': 1,
                'message': '文件不存在'
            }), 404
            
        # 获取文件类型
        file_type = record.file_path.split('/')[-2]  # 从路径中提取文件类型
        
        # 创建存储管理器
        storage = create_storage_manager(current_user.id)
        
        # 删除文件
        if storage.delete_file(record.stored_filename, file_type):
            # 删除记录
            db.session.delete(record)
            db.session.commit()
            
            return jsonify({
                'code': 0,
                'message': '删除成功'
            })
        else:
            return jsonify({
                'code': 2,
                'message': '文件删除失败'
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"删除文件失败: {str(e)}")
        return jsonify({
            'code': 3,
            'message': '服务器错误'
        }), 500

@bp.route('/storage/usage', methods=['GET'])
@login_required
def get_storage_usage():
    """
    获取存储使用情况
    
    返回:
    {
        'code': 0,
        'message': '获取成功',
        'data': {
            'usage': 使用量(字节),
            'quota': 配额(字节),
            'percentage': 使用百分比
        }
    }
    """
    try:
        storage = create_storage_manager(current_user.id)
        usage = storage.get_storage_usage()
        quota = current_app.config['USER_STORAGE_QUOTA']
        
        return jsonify({
            'code': 0,
            'message': '获取成功',
            'data': {
                'usage': usage,
                'quota': quota,
                'percentage': round(usage / quota * 100, 2)
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"获取存储使用情况失败: {str(e)}")
        return jsonify({
            'code': 1,
            'message': '服务器错误'
        }), 500 