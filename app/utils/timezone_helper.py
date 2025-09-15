"""
时区处理工具类
统一处理系统中的时区转换，确保时间显示一致性
"""
from datetime import datetime
import pytz
from flask import current_app

def get_default_timezone():
    """获取系统默认时区"""
    try:
        # 尝试从应用配置中获取时区
        timezone_name = current_app.config.get('TIMEZONE', 'Asia/Shanghai')
        return pytz.timezone(timezone_name)
    except:
        # 如果获取失败，使用硬编码的默认时区
        return pytz.timezone('Asia/Shanghai')

def now_with_timezone():
    """获取当前时间（无时区信息，用于兼容MySQL DATETIME）"""
    # 返回不带tzinfo的时间，避免MySQL不支持时区导致写库失败
    return datetime.now()


def localize_datetime(dt, assume_timezone='UTC'):
    if dt is None:
        return None

    if dt.tzinfo is not None:
        return dt.astimezone(get_default_timezone())

    # 用指定时区来 localize
    tz = pytz.timezone(assume_timezone)
    return tz.localize(dt).astimezone(get_default_timezone())

def format_datetime(dt, format_str='%Y-%m-%d %H:%M:%S'):
    """
    格式化datetime对象为字符串
    
    Args:
        dt: datetime对象
        format_str: 格式化字符串
        
    Returns:
        格式化后的字符串
    """
    if dt is None:
        return ''
    
    # 确保datetime对象有时区信息
    localized_dt = localize_datetime(dt,assume_timezone='Asia/Shanghai')
    
    # 确保使用正确的时区格式化时间
    return localized_dt.strftime(format_str)

def parse_datetime(date_str):
    """
    解析日期字符串为datetime对象
    
    Args:
        date_str: 日期字符串，支持多种格式
        
    Returns:
        带有系统默认时区的datetime对象，解析失败返回None
    """
    if not date_str:
        return None
        
    dt = None
    
    # 尝试多种格式解析
    formats = [
        '%Y-%m-%d %H:%M:%S',  # 标准格式
        '%Y-%m-%dT%H:%M:%S',  # ISO格式无时区
        '%Y-%m-%d',           # 仅日期
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            continue
    
    # 尝试ISO格式解析
    if dt is None and 'T' in date_str:
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            pass
    
    if dt is None:
        return None
    
    # 如果解析出的datetime没有时区信息，添加默认时区
    if dt.tzinfo is None:
        dt = get_default_timezone().localize(dt)
        
    return dt

def datetime_to_isoformat(dt):
    """
    将datetime对象转换为ISO格式字符串
    
    Args:
        dt: datetime对象
        
    Returns:
        ISO格式的字符串
    """
    if dt is None:
        return ''
        
    # 确保datetime对象有时区信息
    localized_dt = localize_datetime(dt,assume_timezone='Asia/Shanghai')
    return localized_dt.isoformat()
# print(now_with_timezone())