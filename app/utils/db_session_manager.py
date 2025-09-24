"""
数据库会话管理工具
提供安全的会话处理方法，确保会话在异常情况下也能被正确关闭
"""
import logging
import time
from contextlib import contextmanager
from typing import Optional, Callable, Any, Dict, List
from flask import current_app
from sqlalchemy.pool import QueuePool
from sqlalchemy import inspect

logger = logging.getLogger(__name__)

@contextmanager
def safe_db_session(db, commit: bool = True):
    """
    安全的数据库会话上下文管理器，确保会话在异常情况下也能被正确关闭
    
    Args:
        db: SQLAlchemy实例
        commit: 是否在退出时提交会话
        
    Yields:
        数据库会话
    """
    try:
        yield db.session
        if commit:
            db.session.commit()
            logger.debug("数据库会话已提交")
    except Exception as e:
        db.session.rollback()
        logger.error(f"数据库会话回滚: {str(e)}")
        raise
    finally:
        db.session.remove()
        logger.debug("数据库会话已移除")

def with_db_session(commit: bool = True):
    """
    数据库会话装饰器，确保函数在执行时有一个安全的数据库会话
    
    Args:
        commit: 是否在函数执行成功后提交会话
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            from app import db
            with safe_db_session(db, commit=commit) as session:
                # 将会话作为关键字参数传递给被装饰的函数
                kwargs['session'] = session
                return func(*args, **kwargs)
        return wrapper
    return decorator

def execute_with_session(func: Callable, *args, commit: bool = True, **kwargs) -> Any:
    """
    在安全的会话环境中执行函数
    
    Args:
        func: 要执行的函数
        *args: 函数的位置参数
        commit: 是否在函数执行成功后提交会话
        **kwargs: 函数的关键字参数
        
    Returns:
        函数的返回值
    """
    from app import db
    with safe_db_session(db, commit=commit) as session:
        # 将会话作为关键字参数传递给函数
        kwargs['session'] = session
        return func(*args, **kwargs)

def get_db_stats() -> Dict[str, Any]:
    """
    获取数据库连接池统计信息
    
    Returns:
        连接池统计信息字典
    """
    try:
        from app import db
        engine = db.engine
        stats = {}
        
        # 尝试获取SQLAlchemy引擎信息
        try:
            stats['engine_name'] = engine.name if hasattr(engine, 'name') else "未知"
            stats['driver_name'] = engine.driver if hasattr(engine, 'driver') else "未知"
            # 隐藏密码
            url_str = str(engine.url)
            if ":" in url_str and "@" in url_str:
                parts = url_str.split("@")
                auth_parts = parts[0].split(":")
                if len(auth_parts) > 2:
                    masked_url = f"{auth_parts[0]}:***@{parts[1]}"
                    stats['url'] = masked_url
                else:
                    stats['url'] = "数据库URL (无法安全显示)"
            else:
                stats['url'] = "数据库URL (无法解析)"
        except Exception as e:
            logger.error(f"获取引擎信息失败: {str(e)}")
            stats['engine_info_error'] = str(e)
        
        # 尝试获取连接池统计信息
        try:
            if hasattr(engine, 'pool') and engine.pool is not None:
                pool = engine.pool
                
                # 检查是否是QueuePool类型
                if isinstance(pool, QueuePool):
                    # 获取基本连接池配置
                    stats['pool_config'] = {
                        'size': getattr(pool, '_pool_size', "未知"),
                        'max_overflow': getattr(pool, '_max_overflow', "未知"),
                        'timeout': getattr(pool, '_timeout', "未知"),
                        'recycle': getattr(pool, '_recycle', "未知"),
                        'pre_ping': getattr(pool, '_pre_ping', "未知")
                    }
                    
                    # 获取实时连接池状态
                    try:
                        stats['pool_size'] = pool.size() if hasattr(pool, 'size') else "不可用"
                    except Exception as e:
                        stats['pool_size'] = f"获取失败: {str(e)}"
                    
                    try:
                        stats['checkedin'] = pool.checkedin() if hasattr(pool, 'checkedin') else "不可用"
                    except Exception as e:
                        stats['checkedin'] = f"获取失败: {str(e)}"
                    
                    try:
                        stats['checkedout'] = pool.checkedout() if hasattr(pool, 'checkedout') else "不可用"
                    except Exception as e:
                        stats['checkedout'] = f"获取失败: {str(e)}"
                    
                    try:
                        stats['overflow'] = pool.overflow() if hasattr(pool, 'overflow') else "不可用"
                    except Exception as e:
                        stats['overflow'] = f"获取失败: {str(e)}"
                    
                    # 获取已检出连接详情
                    try:
                        if hasattr(pool, '_pool'):
                            # 安全获取连接池内部状态
                            checked_out = []
                            for conn in getattr(pool, '_checked_out', []):
                                if hasattr(conn, 'info'):
                                    info = conn.info.copy() if hasattr(conn.info, 'copy') else {}
                                    # 移除敏感信息
                                    if 'user' in info:
                                        del info['user']
                                    if 'password' in info:
                                        del info['password']
                                    checked_out.append(info)
                                else:
                                    checked_out.append({"connection": "信息不可用"})
                            
                            stats['checkedout_connections'] = checked_out
                        else:
                            stats['checkedout_connections'] = "连接池内部状态不可用"
                    except Exception as e:
                        stats['checkedout_connections'] = f"获取失败: {str(e)}"
                else:
                    stats['pool_type'] = pool.__class__.__name__
                    stats['pool_info'] = "非标准连接池，详细统计不可用"
            else:
                stats['error'] = "数据库引擎没有连接池或连接池未初始化"
        except Exception as e:
            logger.error(f"获取连接池信息失败: {str(e)}")
            stats['error'] = f"获取连接池信息失败: {str(e)}"
        
        return stats
    except Exception as e:
        logger.error(f"获取数据库统计信息失败: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return {
            'error': str(e)
        }

def optimize_db_pool():
    """
    优化数据库连接池配置
    
    根据当前应用负载和配置动态调整连接池参数
    """
    try:
        from app import db
        engine = db.engine
        
        if hasattr(engine, 'pool') and engine.pool is not None:
            pool = engine.pool
            
            # 获取当前配置
            current_pool_size = getattr(pool, '_pool_size', 5)
            current_max_overflow = getattr(pool, '_max_overflow', 10)
            current_timeout = getattr(pool, '_timeout', 30)
            current_recycle = getattr(pool, '_recycle', 3600)
            
            # 从应用配置获取优化设置
            config = current_app.config
            target_pool_size = config.get('SQLALCHEMY_POOL_SIZE', current_pool_size)
            target_max_overflow = config.get('SQLALCHEMY_MAX_OVERFLOW', current_max_overflow)
            target_timeout = config.get('SQLALCHEMY_POOL_TIMEOUT', current_timeout)
            target_recycle = config.get('SQLALCHEMY_POOL_RECYCLE', current_recycle)
            
            # 检查是否需要更新
            if (current_pool_size != target_pool_size or 
                current_max_overflow != target_max_overflow or
                current_timeout != target_timeout or
                current_recycle != target_recycle):
                
                logger.info(f"更新数据库连接池配置: pool_size={target_pool_size}, "
                           f"max_overflow={target_max_overflow}, timeout={target_timeout}, "
                           f"recycle={target_recycle}")
                
                # 注意：某些参数可能无法在运行时更改，这取决于SQLAlchemy版本
                # 这里仅尝试更新可以安全更改的参数
                if hasattr(pool, '_recycle'):
                    pool._recycle = target_recycle
                    logger.info(f"已更新连接回收时间: {target_recycle}秒")
                
                # 记录无法更改的参数
                logger.info("注意：pool_size和max_overflow参数无法在运行时更改，"
                           "需要重启应用才能生效")
                
                return True
            else:
                logger.debug("数据库连接池配置已是最优，无需更新")
                return False
        else:
            logger.warning("数据库引擎没有连接池或连接池未初始化，无法优化")
            return False
    except Exception as e:
        logger.error(f"优化数据库连接池失败: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return False

def recycle_idle_connections():
    """
    回收空闲连接
    
    主动回收长时间空闲的数据库连接，减少资源占用
    """
    try:
        from app import db
        engine = db.engine
        
        if hasattr(engine, 'pool') and engine.pool is not None:
            pool = engine.pool
            
            # 获取当前连接池状态
            before_stats = {
                'size': pool.size() if hasattr(pool, 'size') else None,
                'checkedin': pool.checkedin() if hasattr(pool, 'checkedin') else None,
                'checkedout': pool.checkedout() if hasattr(pool, 'checkedout') else None,
                'overflow': pool.overflow() if hasattr(pool, 'overflow') else None
            }
            
            # 尝试触发连接池回收机制
            if hasattr(pool, 'dispose'):
                logger.info("正在回收空闲数据库连接...")
                pool.dispose()
                
                # 获取回收后的状态
                after_stats = {
                    'size': pool.size() if hasattr(pool, 'size') else None,
                    'checkedin': pool.checkedin() if hasattr(pool, 'checkedin') else None,
                    'checkedout': pool.checkedout() if hasattr(pool, 'checkedout') else None,
                    'overflow': pool.overflow() if hasattr(pool, 'overflow') else None
                }
                
                # 计算回收了多少连接
                recycled = 0
                if before_stats['checkedin'] is not None and after_stats['checkedin'] is not None:
                    recycled = before_stats['checkedin'] - after_stats['checkedin']
                
                logger.info(f"已回收 {recycled} 个空闲数据库连接")
                return recycled
            else:
                logger.warning("连接池不支持回收操作")
                return 0
        else:
            logger.warning("数据库引擎没有连接池或连接池未初始化，无法回收连接")
            return 0
    except Exception as e:
        logger.error(f"回收空闲连接失败: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return 0

def setup_db_monitoring(app, interval=3600):
    """
    设置数据库监控
    
    定期检查数据库连接池状态并进行优化
    
    Args:
        app: Flask应用实例
        interval: 监控间隔（秒）
    """
    try:
        import threading
        
        def monitor_db_pool():
            with app.app_context():
                while True:
                    try:
                        # 获取连接池统计信息
                        stats = get_db_stats()
                        
                        # 记录当前状态
                        if 'error' not in stats:
                            logger.info(f"数据库连接池状态: "
                                      f"大小={stats.get('pool_size', '未知')}, "
                                      f"已检入={stats.get('checkedin', '未知')}, "
                                      f"已检出={stats.get('checkedout', '未知')}, "
                                      f"溢出={stats.get('overflow', '未知')}")
                            
                            # 检查连接池健康状态
                            checkedout = stats.get('checkedout', 0)
                            if isinstance(checkedout, int) and checkedout > 0.8 * stats.get('pool_size', 10):
                                logger.warning(f"数据库连接池使用率较高: {checkedout}/{stats.get('pool_size', '未知')}")
                                
                                # 尝试回收空闲连接
                                recycle_idle_connections()
                                
                                # 尝试优化连接池配置
                                optimize_db_pool()
                        else:
                            logger.error(f"获取数据库连接池状态失败: {stats['error']}")
                    
                    except Exception as e:
                        logger.error(f"数据库监控任务出错: {str(e)}")
                    
                    # 等待下一次监控
                    time.sleep(interval)
        
        # 启动监控线程
        monitor_thread = threading.Thread(target=monitor_db_pool, daemon=True)
        monitor_thread.start()
        
        logger.info(f"数据库监控已启动，监控间隔: {interval}秒")
        return monitor_thread
    
    except Exception as e:
        logger.error(f"设置数据库监控失败: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return None 