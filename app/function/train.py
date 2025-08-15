import sys
import os
import time
import subprocess

# 设置 LibreOffice 路径
libreoffice_path = r"C:\Program Files\LibreOffice\program"
sys.path.insert(0, libreoffice_path)
os.environ['PYUNO_LIB_DIR'] = libreoffice_path

# 导入 uno 模块
try:
    import uno
    from com.sun.star.connection import NoConnectException
except ImportError as e:
    print("导入失败：请确认 PYTHONPATH 是否正确设置！")
    print("错误详情：", e)
    exit(1)

def start_libreoffice():
    """启动 LibreOffice 并监听 UNO"""
    soffice = os.path.join(libreoffice_path, "soffice.exe")
    if not os.path.exists(soffice):
        print(f"找不到 soffice.exe，路径错误：{soffice}")
        return False

    args = [
        soffice,
        "--headless",
        "--accept=socket,host=localhost,port=2002;urp;",
        "--norestore",
        "--nologo",
        "--nodefault"
    ]

    print("正在启动 LibreOffice...")
    process = subprocess.Popen(args)
    time.sleep(5)  # 给足够时间启动
    return True

def connect_to_lo(retries=8, delay=3):
    """尝试连接 LibreOffice，带重试机制"""
    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_context
    )

    for i in range(retries):
        try:
            print(f"尝试连接 LibreOffice（第 {i + 1} 次）...")
            ctx = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
            smgr = ctx.ServiceManager
            return ctx, smgr
        except NoConnectException as e:
            print("连接失败：", e)
            time.sleep(delay)
        except Exception as e:
            print("未知异常：", e)
            time.sleep(delay)

    print("无法连接到 LibreOffice，请检查是否正常运行。")
    return None, None

def main():
    print("开始连接 LibreOffice...")

    # Step 1: 尝试连接现有实例
    ctx, smgr = connect_to_lo()
    if not ctx or not smgr:
        # Step 2: 如果连接失败，尝试自动启动
        if not start_libreoffice():
            print("LibreOffice 启动失败")
            return

        # 再次尝试连接
        ctx, smgr = connect_to_lo()
        if not ctx or not smgr:
            print("仍然无法连接到 LibreOffice，结束程序。")
            return

    # Step 3: 获取桌面服务
    try:
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    except Exception as e:
        print("获取 Desktop 失败，可能是连接断开或权限问题。")
        print("错误详情：", e)
        return

    # Step 4: 创建 Writer 文档
    document = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, [])

    # Step 5: 插入文本
    text = document.Text
    cursor = text.createTextCursor()
    text.insertString(cursor, "Hello, this is a test from Python!", False)

    # Step 6: 保存文档（Windows 下建议使用绝对路径）
    output_path = "file:///D:/tmp/test_output.odt"
    document.storeAsURL(output_path, [])
    document.close(True)

    print(f"文档已保存至：{output_path.replace('file:///', '')}")

if __name__ == "__main__":
    main()