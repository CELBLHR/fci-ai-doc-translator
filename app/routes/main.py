from flask import Blueprint

# 创建main蓝图 - 这是一个指向app.views.main的链接
main = Blueprint('routes_main', __name__)

# 此文件仅作为从.routes.main导入main的兼容层
# 实际蓝图定义在app.views.main中 