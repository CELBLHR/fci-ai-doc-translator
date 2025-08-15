from flask import Blueprint, render_template, jsonify
from app.utils.system_monitor import SystemMonitor
from flask_login import login_required
from flask import current_app

bp = Blueprint('monitor', __name__)

# 创建监控实例
system_monitor = None

def get_monitor():
    global system_monitor
    if system_monitor is None:
        system_monitor = SystemMonitor()
        system_monitor.start_monitoring(current_app._get_current_object())
    return system_monitor

@bp.route('/monitor')
@login_required
def monitor_page():
    """渲染监控页面"""
    get_monitor()  # 确保监控实例已创建
    return render_template('main/monitor.html')

@bp.route('/api/metrics')
@login_required
def get_metrics():
    """获取系统指标API"""
    monitor = get_monitor()
    return jsonify(monitor.get_metrics()) 