"""
文件清理定时任务（备用）
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)

def setup_cleanup_task():
    """设置文件清理定时任务"""
    try:
        # 获取Flask应用实例
        from app import create_app

        # 创建应用实例
        app = create_app()

        scheduler = BackgroundScheduler()

        # 每天凌晨3点运行清理任务
        trigger = CronTrigger(
            hour=3,
            minute=0
        )

        def cleanup_job():
            """执行清理任务"""
            # 在应用上下文中执行
            with app.app_context():
                try:
                    logger.info("开始执行文件清理任务")
                    from ..utils.cleanup import file_cleanup
                    success_count, fail_count = file_cleanup.cleanup_files()
                    logger.info(f"文件清理完成: 成功 {success_count} 个, 失败 {fail_count} 个")
                except Exception as e:
                    logger.error(f"文件清理任务执行失败: {str(e)}")

        scheduler.add_job(
            cleanup_job,
            trigger=trigger,
            id='file_cleanup_job',
            name='File Cleanup Job',
            replace_existing=True,
            max_instances=1
        )

        scheduler.start()
        logger.info("文件清理定时任务已启动")

        return scheduler

    except Exception as e:
        logger.error(f"设置清理任务失败: {str(e)}")
        raise