#!/bin/bash
# 设置用户为管理员的Shell脚本
# 使用方法：./set_admin.sh <user_id>

# 检查参数
if [ $# -lt 1 ]; then
    echo "错误: 请提供用户ID"
    echo "使用方法: ./set_admin.sh <user_id>"
    exit 1
fi

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "正在将用户ID $1 设置为管理员..."
python "$SCRIPT_DIR/set_admin.py" "$@"

# 检查执行结果
if [ $? -ne 0 ]; then
    echo "操作失败!"
    exit 1
else
    echo "操作成功完成!"
    exit 0
fi 