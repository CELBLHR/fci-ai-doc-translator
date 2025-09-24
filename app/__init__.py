"""
应用程序初始化模块
创建和配置 Flask 应用实例
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_caching import Cache


from .config import config, app_config
from .utils.logger import LogManager
from .utils.thread_pool_executor import thread_pool
from .utils.enhanced_task_queue import translation_queue
from .utils.lazy_http_client import http_client
from .utils.db_session_manager import setup_db_monitoring

# 创建扩展实例
db = SQLAlchemy()
login_manager = LoginManager()
cache = Cache()
log_manager = LogManager()

def create_app(config_name='development'):
    """
    创建 Flask 应用实例

    Args:
        config_name: 配置名称

    Returns:
        Flask 应用实例
    """
    # 创建应用实例
    app = Flask(__name__)

    # 加载配置
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # 确保上传目录存在
    uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    print(uploads_path)
    os.makedirs(uploads_path, exist_ok=True)

    # 初始化日志
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    log_manager.configure(
        log_level=os.getenv('LOG_LEVEL', 'INFO'),
        log_format=os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
        date_format=os.getenv('LOG_DATE_FORMAT', '%Y-%m-%d %H:%M:%S'),
        max_bytes=int(os.getenv('LOG_MAX_BYTES', 10 * 1024 * 1024)),  # 默认10MB
        backup_count=int(os.getenv('LOG_BACKUP_COUNT', 5)),
        log_dir=log_dir
    )
    logger = log_manager.get_logger()
    logger.info("正在初始化应用...")

    # 配置日志过滤器 - 减少SQL和HTTP请求日志噪音
    _configure_smart_log_filters(config_name)

    # 配置HTTPS重定向
    if config_name == 'production' or os.environ.get('FORCE_HTTPS', 'false').lower() == 'true':
        logger.info("启用HTTPS重定向")
        
        @app.before_request
        def redirect_to_https():
            from flask import request, redirect, url_for
            # 如果请求不是HTTPS，则重定向到HTTPS
            if not request.is_secure and request.endpoint and request.endpoint != 'static':
                url = request.url.replace('http://', 'https://', 1)
                logger.debug(f"重定向HTTP请求到HTTPS: {url}")
                return redirect(url, code=301)
    
    # 显式设置SQLAlchemy引擎选项，确保连接池大小为100
    pool_size = int(os.environ.get('DB_POOL_SIZE', 100))
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': pool_size,
        'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', 30)),
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 3600)),
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 20)),
        'connect_args': {
            'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', 10))
        }
    }
    logger.info(f"配置数据库连接池大小: {pool_size}")

    # 初始化扩展
    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录'
    login_manager.login_message_category = 'info'

    cache.init_app(app)

    # 配置线程池
    thread_pool.configure(
        max_workers=int(os.getenv('THREAD_POOL_MAX_WORKERS', 32)),
        io_bound_workers=int(os.getenv('THREAD_POOL_IO_WORKERS', 24)),
        cpu_bound_workers=int(os.getenv('THREAD_POOL_CPU_WORKERS', 8)),
        thread_name_prefix=os.getenv('THREAD_POOL_NAME_PREFIX', 'app')
    )

    # 配置任务队列 - 限制最大并发翻译任务为10个
    translation_queue.configure(
        max_concurrent_tasks=int(os.getenv('TASK_QUEUE_MAX_CONCURRENT', 10)),
        task_timeout=int(os.getenv('TASK_QUEUE_TIMEOUT', 3600)),
        retry_times=int(os.getenv('TASK_QUEUE_RETRY_TIMES', 3))
    )

    # 配置 HTTP 客户端
    http_client.configure(
        max_connections=int(os.getenv('HTTP_CLIENT_MAX_CONNECTIONS', 100)),
        default_timeout=int(os.getenv('HTTP_CLIENT_TIMEOUT', 60)),
        retry_times=int(os.getenv('HTTP_CLIENT_RETRY_TIMES', 3)),
        retry_delay=int(os.getenv('HTTP_CLIENT_RETRY_DELAY', 1))
    )

    # 注册蓝图
    from .views.main import main as main_bp
    from .views.auth import bp as auth_bp
    from .views.upload import bp as upload_bp
    from .views.sso_auth import sso_bp
    from .views.ingredient import ingredient as ingredient_bp
    from .routes.log_management import router as log_management_bp
    from .routes.stop_words import bp as stop_words_bp
    from .routes.db_management import router as db_management_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(sso_bp)  # SSO路由已包含前缀
    app.register_blueprint(upload_bp, url_prefix='/api')
    app.register_blueprint(ingredient_bp, url_prefix='/ingredient')  # 成分搜索路由
    app.register_blueprint(stop_words_bp)  # 停翻词路由
    app.register_blueprint(log_management_bp)
    app.register_blueprint(db_management_bp)  # 数据库管理路由

    # 创建数据库表
    with app.app_context():
        db.create_all()
        logger.info("数据库表已创建")

    # 启动任务处理器
    translation_queue.start_processor()
    logger.info("任务处理器已启动")

    # 启动数据库监控
    monitor_interval = int(os.getenv('DB_MONITOR_INTERVAL', 3600))  # 默认每小时监控一次
    db_monitor_thread = setup_db_monitoring(app, interval=monitor_interval)
    logger.info(f"数据库监控已启动，监控间隔: {monitor_interval}秒")
    
    # 启动清理任务 - 确保在任务处理器启动后执行
    try:
        from .tasks.cleanup import schedule_cleanup_task
        cleanup_scheduler = schedule_cleanup_task()
        logger.info("文件清理任务已调度")
    except Exception as e:
        logger.error(f"调度清理任务失败: {str(e)}")

    logger.info(f"应用已初始化 - 环境: {config_name}")
    return app

@login_manager.user_loader
def load_user(user_id):
    from .models.user import User
    return User.query.get(int(user_id))

def _configure_smart_log_filters(config_name):
    """
    配置智能日志过滤器，减少SQL查询和HTTP请求的日志噪音

    Args:
        config_name: 配置环境名称
    """
    try:
        from .utils.log_filter import apply_smart_filtering

        # 根据环境应用不同的过滤策略
        if config_name == 'development':
            apply_smart_filtering('development')
        elif config_name == 'production':
            apply_smart_filtering('production')
        else:
            # 测试环境或其他环境使用自定义配置
            apply_smart_filtering('custom')

    except ImportError as e:
        # 如果导入失败，使用简单的日志级别配置
        import logging
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logger = log_manager.get_logger()
        logger.warning(f"无法导入智能日志过滤器: {e}，使用基本配置")

# 确保其他模块可以从app包中导入db和create_app
__all__ = ['db', 'create_app']
