import time
import json

import pytz


from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory, \
    jsonify, session, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.exc import SQLAlchemyError

from config import data_file
# from ..Ingredient_Search.Flask_app import search, download_files
from ..function.adjust_text_size import set_textbox_autofit
from ..function.ppt_translate import process_presentation, process_presentation_add_annotations
from config import base_model_file
from ..models import User, UploadRecord, Translation, StopWord
from ..services.sso_service import get_sso_service
from .. import db
import os
import uuid
import re

from ..utils.task_queue import translation_queue as old_translation_queue
from ..function.ppt_translate_async import process_presentation as process_presentation_async
from ..function.ppt_translate_async import process_presentation_add_annotations as process_presentation_add_annotations_async
from ..utils.enhanced_task_queue import EnhancedTranslationQueue, TranslationTask, translation_queue
from ..utils.thread_pool_executor import thread_pool, TaskType
import logging
import threading
from datetime import datetime
from app.utils.timezone_helper import format_datetime, datetime_to_isoformat

# from ..utils.Tokenization import Tokenizer
# from ...train import train_model
# sys.stdout.reconfigure(encoding='utf-8')
main = Blueprint('main', __name__)

# 配置日志记录器
logger = logging.getLogger(__name__)

# 使用增强的任务队列替换旧队列
# translation_queue = TranslationQueue()

# 简单任务状态存储（用于公开API）
simple_task_status = {}
simple_task_files = {}


@main.route('/')
@login_required
def index():
    return render_template('main/index.html', user=current_user)


