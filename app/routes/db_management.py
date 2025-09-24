"""
数据库管理路由
提供数据库连接池状态查看和管理功能
"""
import logging
from flask import Blueprint, render_template, jsonify, current_app
from flask_login import login_required, current_user
from app.utils.db_session_manager import get_db_stats, recycle_idle_connections
from app.utils.thread_pool_executor import thread_pool
from app.utils.enhanced_task_queue import translation_queue

# 创建蓝图
router = Blueprint('db_management', __name__)

logger = logging.getLogger(__name__)

@router.route('/admin/db-stats')
@login_required
def db_stats_page():
    """
    显示数据库连接池状态页面
    
    Returns:
        渲染后的数据库统计信息页面
    """
    try:
        # 检查用户权限
        if not current_user.is_administrator():
            logger.warning(f"非管理员用户 {current_user.username} 尝试访问数据库统计信息")
            return render_template('main/error.html', 
                                  error_title="权限错误", 
                                  error_message="您没有权限访问此页面")
        
        # 获取数据库连接池统计信息
        db_stats = get_db_stats()
        
        # 获取线程池统计信息
        thread_stats = {
            'io_bound_pool_size': thread_pool.io_bound_workers,
            'io_bound_active_threads': thread_pool.get_io_active_count(),
            'cpu_bound_pool_size': thread_pool.cpu_bound_workers,
            'cpu_bound_active_threads': thread_pool.get_cpu_active_count(),
            'total_tasks': thread_pool.get_task_count(),
            'completed_tasks': thread_pool.get_completed_task_count()
        }
        
        # 获取任务队列统计信息
        queue_stats = {
            'queue_size': translation_queue.get_queue_size(),
            'active_tasks': translation_queue.get_active_count(),
            'waiting_tasks': translation_queue.get_waiting_count(),
            'completed_tasks': translation_queue.get_completed_count(),
            'failed_tasks': translation_queue.get_failed_count(),
            'max_concurrent': translation_queue.max_concurrent_tasks
        }
        
        logger.info(f"管理员 {current_user.username} 访问了数据库统计信息页面")
        
        return render_template('main/db_stats.html', 
                              db_stats=db_stats,
                              thread_stats=thread_stats,
                              queue_stats=queue_stats)
    
    except Exception as e:
        logger.error(f"显示数据库统计信息页面时出错: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        
        return render_template('main/db_stats.html', 
                              error=f"获取数据库统计信息失败: {str(e)}")

@router.route('/api/db/recycle', methods=['POST'])
@login_required
def recycle_connections():
    """
    回收空闲数据库连接
    
    Returns:
        JSON响应，包含操作结果
    """
    try:
        # 检查用户权限
        if not current_user.is_administrator():
            logger.warning(f"非管理员用户 {current_user.username} 尝试回收数据库连接")
            return jsonify({
                'success': False,
                'error': "您没有权限执行此操作"
            }), 403
        
        # 回收空闲连接
        recycled = recycle_idle_connections()
        
        logger.info(f"管理员 {current_user.username} 回收了 {recycled} 个空闲数据库连接")
        
        return jsonify({
            'success': True,
            'recycled': recycled,
            'message': f"成功回收了 {recycled} 个空闲连接"
        })
    
    except Exception as e:
        logger.error(f"回收空闲数据库连接时出错: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 