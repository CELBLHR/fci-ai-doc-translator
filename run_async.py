"""
异步优化版应用启动脚本
使用异步和多线程特性优化应用性能
"""
import os
import logging
import asyncio
import uvicorn
from hypercorn.config import Config
from hypercorn.asyncio import serve

from app import create_app, db
from app.utils.enhanced_task_queue import translation_queue
from app.utils.thread_pool_executor import thread_pool, TaskType
from app.utils.logger import get_logger

# 获取主应用日志记录器
logger = get_logger('app.main')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 创建应用实例
app = create_app('development')

# 配置ASGI服务器（Hypercorn）
config = Config()
config.bind = ["0.0.0.0:5000"]
config.worker_class = "asyncio"
config.workers = 2  # 根据可用CPU核心数调整
config.accesslog = "-"  # 输出到标准输出

async def setup_async_environment():
    """初始化异步环境"""
    try:
        from app import create_app, db
        from app.utils.enhanced_task_queue import translation_queue
        from app.utils.thread_pool_executor import thread_pool
        import psutil
        import platform
        import sys
        
        logger.info("开始初始化异步环境...")
        
        # 创建应用实例和上下文
        app = create_app('development')
        ctx = app.app_context()
        ctx.push()
        
        try:
            # 创建数据库表
            logger.info("正在创建数据库表...")
            db.create_all()
            logger.info("数据库表创建完成")
            
            # 启动任务队列处理器
            logger.info("正在启动任务队列处理器...")
            translation_queue.start_processor()
            
            # 记录诊断信息
            logger.info("系统信息:")
            logger.info(f"Python版本: {sys.version}")
            logger.info(f"平台: {platform.platform()}")
            logger.info(f"CPU核心数: {psutil.cpu_count()}")
            logger.info(f"可用内存: {psutil.virtual_memory().available / (1024*1024):.2f} MB")
            
            # 记录线程池状态
            pool_stats = thread_pool.get_stats()
            logger.info("线程池状态:")
            logger.info(f"最大工作线程数: {pool_stats['max_workers']}")
            logger.info(f"I/O密集型线程数: {pool_stats['io_bound_workers']}")
            logger.info(f"CPU密集型线程数: {pool_stats['cpu_bound_workers']}")
            
            # 记录任务队列状态
            queue_stats = translation_queue.get_queue_stats()
            logger.info("任务队列状态:")
            logger.info(f"最大并发任务数: {queue_stats['max_concurrent']}")
            logger.info(f"当前任务数: {queue_stats['total']}")
            
            logger.info("异步环境初始化完成")
            
        except Exception as e:
            logger.error(f"初始化过程中出错: {str(e)}", exc_info=True)
            raise
        finally:
            ctx.pop()
            
    except Exception as e:
        logger.error(f"设置异步环境失败: {str(e)}", exc_info=True)
        raise

async def cleanup_async_environment():
    """清理异步环境，关闭队列和线程池"""
    logger.info("正在清理异步环境...")
    
    # 停止任务队列处理器
    translation_queue.stop_processor()
    logger.info("翻译任务队列处理器已停止")
    
    # 关闭线程池
    thread_pool.shutdown()
    logger.info("线程池已关闭")
    
    logger.info("异步环境清理完成")

async def serve_app():
    """启动异步Web服务器"""
    logger.info("正在启动Hypercorn ASGI服务器...")
    
    # 设置环境
    await setup_async_environment()
    
    try:
        # 启动Hypercorn服务器
        await serve(app, config)
    finally:
        # 清理环境
        await cleanup_async_environment()

def run_with_uvicorn():
    """使用Uvicorn运行应用（备选方案）"""
    logger.info("正在启动Uvicorn ASGI服务器...")
    
    # 创建应用上下文并初始化数据库
    with app.app_context():
        db.create_all()
        logger.info("数据库表已创建")
    
    # 启动线程池和任务队列处理器
    thread_pool.initialize()
    translation_queue.start_processor()
    
    # 记录诊断信息
    try:
        # 记录线程池状态
        thread_pool_stats = thread_pool.get_stats()
        logger.info(f"线程池状态: 最大工作线程={thread_pool_stats['max_workers']}, "
                  f"IO工作线程={thread_pool_stats['io_bound_workers']}, "
                  f"CPU工作线程={thread_pool_stats['cpu_bound_workers']}")
        
        # 记录任务队列状态
        queue_stats = translation_queue.get_queue_stats()
        logger.info(f"任务队列状态: 等待任务={queue_stats['waiting']}, "
                  f"处理中任务={queue_stats['processing']}, "
                  f"最大并发任务={queue_stats['max_concurrent']}")
        
        # 记录Python版本和系统信息
        import sys
        import platform
        logger.info(f"Python版本: {sys.version}")
        logger.info(f"操作系统: {platform.platform()}")
        
        # 记录已加载的模块
        from app.function import ppt_translate
        logger.info("已加载主要模块: ppt_translate")
    except Exception as e:
        logger.error(f"记录诊断信息时出错: {str(e)}")
    
    # 定义Uvicorn启动和关闭回调
    def on_startup():
        logger.info("Uvicorn 服务器已启动")
    
    def on_shutdown():
        logger.info("Uvicorn 服务器正在关闭")
        translation_queue.stop_processor()
        thread_pool.shutdown()
    
    # 启动Uvicorn服务器
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level="info",
        on_startup=[on_startup],
        on_shutdown=[on_shutdown]
    )

if __name__ == "__main__":
    logger.info("多线程优先级异步系统正在启动...")
    
    # 选择服务器类型
    server_type = os.environ.get("SERVER_TYPE", "hypercorn").lower()
    
    if server_type == "uvicorn":
        # 使用Uvicorn运行（更稳定，但异步功能有限）
        run_with_uvicorn()
    else:
        # 使用Hypercorn运行（更强大的异步支持）
        asyncio.run(serve_app()) 