@main.route('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('main.index'))


@main.route('/index')
@login_required
def index_page():
    return render_template('main/index.html', user=current_user)


@main.route('/page1')
@login_required
def page1():
    return render_template('main/page1.html', user=current_user)


@main.route('/page2')
@login_required
def page2():
    return render_template('main/page2.html', user=current_user)


# 允许的文件扩展名和大小限制
ALLOWED_EXTENSIONS = {'ppt', 'pptx'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_unique_filename(filename):
    """生成唯一的文件名"""
    ext = filename.rsplit('.', 1)[1].lower()
    return f"{uuid.uuid4().hex}.{ext}"

def custom_filename(name):
    # 移除危险的路径字符，仅保留基本合法字符 + 中文
    name = re.sub(r'[\\/:"*?<>|]+', '_', name)  # 替换非法字符
    return name
@main.route('/upload', methods=['POST'])
@login_required
def upload_file():
    try:
        # 验证用户是否登录
        if not current_user.is_authenticated:
            return jsonify({'code': 403, 'msg': '用户未登录'}), 403

        # 获取表单数据
        user_language = request.form.get('source_language', 'en')
        target_language = request.form.get('target_language', 'zh-cn')
        bilingual_translation = request.form.get('bilingual_translation', '0')
        translation_model = request.form.get('translation_model', 'qwen')  # 默认使用qwen模型
        select_page = request.form.getlist('select_page')

        # 转换select_page为整数列表
        if select_page and select_page[0]:
            try:
                select_page = [int(x) for x in select_page[0].split(',')]
                logger.info(f"  用户选择的页面: {select_page}")
            except Exception as e:
                logger.error(f"  页面选择参数解析失败: {select_page}, 错误: {str(e)}")
                select_page = []
        else:
            logger.info(f"  没有选择页面，将翻译所有页面")
            select_page = []

        # 其他参数处理
        stop_words_input = request.form.get('stop_words', '')
        stop_words = [word.strip() for word in stop_words_input.split('\n') if word.strip()]

        custom_translations_input = request.form.get('custom_translations', '')
        custom_translations = {}
        for line in custom_translations_input.split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = line.split('->')
            if len(parts) == 2:
                eng, chi = parts[0].strip(), parts[1].strip()
                custom_translations[eng] = chi

        # 获取上传的文件
        file = request.files.get('file')

        # 获取注释文件名（从表单参数，不是文件上传）
        annotation_filename = request.form.get('annotation_filename', '')

        if not file:
            return jsonify({'code': 400, 'msg': '请选择文件上传'}), 400

        # 检查文件名和类型
        if not file.filename or not allowed_file(file.filename):
            return jsonify({'code': 400, 'msg': '不支持的文件类型'}), 400

        # 检查文件大小
        file.seek(0, 2)  # 移动到文件末尾
        file_size = file.tell()  # 获取文件大小
        file.seek(0)  # 重置文件指针

        if file_size > MAX_FILE_SIZE:
            return jsonify({'code': 400, 'msg': f'文件大小超过限制 ({MAX_FILE_SIZE/1024/1024}MB)'}), 400

        # 创建用户上传目录
        upload_folder = current_app.config['UPLOAD_FOLDER']
        user_upload_dir = os.path.join(upload_folder, f"user_{current_user.id}")
        os.makedirs(user_upload_dir, exist_ok=True)

        # 生成安全的文件名
        original_filename = custom_filename(file.filename)
        
        # 创建语言名称到语言代码的映射
        language_map = {
            'English': 'en',
            'Chinese': 'zh',
            'Dutch': 'nl'
        }
        
        # 获取源语言和目标语言的代码
        source_lang_code = language_map.get(user_language, user_language)
        target_lang_code = language_map.get(target_language, target_language)
        
        # 生成新的文件名格式：源语言_目标语言_源文件名.pptx
        name_without_ext, ext = os.path.splitext(original_filename)
        new_filename = f"{source_lang_code}_{target_lang_code}_{name_without_ext}{ext}"
        
        stored_filename = get_unique_filename(new_filename)
        file_path = os.path.join(user_upload_dir, stored_filename)

        annotation_json = None

        try:
            # 保存PPT文件
            file.save(file_path)

            # 处理注释文件（如果选择了注释文件）
            if annotation_filename:
                logger.info(f"用户选择了注释文件: {annotation_filename}")
                # 注释文件应该在用户的注释目录中
                annotations_dir = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    f"{current_user.username}_annotations"
                )
                annotation_path = os.path.join(annotations_dir, annotation_filename)

                if os.path.exists(annotation_path):
                    try:
                        with open(annotation_path, 'r', encoding='utf-8') as f:
                            annotation_json = json.load(f)
                        logger.info(f"成功加载注释文件: {annotation_path}")
                    except Exception as e:
                        logger.error(f"解析注释文件失败: {str(e)}")
                        # 清理已上传的文件
                        os.remove(file_path)
                        return jsonify({'code': 400, 'msg': f'解析注释文件失败: {str(e)}'}), 400
                else:
                    logger.error(f"注释文件不存在: {annotation_path}")
                    os.remove(file_path)
                    return jsonify({'code': 400, 'msg': f'注释文件不存在: {annotation_filename}'}), 400

            # 创建上传记录，使用新的文件名
            record = UploadRecord(
                user_id=current_user.id,
                filename=new_filename,  # 使用新的文件名格式
                stored_filename=stored_filename,
                file_path=user_upload_dir,
                file_size=file_size,
                status='pending'
            )

            db.session.add(record)
            db.session.commit()

            # 添加翻译任务到队列
            priority = 0  # 默认优先级
            queue_position = translation_queue.add_task(
                user_id=current_user.id,
                user_name=current_user.username,
                file_path=file_path,
                annotation_filename=annotation_filename if annotation_filename else None,
                annotation_json=annotation_json,  # 直接传递注释数据
                select_page=select_page,
                source_language=user_language,
                target_language=target_language,
                bilingual_translation=bilingual_translation,
                translation_model=translation_model,  # 添加翻译模型参数
                priority=priority
            )

            return jsonify({
                'code': 200,
                'msg': '文件上传成功，已加入翻译队列',
                'queue_position': queue_position,
                'record_id': record.id
            })

        except Exception as e:
            # 清理已上传的文件
            if os.path.exists(file_path):
                os.remove(file_path)
            if annotation_filename and os.path.exists(annotation_path):
                os.remove(annotation_path)

            # 回滚数据库事务
            db.session.rollback()

            logger.error(f"文件上传失败: {str(e)}")
            return jsonify({'code': 500, 'msg': f'文件上传失败: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"处理上传请求失败: {str(e)}")
        return jsonify({'code': 500, 'msg': f'处理上传请求失败: {str(e)}'}), 500


def process_queue(app, stop_words_list, custom_translations,source_language, target_language,bilingual_translation):
    """
    处理翻译队列的函数

    注意：此函数已被 EnhancedTranslationQueue 类的 _processor_loop 方法取代，
    不再被主动调用。保留此函数仅用于兼容旧代码。
    新的任务处理逻辑在 app/utils/enhanced_task_queue.py 中实现。
    """
    while True:
        task = translation_queue.start_next_task()
        if not task:
            time.sleep(1)  # 如果没有任务，等待1秒
            continue

        # 创建应用上下文
        with app.app_context():
            # try:
                # 处理注释文件（如果有）
                annotations = None
                # TODO: 从任务中获取注释文件信息
                annotations_dir = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    f"{task['user_name']}_annotations"
                )
                if task['annotation_filename']:
                    annotations_file_path = os.path.join(annotations_dir, task['annotation_filename'])
                    annotations = load_data(annotations_file_path)
                # 执行翻译
                if annotations:
                    process_presentation_add_annotations(task['file_path'], annotations, stop_words_list,
                                                         custom_translations,source_language, target_language,bilingual_translation)

                else:
                    process_presentation(task['file_path'], stop_words_list, custom_translations,task['select_page'],source_language, target_language,bilingual_translation)

                set_textbox_autofit(task['file_path'])

                translation_queue.complete_current_task(success=True)

                # 更新数据库记录状态
                record = UploadRecord.query.filter_by(
                    user_id=task['user_id'],
                    file_path=os.path.dirname(task['file_path']),
                    stored_filename=os.path.basename(task['file_path'])
                ).first()

                if record:
                    record.status = 'completed'
                    db.session.commit()

            # except Exception as e:
            #     print(f"Translation error: {str(e)}")
            #     translation_queue.complete_current_task(success=False, error=str(e))

                # 更新数据库记录状态
                if 'record' in locals() and record:
                    record.status = 'failed'
                    try:
                        db.session.commit()
                    except:
                        db.session.rollback()
            # finally:
            #     # 确保会话被正确清理
            #     db.session.remove()


@main.route('/task_status')
@login_required
def get_task_status():
    """获取当前用户的任务状态"""
    status = translation_queue.get_task_status_by_user(current_user.id)
    if status:
        # 转换日志格式以便前端显示
        if 'recent_logs' in status:
            formatted_logs = []
            for log in status['recent_logs']:
                formatted_logs.append({
                    'timestamp': datetime_to_isoformat(log['timestamp']) if log['timestamp'] else '',
                    'message': log['message'],
                    'level': log['level']
                })
            status['recent_logs'] = formatted_logs

        # 使用ISO格式化时间戳
        for key in ['created_at', 'started_at', 'completed_at']:
            if key in status and status[key]:
                status[key] = datetime_to_isoformat(status[key])

        return jsonify(status)
    return jsonify({'status': 'no_task'})


@main.route('/queue_status')
@login_required
def get_queue_status():
    """获取翻译队列状态信息"""
    try:
        # 获取队列统计信息
        queue_stats = translation_queue.get_queue_stats()

        # 添加详细的任务信息
        active_tasks = queue_stats.get('processing', 0)  # 修正键名
        waiting_tasks = queue_stats.get('waiting', 0)
        max_concurrent = queue_stats.get('max_concurrent', 10)

        detailed_stats = {
            'max_concurrent_tasks': max_concurrent,
            'active_tasks': active_tasks,
            'waiting_tasks': waiting_tasks,
            'total_tasks': queue_stats.get('total', 0),
            'completed_tasks': queue_stats.get('completed', 0),
            'failed_tasks': queue_stats.get('failed', 0),
            'available_slots': max(0, max_concurrent - active_tasks),
            'queue_full': (active_tasks + waiting_tasks) >= max_concurrent,
            'system_status': 'normal' if (active_tasks + waiting_tasks) < max_concurrent else 'busy'
        }

        # 如果是管理员，提供更多详细信息
        if current_user.is_administrator():
            detailed_stats['admin_info'] = {
                'processor_running': translation_queue.running,
                'task_timeout': translation_queue.task_timeout,
                'retry_times': translation_queue.retry_times
            }

        return jsonify(detailed_stats)

    except Exception as e:
        logger.error(f"获取队列状态失败: {str(e)}")
        return jsonify({
            'error': '获取队列状态失败',
            'max_concurrent_tasks': 10,
            'active_tasks': 0,
            'waiting_tasks': 0,
            'total_tasks': 0,
            'available_slots': 10,
            'queue_full': False,
            'system_status': 'unknown'
        }), 500


@main.route('/history')
@login_required
def get_history():
    try:
        # 只返回状态为 completed 的记录
        records = UploadRecord.query.filter_by(user_id=current_user.id, status='completed') \
            .order_by(UploadRecord.upload_time.desc()).all()

        history_records = []
        for record in records:
            # 检查文件是否仍然存在
            file_exists = os.path.exists(os.path.join(record.file_path, record.stored_filename))

            # 使用ISO格式返回时间，让前端正确处理时区
            upload_time = datetime_to_isoformat(record.upload_time)
            
            # 直接使用数据库中存储的文件名
            history_records.append({
                'id': record.id,
                'filename': record.filename,  # 使用数据库中存储的文件名
                'file_size': record.file_size,
                'upload_time': upload_time,
                'status': record.status,
                'file_exists': file_exists
            })

        return jsonify(history_records)

    except Exception as e:
        print(f"History error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': '获取历史记录失败'
        }), 500


@main.route('/download/<int:record_id>')
@login_required
def download_file(record_id):
    try:
        # 获取上传记录
        record = UploadRecord.query.get_or_404(record_id)

        # 验证用户权限
        if record.user_id != current_user.id:
            return jsonify({'error': '无权访问此文件'}), 403

        # 检查文件是否存在
        file_path = os.path.join(record.file_path, record.stored_filename)
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404

        # 添加调试信息
        print(f"Downloading file: {file_path}")
        print(f"Original filename: {record.filename}")
        file_path = os.path.abspath(file_path)
        return send_file(file_path, as_attachment=True, download_name=record.filename)
    except Exception as e:
        print(f"Download error: {str(e)}")
        return jsonify({'error': f'下载失败: {str(e)}'}), 500


@main.route('/delete/<int:record_id>', methods=['DELETE'])
@login_required
def delete_file(record_id):
    try:
        # 获取上传记录
        record = UploadRecord.query.get_or_404(record_id)

        # 验证用户权限
        if record.user_id != current_user.id:
            return jsonify({'error': '无权删除此文件'}), 403

        try:
            # 删除物理文件
            file_path = os.path.join(record.file_path, record.stored_filename)
            if os.path.exists(file_path):
                os.remove(file_path)

            # 删除数据库记录
            db.session.delete(record)
            db.session.commit()

            return jsonify({'message': '文件删除成功'})

        except Exception as e:
            db.session.rollback()
            print(f"Delete error: {str(e)}")
            return jsonify({'error': f'删除失败: {str(e)}'}), 500

    except Exception as e:
        print(f"Delete error: {str(e)}")
        return jsonify({'error': f'删除失败: {str(e)}'}), 500


@main.route('/translate')
@login_required
def translate():
    return render_template('main/translate.html', user=current_user)


@main.route('/batch_process')
@login_required
def batch_process():
    return render_template('main/batch_process.html', user=current_user)


@main.route('/settings')
@login_required
def settings():
    return render_template('main/settings.html', user=current_user)


@main.route('/dictionary')
@login_required
def dictionary():
    return render_template('main/dictionary.html', user=current_user)


@main.route('/file_search')
@login_required
def file_search():
    return render_template('main/file_search.html', user=current_user)


@main.route('/account_settings')
@login_required
def account_settings():
    return render_template('main/account_settings.html', user=current_user)


@main.route('/registration_approval')
@login_required
def registration_approval():
    if not current_user.is_administrator():
        flash('没有权限访问此页面')
        return redirect(url_for('main.index'))
    return render_template('main/registration_approval.html')


# @main.route('/sso_management')
# @login_required
# def sso_management():
#     """SSO管理页面"""
#     if not current_user.is_administrator():
#         flash('没有权限访问此页面')
#         return redirect(url_for('main.index'))
#     return render_template('main/sso_management.html')


@main.route('/api/registrations')
@login_required
def get_registrations():
    if not current_user.is_administrator():
        return jsonify({'error': '没有权限访问'}), 403

    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    per_page = 10

    query = User.query
    if status != 'all':
        query = query.filter_by(status=status)

    pagination = query.order_by(User.register_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'registrations': [{ 
            'id': user.id,
            'username': user.username,
            'status': user.status,
            'register_time': datetime_to_isoformat(user.register_time) if user.register_time else None,
            'approve_user': user.approve_user.username if user.approve_user else None,
            'approve_time': datetime_to_isoformat(user.approve_time) if user.approve_time else None
        } for user in pagination.items],
        'total_pages': pagination.pages,
        'current_page': page,
        'total': pagination.total
    })


