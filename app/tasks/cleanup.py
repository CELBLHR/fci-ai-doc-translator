"""
文件清理任务
"""
import logging
import os
from datetime import datetime, timedelta
from flask import current_app
from pytz import timezone

logger = logging.getLogger(__name__)

def cleanup_expired_files():
    """清理过期文件"""
    # 获取Flask应用实例
    from app import create_app

    # 创建应用实例
    app = create_app()

    # 在应用上下文中执行清理任务
    with app.app_context():
        try:
            logger.info("开始清理过期文件")

            # 导入模型（在应用上下文中）
            from ..models import User, UploadRecord, db
            from ..utils.storage_manager import create_storage_manager

            # 获取所有用户
            users = User.query.all()
            total_success = 0
            total_fail = 0

            for user in users:
                try:
                    # 创建存储管理器
                    storage = create_storage_manager(user.id)

                    # 清理文件
                    success, fail = storage.cleanup_expired_files()
                    total_success += success
                    total_fail += fail

                    logger.info(f"用户 {user.id} 清理完成: 成功 {success}, 失败 {fail}")

                except Exception as e:
                    logger.error(f"清理用户 {user.id} 的文件时出错: {str(e)}")
                    total_fail += 1

            # 额外清理：删除临时文件和孤立文件
            cleanup_temp_files()

            logger.info(f"清理完成: 总成功 {total_success}, 总失败 {total_fail}")

        except Exception as e:
            logger.error(f"清理过期文件时出错: {str(e)}")
            raise

def cleanup_temp_files():
    """清理临时文件"""
    try:
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        temp_folder = os.path.join(upload_folder, 'temp')

        if not os.path.exists(temp_folder):
            return

        # 清理超过24小时的临时文件
        cutoff_time = datetime.now() - timedelta(hours=24)
        cleaned_count = 0

        for filename in os.listdir(temp_folder):
            file_path = os.path.join(temp_folder, filename)
            try:
                if os.path.isfile(file_path):
                    # 获取文件修改时间
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                    if file_mtime < cutoff_time:
                        os.remove(file_path)
                        cleaned_count += 1
                        logger.debug(f"删除临时文件: {filename}")

            except Exception as e:
                logger.error(f"删除临时文件 {filename} 时出错: {str(e)}")

        if cleaned_count > 0:
            logger.info(f"清理了 {cleaned_count} 个临时文件")

    except Exception as e:
        logger.error(f"清理临时文件时出错: {str(e)}")

def schedule_cleanup_task():
    """调度清理任务"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from app.utils.thread_pool_executor import thread_pool
        import time

        # 确保线程池已初始化
        if not thread_pool.initialized:
            logger.info("线程池未初始化，正在初始化...")
            thread_pool.configure()
            # 等待线程池初始化完成
            time.sleep(1)
            
        # 检查线程池健康状态
        health_status = thread_pool.get_health_status()
        if not health_status.get('healthy', False):
            logger.warning(f"线程池健康状态异常: {health_status}")
            # 尝试重新初始化线程池
            thread_pool.configure()
            time.sleep(1)
            # 再次检查健康状态
            health_status = thread_pool.get_health_status()
            if not health_status.get('healthy', False):
                logger.error("线程池健康状态仍然异常，清理任务可能无法正常执行")
            else:
                logger.info("线程池已重新初始化，健康状态正常")

        # 创建调度器
        scheduler = BackgroundScheduler()

        # 每天凌晨3点执行清理
        beijing = timezone('Asia/Shanghai')
        trigger = CronTrigger(hour=3, timezone=beijing)
        
        # 定义安全的清理任务包装函数
        def safe_cleanup_job():
            try:
                # 再次检查线程池健康状态
                if thread_pool.initialized and thread_pool.get_health_status().get('healthy', False):
                    logger.info("开始执行定时清理任务")
                    cleanup_expired_files()
                    logger.info("定时清理任务完成")
                else:
                    logger.error("线程池状态异常，跳过定时清理任务")
            except Exception as e:
                logger.error(f"执行定时清理任务失败: {str(e)}")

        # 添加任务
        scheduler.add_job(
            safe_cleanup_job,
            trigger=trigger,
            id='cleanup_expired_files',
            name='清理过期文件',
            replace_existing=True,
            max_instances=1  # 确保同时只有一个实例运行
        )

        # 启动调度器
        scheduler.start()
        logger.info("文件清理任务已调度，每天凌晨3点执行")

        return scheduler

    except Exception as e:
        logger.error(f"调度清理任务失败: {str(e)}")
        # 不抛出异常，避免影响应用启动
        return None

def manual_cleanup():
    """手动执行清理任务（用于测试）"""
    try:
        logger.info("手动执行文件清理任务")
        cleanup_expired_files()
        logger.info("手动清理任务完成")
    except Exception as e:
        logger.error(f"手动清理任务失败: {str(e)}")
        raise