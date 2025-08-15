# 管理脚本使用说明

本目录包含系统管理相关的脚本工具。

## 设置用户为管理员

### 脚本文件

- `set_admin.py` - Python脚本，用于将指定用户ID的用户设置为管理员
- `set_admin.bat` - Windows批处理文件，用于在Windows系统上运行set_admin.py
- `set_admin.sh` - Shell脚本，用于在Linux/Mac系统上运行set_admin.py

### 使用方法

#### Windows系统

```bash
# 基本用法
set_admin.bat <user_id>

# 强制执行（不询问确认）
set_admin.bat <user_id> -f
```

#### Linux/Mac系统

```bash
# 确保脚本有执行权限
chmod +x set_admin.sh

# 基本用法
./set_admin.sh <user_id>

# 强制执行（不询问确认）
./set_admin.sh <user_id> -f
```

#### 直接使用Python脚本

```bash
# 基本用法
python set_admin.py <user_id>

# 强制执行（不询问确认）
python set_admin.py <user_id> -f

# 查看帮助信息
python set_admin.py -h
```

### 功能说明

- 将指定ID的用户设置为管理员角色
- 如果管理员角色不存在，会自动创建
- 如果用户状态为pending，会自动设置为approved
- 脚本会检查用户是否已经是管理员，避免重复设置

### 注意事项

- 需要在项目根目录下运行这些脚本，或者使用提供的批处理/Shell脚本
- 需要安装项目所需的所有依赖
- 需要有数据库的访问权限 