@main.route('/api/users')
@login_required
def get_users():
    if not current_user.is_administrator():
        return jsonify({'error': '没有权限访问'}), 403

    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    per_page = 10

    query = User.query.filter(User.status.in_(['approved', 'disabled']))
    if status != 'all':
        query = query.filter_by(status=status)

    pagination = query.order_by(User.register_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'users': [{ 
            'id': user.id,
            'username': user.username,
            'status': user.status,
            'register_time': datetime_to_isoformat(user.register_time) if user.register_time else None,
        } for user in pagination.items],
        'total_pages': pagination.pages,
        'current_page': page,
        'total': pagination.total
    })


@main.route('/api/registrations/<int:id>/approve', methods=['POST'])
@login_required
def approve_registration(id):
    if not current_user.is_administrator():
        return jsonify({'error': '没有权限进行此操作'}), 403

    user = User.query.get_or_404(id)
    if user.status != 'pending':
        return jsonify({'error': '该用户已被审批'}), 400

    try:
        user.status = 'approved'
        user.approve_time = datetime.now(pytz.timezone('Asia/Shanghai'))
        user.approve_user_id = current_user.id
        db.session.commit()
        return jsonify({'message': '审批成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main.route('/api/registrations/<int:id>/reject', methods=['POST'])
@login_required
def reject_registration(id):
    if not current_user.is_administrator():
        return jsonify({'error': '没有权限进行此操作'}), 403

    user = User.query.get_or_404(id)
    if user.status != 'pending':
        return jsonify({'error': '该用户已被审批'}), 400

    try:
        user.status = 'rejected'
        user.approve_time = datetime.now(pytz.timezone('Asia/Shanghai'))
        user.approve_user_id = current_user.id
        db.session.commit()
        return jsonify({'message': '已拒绝申请'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main.route('/api/users/<int:id>/disable', methods=['POST'])
@login_required
def disable_user(id):
    if not current_user.is_administrator():
        return jsonify({'error': '没有权限进行此操作'}), 403

    user = User.query.get_or_404(id)
    if user.status != 'approved':
        return jsonify({'error': '该用户无法被禁用'}), 400

    try:
        user.status = 'disabled'
        db.session.commit()
        return jsonify({'message': '用户已禁用'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main.route('/api/users/<int:id>/enable', methods=['POST'])
@login_required
def enable_user(id):
    if not current_user.is_administrator():
        return jsonify({'error': '没有权限进行此操作'}), 403

    user = User.query.get_or_404(id)
    if user.status != 'disabled':
        return jsonify({'error': '该用户无法被启用'}), 400

    try:
        user.status = 'approved'
        db.session.commit()
        return jsonify({'message': '用户已启用'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# 词库管理API路由
@main.route('/api/translations', methods=['GET'])
@login_required
def get_translations():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    search = request.args.get('search', '')

    # 只查询当前用户的翻译数据
    query = Translation.query.filter_by(user_id=current_user.id)

    if search:
        query = query.filter(
            db.or_(
                Translation.english.ilike(f'%{search}%'),
                Translation.chinese.ilike(f'%{search}%')
            )
        )

    pagination = query.order_by(Translation.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'translations': [{
            'id': item.id,
            'english': item.english,
            'chinese': item.chinese,
            'created_at': datetime_to_isoformat(item.created_at)
        } for item in pagination.items],
        'total_pages': pagination.pages,
        'current_page': page,
        'total_items': pagination.total
    })


@main.route('/api/translations', methods=['POST'])
@login_required
def add_translation():
    data = request.get_json()
    english = data.get('english')
    chinese = data.get('chinese')

    if not english or not chinese:
        return jsonify({'error': '英文和中文翻译都是必填的'}), 400

    # 检查是否已存在相同的翻译（在当前用户的词库中）
    existing = Translation.query.filter_by(
        user_id=current_user.id,
        english=english
    ).first()

    if existing:
        return jsonify({'error': '该英文翻译已存在于你的词库中'}), 400

    try:
        translation = Translation(
            english=english,
            chinese=chinese,
            user_id=current_user.id
        )
        db.session.add(translation)
        db.session.commit()

        return jsonify({
            'message': '添加成功',
            'translation': {
                'id': translation.id,
                'english': translation.english,
                'chinese': translation.chinese,
                'created_at': datetime_to_isoformat(translation.created_at)
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main.route('/api/translations/<int:id>', methods=['PUT'])
@login_required
def update_translation(id):
    translation = Translation.query.get_or_404(id)

    # 验证所有权
    if translation.user_id != current_user.id:
        return jsonify({'error': '无权修改此翻译'}), 403

    data = request.get_json()
    english = data.get('english')
    chinese = data.get('chinese')

    if not english or not chinese:
        return jsonify({'error': '英文和中文翻译都是必填的'}), 400

    # 检查是否与其他翻译重复（在当前用户的词库中）
    existing = Translation.query.filter(
        Translation.user_id == current_user.id,
        Translation.english == english,
        Translation.id != id
    ).first()

    if existing:
        return jsonify({'error': '该英文翻译已存在于你的词库中'}), 400

    try:
        translation.english = english
        translation.chinese = chinese
        db.session.commit()

        return jsonify({
            'message': '更新成功',
            'translation': {
                'id': translation.id,
                'english': translation.english,
                'chinese': translation.chinese,
                'created_at': datetime_to_isoformat(translation.created_at)
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main.route('/api/translations/<int:id>', methods=['DELETE'])
@login_required
def delete_translation(id):
    translation = Translation.query.get_or_404(id)

    # 验证所有权
    if translation.user_id != current_user.id:
        return jsonify({'error': '无权删除此翻译'}), 403

    try:
        db.session.delete(translation)
        db.session.commit()
        return jsonify({'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main.route('/api/translations/stats', methods=['GET'])
@login_required
def get_translation_stats():
    """获取当前用户的词库统计信息"""
    try:
        total_count = Translation.query.filter_by(user_id=current_user.id).count()
        return jsonify({
            'total_translations': total_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main.route('/api/train', methods=['POST'])
@login_required
def train_model():
    """使用当前用户的词库数据进行训练"""
    try:

        # Tokenizer()
        # # TODO: 实现模型训练逻辑，只使用当前用户的数据
        # train_model()
        translations = Translation.query.all()
        return jsonify({
            'message': '训练完成',
            'data_count': len(translations)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main.route('/ingredient')
@login_required
def ingredient():
    return render_template('main/ingredient.html')


# 加载JSON数据
def load_data(json_path):
    with open(json_path, 'r', encoding='UTF-8') as file:
        return json.load(file)


def extract_ingredient(s, ingredient):
    """提取匹配的成分"""
    ingredients = re.sub(r'(\(|\（)', ',', s)
    ingredients = re.sub(r'(\)|\）)', '', ingredients)
    ingredients = re.split(r'[、,，]', ingredients)
    ingredients = [ing.replace(' ', "") for ing in ingredients]
    # 去掉类似于"又名"、"以"、"记"等词
    cleaned_ingredient_list = [re.sub(r'(又名|以|记)', '', ing) for ing in ingredients]

    for i in cleaned_ingredient_list:
        if ingredient in i:
            return i
    return None


def clean_food_name(food_name):
    """清理食品名称"""
    return re.sub(r'备案入.*', '', food_name)


@main.route('/search', methods=['POST'])
@login_required
def search_ingredient():
    # print(request.form['query'])
    # 临时返回空结果，直到实现完整的搜索功能
    return jsonify([])


@main.route('/ingredient/download', methods=['POST'])
@login_required
def download_ingredient_file():
    # print(request.form['file_path'])
    # 临时返回错误，直到实现完整的下载功能
    return jsonify({'error': '功能暂未实现'}), 500


# 允许的PDF文件扩展名
PDF_ALLOWED_EXTENSIONS = {'pdf'}


def allowed_pdf_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in PDF_ALLOWED_EXTENSIONS


@main.route('/pdf/<filename>')
@login_required
def get_pdf(filename):
    try:
        # 获取上传文件夹路径
        upload_folder = current_app.config['UPLOAD_FOLDER']
        logger.info(f"PDF请求: {filename}, 上传文件夹: {upload_folder}")
        
        if not os.path.exists(upload_folder):
            logger.error(f"上传文件夹不存在: {upload_folder}")
            return jsonify({'error': '上传文件夹不存在'}), 404

        # 构建用户PDF目录路径
        user_pdf_dir = os.path.join(upload_folder, f"{current_user.username}_pdfs")
        logger.info(f"尝试从目录提供PDF: {user_pdf_dir}")

        if not os.path.exists(user_pdf_dir):
            # 尝试创建目录
            try:
                os.makedirs(user_pdf_dir, exist_ok=True)
                logger.info(f"创建了PDF目录: {user_pdf_dir}")
            except Exception as e:
                logger.error(f"无法创建PDF目录: {user_pdf_dir}, 错误: {str(e)}")
                return jsonify({'error': f'无法创建PDF目录: {str(e)}'}), 500
                
        # 构建完整的文件路径
        file_path = os.path.join(user_pdf_dir, filename)
        file_path = os.path.abspath(file_path)  # 转换为绝对路径
        logger.info(f"完整的PDF文件路径: {file_path}")

        if not os.path.exists(file_path):
            logger.error(f"PDF文件不存在: {file_path}")
            
            # 检查是否存在于其他可能的位置
            alt_paths = [
                os.path.join(upload_folder, filename),  # 直接在上传文件夹中
                os.path.join(upload_folder, 'pdf', filename),  # 在pdf子文件夹中
                os.path.join(current_app.root_path, 'static', 'uploads', filename)  # 在静态文件夹中
            ]
            
            for alt_path in alt_paths:
                if os.path.exists(alt_path):
                    logger.info(f"在替代位置找到PDF文件: {alt_path}")
                    file_path = alt_path
                    break
            else:
                return jsonify({'error': '文件不存在'}), 404

        # 检查文件权限
        try:
            # 尝试打开文件进行读取测试
            with open(file_path, 'rb') as f:
                f.read(1)  # 只读取1字节进行测试
            logger.info(f"文件权限检查通过: {file_path}")
        except PermissionError:
            logger.error(f"无法读取PDF文件(权限错误): {file_path}")
            # 尝试修改文件权限
            try:
                import stat
                os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                logger.info(f"已修改文件权限: {file_path}")
            except Exception as e:
                logger.error(f"无法修改文件权限: {str(e)}")
                return jsonify({'error': f'文件无法访问(权限错误): {str(e)}'}), 403
        except Exception as e:
            logger.error(f"文件读取测试失败: {str(e)}")
            return jsonify({'error': f'文件无法访问: {str(e)}'}), 403

        logger.info(f"准备提供PDF文件: {file_path}")
        try:
            # 使用安全的方式提供文件
            response = send_file(
                file_path,
                mimetype='application/pdf',
                as_attachment=False,
                download_name=filename
            )
            # 添加必要的安全头部
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            
            # 添加内容安全策略头部
            response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; object-src 'self'"
            
            # 添加X-Content-Type-Options头部，防止MIME类型嗅探
            response.headers['X-Content-Type-Options'] = 'nosniff'
            
            # 强制使用HTTPS
            if request.is_secure:
                response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
            logger.info(f"PDF文件已成功提供: {file_path}")
            return response

        except Exception as e:
            logger.error(f"提供PDF文件时出错: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"PDF提供错误: {str(e)}")
        return jsonify({'error': f'获取文件失败: {str(e)}'}), 500


@main.route('/ocr_region', methods=['POST'])
@login_required
def ocr_region():
    try:
        data = request.get_json()
        image_data = data.get('imageData')  # base64格式的图像数据

        # 使用异步OCR处理
        from ..function.pdf_annotate_async import ocr_image_region_async
        import asyncio

        # 创建异步事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                ocr_image_region_async(image_data, 'auto')
            )
            return jsonify(result)
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"OCR error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'OCR识别失败: {str(e)}'
        }), 500


@main.route('/save_annotations', methods=['POST'])
@login_required
def save_annotations():
    try:
        data = request.get_json()
        annotations = data.get('annotations', [])

        # 创建注释存储目录
        annotations_dir = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            f"{current_user.username}_annotations"
        )

        if not os.path.exists(annotations_dir):
            os.makedirs(annotations_dir)

        # 保存注释到JSON文件
        filename = f"annotations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = os.path.join(annotations_dir, filename)

        # 添加时间戳和用户信息
        annotation_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'user': current_user.username,
            'annotations': annotations
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(annotation_data, f, ensure_ascii=False, indent=2)

        return jsonify({'message': '注释保存成功'})

    except Exception as e:
        print(f"Save annotations error: {str(e)}")
        return jsonify({'error': f'保存失败: {str(e)}'}), 500


@main.route('/get_annotations/<filename>')
@login_required
def get_annotations(filename):
    try:
        annotations_dir = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            f"{current_user.username}_annotations"
        )

        file_path = os.path.join(annotations_dir, filename)

        if not os.path.exists(file_path):
            return jsonify({'error': '注释文件不存在'}), 404

        with open(file_path, 'r', encoding='utf-8') as f:
            annotations = json.load(f)

        return jsonify(annotations)

    except Exception as e:
        print(f"Get annotations error: {str(e)}")
        return jsonify({'error': f'获取注释失败: {str(e)}'}), 500


@main.route('/get_annotation_files')
@login_required
def get_annotation_files():
    try:
        # 获取用户注释文件目录
        annotations_dir = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            f"{current_user.username}_annotations"
        )

        if not os.path.exists(annotations_dir):
            return jsonify([])

        # 获取目录中的所有JSON文件
        files = []
        for filename in os.listdir(annotations_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(annotations_dir, filename)
                files.append({
                    'filename': filename,
                    'created_time': datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                })

        # 按创建时间降序排序
        files.sort(key=lambda x: x['created_time'], reverse=True)
        return jsonify(files)

    except Exception as e:
        print(f"Error getting annotation files: {str(e)}")
        return jsonify({'error': str(e)}), 500


@main.route('/api/users/sso')
@login_required
def get_sso_users():
    """获取SSO用户列表"""
    if not current_user.is_administrator():
        return jsonify({'error': '权限不足'}), 403

    try:
        # 查询所有SSO用户
        sso_users = User.query.filter(User.sso_provider.isnot(None)).all()

        users_data = []
        for user in sso_users:
            # 格式化时间
            last_login = format_datetime(user.last_login)
            register_time = format_datetime(user.register_time)

            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email or '',
                'display_name': user.get_display_name(),
                'first_name': user.first_name or '',
                'last_name': user.last_name or '',
                'sso_provider': user.sso_provider,
                'sso_subject': user.sso_subject or '',
                'status': user.status,
                'role': user.role.name if user.role else 'unknown',
                'last_login': last_login,
                'register_time': register_time
            })

        return jsonify(users_data)

    except Exception as e:
        logger.error(f"获取SSO用户列表失败: {e}")
        return jsonify({'error': f'获取用户列表失败: {str(e)}'}), 500


@main.route('/ocr_status', methods=['GET'])
@login_required
def get_ocr_status():
    """获取OCR状态信息"""
    try:
        from ..function.pdf_annotate_async import pdf_processor

        # 获取OCR读取器信息
        ocr_info = pdf_processor.get_ocr_info()

        return jsonify({
            'success': True,
            'ocr_info': ocr_info
        })

    except Exception as e:
        logger.error(f"获取OCR状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'获取状态失败: {str(e)}'
        }), 500


@main.route('/get_queue_status')
def get_detailed_queue_status():
    """获取详细的翻译队列状态（旧版API）"""
    username = session.get('username', '')
    if not username:
        return jsonify({'code': 403, 'msg': '用户未登录'}), 403

    try:
        # 获取队列状态和统计信息
        status_info = translation_queue.get_queue_status()
        user_tasks = translation_queue.get_user_tasks(username)

        # 轮询用户任务以获取当前状态
        user_task_details = []
        for task in user_tasks:
            task_detail = {
                'task_id': task.task_id,
                'file_name': os.path.basename(task.file_path),
                'status': task.status,
                'progress': task.progress,
                'result': task.result,
                'error': task.error,
                'created_at': task.created_at.isoformat(),
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None
            }
            user_task_details.append(task_detail)

        return jsonify({
            'code': 200,
            'queue_status': status_info,
            'user_tasks': user_task_details
        })
    except Exception as e:
        logger.error(f"获取队列状态失败: {str(e)}")
        return jsonify({'code': 500, 'msg': f'获取队列状态失败: {str(e)}'}), 500


@main.route('/cancel_task/<task_id>')
def cancel_task(task_id):
    """取消翻译任务"""
    username = session.get('username', '')
    if not username:
        return jsonify({'code': 403, 'msg': '用户未登录'}), 403

    try:
        # 尝试取消任务
        result = translation_queue.cancel_task(task_id, username)
        if result:
            return jsonify({'code': 200, 'msg': '任务已取消'})
        else:
            return jsonify({'code': 400, 'msg': '取消任务失败，任务可能不存在或已经开始处理'}), 400
    except Exception as e:
        logger.error(f"取消任务失败: {str(e)}")
        return jsonify({'code': 500, 'msg': f'取消任务失败: {str(e)}'}), 500


@main.route('/logs')
@login_required
def logs():
    """日志管理页面"""
    # 检查管理员权限
    if not current_user.is_administrator():
        flash('没有权限访问此页面', 'error')
        return redirect(url_for('main.index'))
    return render_template('main/logs.html')


# ==================== 公开API端点（不需要认证） ====================
# 用于简单前端（html文件夹）的API端点

@main.route('/start_translation', methods=['POST'])
def start_translation():
    """启动PPT翻译任务（公开API，不需要认证）"""
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': '不支持的文件格式'}), 400

        # 生成唯一的任务ID
        task_id = str(uuid.uuid4())

        # 创建临时上传目录
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        temp_upload_dir = os.path.join(upload_folder, 'temp')
        os.makedirs(temp_upload_dir, exist_ok=True)

        # 保存上传的文件
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{task_id}_{filename}"
        file_path = os.path.join(temp_upload_dir, unique_filename)
        file.save(file_path)

        logger.info(f"公开API文件已保存: {file_path}")

        # 初始化任务状态
        simple_task_status[task_id] = {
            'status': 'processing',
            'progress': 0,
            'current_slide': 0,
            'total_slides': 0,
            'file_path': file_path,
            'original_filename': filename,
            'created_at': datetime.now(),
            'error': None
        }

        # 启动异步翻译任务
        translation_thread = threading.Thread(
            target=execute_simple_translation_task,
            args=(task_id, file_path, filename)
        )
        translation_thread.daemon = True
        translation_thread.start()

        logger.info(f"公开API翻译任务已启动: {task_id}")

        # 立即返回任务ID
        return jsonify({
            'task_id': task_id,
            'status': 'started',
            'message': '翻译任务已启动'
        })

    except Exception as e:
        logger.error(f"启动公开API翻译任务失败: {str(e)}")
        return jsonify({'error': f'启动翻译任务失败: {str(e)}'}), 500


def execute_simple_translation_task(task_id, file_path, filename):
    """执行简单翻译任务（在后台线程中运行）"""
    try:
        logger.info(f"开始执行公开API翻译任务: {task_id}")

        # 进度回调函数
        def progress_callback(current, total):
            if task_id in simple_task_status:
                progress = int((current / total) * 100) if total > 0 else 0
                simple_task_status[task_id].update({
                    'progress': progress,
                    'current_slide': current,
                    'total_slides': total
                })
                logger.info(f"公开API任务 {task_id} 进度: {current}/{total} ({progress}%)")

        # 翻译参数（使用默认值）
        stop_words_list = []
        custom_translations = {}
        select_page = []  # 处理所有页面
        source_language = "en"
        target_language = "zh"
        bilingual_translation = "1"  # 双语模式

        # 执行翻译
        result = process_presentation(
            file_path,
            stop_words_list,
            custom_translations,
            select_page,
            source_language,
            target_language,
            bilingual_translation,
            progress_callback
        )

        if result:
            # 翻译成功
            simple_task_status[task_id].update({
                'status': 'completed',
                'progress': 100,
                'completed_at': datetime.now()
            })
            # 保存翻译后的文件路径
            simple_task_files[task_id] = file_path
            logger.info(f"公开API翻译任务完成: {task_id}")
        else:
            # 翻译失败
            simple_task_status[task_id].update({
                'status': 'failed',
                'error': '翻译处理失败'
            })
            logger.error(f"公开API翻译任务失败: {task_id}")

    except Exception as e:
        # 翻译异常
        error_msg = str(e)
        logger.error(f"公开API翻译任务异常: {task_id}, 错误: {error_msg}")
        simple_task_status[task_id].update({
            'status': 'failed',
            'error': error_msg
        })


@main.route('/task_status/<task_id>')
def get_simple_task_status(task_id):
    """获取特定任务状态（公开API，不需要认证）"""
    try:
        if task_id not in simple_task_status:
            return jsonify({'status': 'not_found', 'error': '任务不存在'}), 404

        task = simple_task_status[task_id]

        # 返回任务状态
        response = {
            'status': task['status'],
            'progress': task['progress'],
            'current_slide': task['current_slide'],
            'total_slides': task['total_slides']
        }

        if task['error']:
            response['error'] = task['error']

        return jsonify(response)

    except Exception as e:
        logger.error(f"获取公开API任务状态失败: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@main.route('/download/<task_id>')
def download_simple_translated_file(task_id):
    """下载翻译后的文件（公开API，不需要认证）"""
    try:
        if task_id not in simple_task_status:
            return jsonify({'error': '任务不存在'}), 404

        task = simple_task_status[task_id]

        if task['status'] != 'completed':
            return jsonify({'error': '任务尚未完成'}), 400

        if task_id not in simple_task_files:
            return jsonify({'error': '翻译文件不存在'}), 404

        file_path = simple_task_files[task_id]

        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404

        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"translated_{task['original_filename']}",
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation'
        )

    except Exception as e:
        logger.error(f"下载公开API文件失败: {str(e)}")
        return jsonify({'error': f'下载失败: {str(e)}'}), 500


@main.route('/ppt_translate', methods=['POST'])
def ppt_translate_simple():
    """PPT翻译（公开API，兼容原有接口，不需要认证）"""
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': '不支持的文件格式'}), 400

        # 创建临时上传目录
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        temp_upload_dir = os.path.join(upload_folder, 'temp')
        os.makedirs(temp_upload_dir, exist_ok=True)

        # 保存上传的文件
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(temp_upload_dir, unique_filename)
        file.save(file_path)

        logger.info(f"同步API文件已保存: {file_path}")

        # 翻译参数（使用默认值）
        stop_words_list = []
        custom_translations = {}
        select_page = []  # 处理所有页面
        source_language = "en"
        target_language = "zh"
        bilingual_translation = "1"  # 双语模式

        # 执行同步翻译
        result = process_presentation(
            file_path,
            stop_words_list,
            custom_translations,
            select_page,
            source_language,
            target_language,
            bilingual_translation
        )

        if result:
            logger.info(f"同步API翻译完成: {file_path}")
            # 返回翻译后的文件
            return send_file(
                file_path,
                as_attachment=True,
                download_name=f"translated_{filename}",
                mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation'
            )
        else:
            return jsonify({'error': '翻译处理失败'}), 500

    except Exception as e:
        logger.error(f"同步API翻译失败: {str(e)}")
        return jsonify({'error': f'翻译失败: {str(e)}'}), 500


@main.route('/db_stats')
@login_required
def db_stats():
    """数据库状态页面"""
    if not current_user.is_administrator():
        flash('您没有权限访问此页面')
        return redirect(url_for('main.index'))
    
    # 获取数据库统计信息
    db_stats = get_db_stats()
    
    # 获取线程池统计信息
    thread_pool_stats = thread_pool.get_stats()
    
    # 获取任务队列统计信息
    queue_stats = translation_queue.get_queue_stats()
    
    return render_template('main/db_stats.html', 
                          user=current_user,
                          db_stats=db_stats,
                          thread_pool_stats=thread_pool_stats,
                          queue_stats=queue_stats)


@main.route('/db_stats_data')
@login_required
def get_db_stats_data():
    """获取数据库统计数据的API，用于AJAX刷新"""
    if not current_user.is_administrator():
        return jsonify({'error': '没有权限访问此API'}), 403
    
    # 获取数据库统计信息
    db_stats = get_db_stats()
    
    return jsonify(db_stats)


@main.route('/recycle_connections', methods=['POST'])
@login_required
def recycle_connections():
    """回收空闲数据库连接"""
    if not current_user.is_administrator():
        return jsonify({'success': False, 'message': '没有权限执行此操作'}), 403
    
    try:
        # 调用翻译队列中的回收连接方法
        result = translation_queue.recycle_idle_connections()
        
        # 记录操作日志
        logger.info(f"管理员 {current_user.username} 手动回收了数据库空闲连接")
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"回收数据库连接失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'回收连接失败: {str(e)}',
            'error': str(e)
        }), 500


def get_db_stats():
    """获取数据库连接池统计信息"""
    try:
        engine = db.engine
        
        # 基本信息
        stats = {
            'engine_name': engine.name,
            'driver_name': engine.driver,
            'url': str(engine.url).replace('://*:*@', '://***:***@'),  # 隐藏敏感信息
            'pool_size': engine.pool.size(),
            'current_size': engine.pool.size(),
            'checked_in': engine.pool.checkedin(),
            'checked_out': engine.pool.checkedout(),
            'overflow': engine.pool.overflow(),
            'max_overflow': engine.pool._max_overflow
        }
        
        # 获取连接池配置
        try:
            stats['pool_config'] = {
                'size': engine.pool.size(),
                'max_overflow': engine.pool._max_overflow,
                'timeout': engine.pool._timeout,
                'recycle': engine.pool._recycle,
                'pre_ping': engine.pool._pre_ping
            }
        except:
            stats['pool_config'] = None
        
        # 获取已签出连接的详细信息
        checked_out_details = []
        try:
            mutex = engine.pool._mutex
            checked_out = {}
            
            if hasattr(mutex, '_semlock') and hasattr(engine.pool, '_checked_out'):
                # SQLAlchemy 1.3+ 
                checked_out = engine.pool._checked_out
            elif hasattr(engine.pool, '_checked_out'):
                # 早期版本
                checked_out = engine.pool._checked_out
            
            for conn, (ref, traceback, timestamp) in checked_out.items():
                conn_id = str(conn)
                checkout_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                duration = time.time() - timestamp
                duration_str = f"{duration:.2f}秒"
                
                if duration > 3600:
                    hours = int(duration / 3600)
                    minutes = int((duration % 3600) / 60)
                    duration_str = f"{hours}小时{minutes}分钟"
                elif duration > 60:
                    minutes = int(duration / 60)
                    seconds = int(duration % 60)
                    duration_str = f"{minutes}分钟{seconds}秒"
                
                checked_out_details.append({
                    'connection_id': conn_id,
                    'checkout_time': checkout_time,
                    'duration': duration_str,
                    'stack_trace': '\n'.join(traceback) if traceback else '无堆栈信息'
                })
            
            stats['checked_out_details'] = checked_out_details
        except Exception as e:
            stats['checked_out_details'] = []
            logger.warning(f"获取已签出连接详情失败: {str(e)}")
        
        return stats
    
    except Exception as e:
        logger.error(f"获取数据库统计信息失败: {str(e)}")
        return {'error': f'获取数据库统计信息失败: {str(e)}'}


@main.route('/system_status', methods=['GET'])
@login_required
def system_status():
    """获取系统状态信息"""
    if not current_user.is_administrator():
        return jsonify({'error': '没有权限访问此API'}), 403
    
    try:
        # 获取线程池状态
        thread_pool_stats = thread_pool.get_stats()
        thread_pool_health = thread_pool.get_health_status()
        
        # 获取任务队列状态
        queue_stats = translation_queue.get_queue_stats()
        
        # 获取数据库连接状态
        db_stats = get_db_stats()
        
        # 系统内存使用情况
        import psutil
        memory = psutil.virtual_memory()
        memory_stats = {
            'total': memory.total,
            'available': memory.available,
            'used': memory.used,
            'percent': memory.percent
        }
        
        # CPU使用情况
        cpu_stats = {
            'percent': psutil.cpu_percent(),
            'count': psutil.cpu_count(),
            'logical_count': psutil.cpu_count(logical=True)
        }
        
        # 返回汇总状态
        status = {
            'thread_pool': {
                'stats': thread_pool_stats,
                'health': thread_pool_health
            },
            'task_queue': queue_stats,
            'database': db_stats,
            'memory': memory_stats,
            'cpu': cpu_stats,
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"获取系统状态失败: {str(e)}")
        return jsonify({
            'error': f'获取系统状态失败: {str(e)}'
        }), 500


@main.route('/system/reset_thread_pool', methods=['POST'])
@login_required
def reset_thread_pool():
    """重置线程池"""
    if not current_user.is_administrator():
        return jsonify({'success': False, 'message': '没有权限执行此操作'}), 403
    
    try:
        # 记录操作日志
        logger.warning(f"管理员 {current_user.username} 正在重置线程池")
        
        # 获取线程池配置
        stats_before = thread_pool.get_stats()
        
        # 重新配置线程池
        thread_pool.configure()
        
        # 获取重置后的状态
        stats_after = thread_pool.get_stats()
        
        return jsonify({
            'success': True,
            'message': '线程池已重置',
            'before': stats_before,
            'after': stats_after
        })
        
    except Exception as e:
        logger.error(f"重置线程池失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'重置线程池失败: {str(e)}',
            'error': str(e)
        }), 500


@main.route('/system/reset_task_queue', methods=['POST'])
@login_required
def reset_task_queue():
    """重置任务队列"""
    if not current_user.is_administrator():
        return jsonify({'success': False, 'message': '没有权限执行此操作'}), 403
    
    try:
        # 记录操作日志
        logger.warning(f"管理员 {current_user.username} 正在重置任务队列")
        
        # 获取任务队列状态
        stats_before = translation_queue.get_queue_stats()
        
        # 停止处理器
        translation_queue.stop_processor()
        
        # 重新启动处理器
        translation_queue.start_processor()
        
        # 获取重置后的状态
        stats_after = translation_queue.get_queue_stats()
        
        return jsonify({
            'success': True,
            'message': '任务队列已重置',
            'before': stats_before,
            'after': stats_after
        })
        
    except Exception as e:
        logger.error(f"重置任务队列失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'重置任务队列失败: {str(e)}',
            'error': str(e)
        }), 500


@main.route('/system_monitoring')
@login_required
def system_monitoring():
    """系统监控页面 - 显示线程池、任务队列和数据库连接状态"""
    # 验证用户是否有管理员权限
    if not current_user.is_administrator:
        flash('您没有访问此页面的权限。', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('main/system_monitoring.html', user=current_user)


@main.route('/pdf_annotate')
@login_required
def pdf_annotate():
    """PDF注释页面"""
    try:
        # 添加详细的日志
        logger.info("访问 pdf_annotate 页面")
        return render_template('main/pdf_annotate.html')
    except Exception as e:
        logger.error(f"渲染 pdf_annotate 页面出错: {str(e)}")
        # 返回一个简单的错误页面，避免模板渲染问题
        return f"PDF注释功能临时不可用: {str(e)}", 500


@main.route('/upload_pdf', methods=['POST'])
@login_required
def upload_pdf():
    try:
        if 'file' not in request.files:
            logger.error("没有文件部分在请求中")
            return jsonify({'error': '没有文件部分'}), 400

        file = request.files['file']
        if file.filename == '':
            logger.error("没有选择文件")
            return jsonify({'error': '没有选择文件'}), 400

        if not allowed_pdf_file(file.filename):
            logger.error(f"不允许的文件类型: {file.filename}")
            return jsonify({'error': '不允许的文件类型'}), 400

        # 生成安全的文件名和唯一的存储文件名
        original_filename = secure_filename(file.filename)
        logger.info(f"安全文件名: {original_filename}")
        stored_filename = f"{uuid.uuid4().hex}.pdf"

        # 确保上传文件夹存在
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            logger.info(f"创建上传文件夹: {upload_folder}")

        # 创建用户PDF目录
        user_pdf_dir = os.path.join(upload_folder, f"{current_user.username}_pdfs")
        logger.info(f"PDF上传目录路径: {user_pdf_dir}")

        if not os.path.exists(user_pdf_dir):
            os.makedirs(user_pdf_dir)
            logger.info(f"创建PDF上传目录: {user_pdf_dir}")

        # 保存文件
        file_path = os.path.join(user_pdf_dir, stored_filename)
        file_path = os.path.abspath(file_path)  # 转换为绝对路径
        logger.info(f"保存文件的绝对路径: {file_path}")

        file.save(file_path)
        logger.info(f"PDF文件已保存到: {file_path}")

        # 验证文件是否成功保存
        if not os.path.exists(file_path):
            raise Exception(f"文件保存失败，路径: {file_path}")

        # 检查文件权限并尝试修复
        try:
            with open(file_path, 'rb') as f:
                f.read(1)  # 测试读取
        except PermissionError:
            # 尝试修改文件权限
            try:
                import stat
                os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                logger.info(f"已修改文件权限: {file_path}")
            except Exception as e:
                logger.error(f"无法修改文件权限: {str(e)}")
                raise Exception(f"文件无法访问，权限问题: {str(e)}")
        except Exception as e:
            raise Exception(f"文件读取测试失败: {str(e)}")

        # 生成完整的URL，包含域名和协议，确保使用与当前请求相同的协议
        file_url = url_for('main.get_pdf', filename=stored_filename, _external=True)
        
        # 确保URL使用与当前请求相同的协议(HTTP或HTTPS)
        if request.is_secure and file_url.startswith('http:'):
            file_url = file_url.replace('http:', 'https:', 1)
        
        logger.info(f"生成的PDF URL: {file_url}")

        return jsonify({
            'message': '文件上传成功',
            'filename': original_filename,
            'file_url': file_url,
            'file_path': file_path  # 添加服务器端文件路径
        })

    except Exception as e:
        logger.error(f"PDF上传错误: {str(e)}")
        # 如果文件已经保存，则删除
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"清理失败的上传: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"无法清理文件: {cleanup_error}")
        return jsonify({'error': f'上传失败: {str(e)}'}), 500


@main.route('/file_management')
@login_required
def file_management():
    """文件管理页面 - 管理员可查看所有用户上传的文件"""
    if not current_user.is_administrator():
        flash('没有权限访问此页面')
        return redirect(url_for('main.index'))
        
    return render_template('main/file_management.html', user=current_user)


@main.route('/user_management')
@login_required
def user_management():
    """用户管理页面 - 仅管理员可见"""
    if not current_user.is_administrator():
        flash('没有权限访问此页面')
        return redirect(url_for('main.index'))
    return render_template('main/user_management.html', user=current_user)


@main.route('/api/admin/files')
@login_required
def get_admin_files():
    """获取所有用户上传的文件 (仅管理员)"""
    if not current_user.is_administrator():
        return jsonify({'error': '没有权限访问此API'}), 403
        
    try:
        # 查询所有文件记录
        records = UploadRecord.query.order_by(UploadRecord.upload_time.desc()).all()
        
        # 构建文件列表，包含用户信息
        files = []
        for record in records:
            # 查询用户信息
            user = User.query.get(record.user_id)
            username = user.username if user else "未知用户"
            
            # 检查文件是否存在
            file_exists = os.path.exists(os.path.join(record.file_path, record.stored_filename))
            
            # 使用ISO格式返回时间，让前端正确处理时区
            upload_time = datetime_to_isoformat(record.upload_time)
            
            files.append({
                'id': record.id,
                'filename': record.filename,
                'stored_filename': record.stored_filename,
                'file_path': record.file_path,
                'file_size': record.file_size,
                'upload_time': upload_time,
                'status': record.status,
                'error_message': record.error_message,
                'user_id': record.user_id,
                'username': username,
                'file_exists': file_exists
            })
            
        return jsonify({
            'files': files,
            'total': len(files)
        })
        
    except Exception as e:
        logger.error(f"获取管理员文件列表失败: {str(e)}")
        return jsonify({
            'error': f'获取文件列表失败: {str(e)}',
            'files': [],
            'total': 0
        }), 500


@main.route('/api/admin/files/<int:record_id>', methods=['DELETE'])
@login_required
def admin_delete_file(record_id):
    """管理员删除文件"""
    if not current_user.is_administrator():
        return jsonify({'error': '没有权限执行此操作'}), 403
        
    try:
        # 获取上传记录
        record = UploadRecord.query.get_or_404(record_id)
        
        # 删除物理文件
        file_path = os.path.join(record.file_path, record.stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"管理员删除文件: {file_path}")
        
        # 删除数据库记录
        db.session.delete(record)
    except Exception as e:
        db.session.rollback()
        logger.error(f"管理员删除文件失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'删除文件失败: {str(e)}'
        }), 500
        db.session.commit()
    return jsonify({
            'success': True,
            'message': '文件删除成功'
        })

@main.route('/zxcvbnm')
def secret_login():
    """秘密登录页面，用于直接访问账号密码登录"""
    return render_template('auth/login.html')
