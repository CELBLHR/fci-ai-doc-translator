#先展示截图，再下载图片，同时保留了原有的批量下载功能
import json
import os
import re
import shutil
import requests
import webbrowser
import subprocess
from urllib.parse import urlparse
import uuid
import sys
import platform


def search_products_by_ingredient(json_path, keyword):
    """
    根据成分关键词搜索JSON文件中的保健食品产品

    :param json_path: JSON文件路径
    :param keyword: 要搜索的成分关键词
    :return: 匹配的产品列表
    """
    # 读取JSON文件
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ 已加载JSON文件: {os.path.basename(json_path)}")
        print(f"📊 文件包含 {len(data)} 个产品")
    except Exception as e:
        print(f"❌ 加载JSON文件失败: {str(e)}")
        return []

    matched_products = []

    for product_name, product_info in data.items():
        ingredients = product_info.get('ingredient', '')

        # 跳过成分为空的产品
        if not ingredients:
            continue

        # 检查关键词是否出现在成分列表中（不区分大小写）
        if keyword.lower() in ingredients.lower():
            # 提取主要成分（最多前3个）
            main_ingredients = [ing.strip() for ing in ingredients.split(',')[:3]]
            main_ingredients_str = "、".join(main_ingredients) + ("等" if len(ingredients.split(',')) > 3 else "")

            matched_products.append({
                '产品名称': product_name,
                '主要成分': main_ingredients_str,
                '完整成分': ingredients,
                '截图路径': product_info.get('path', '无截图路径'),
                '原始数据': product_info  # 保存原始数据以便下载图片
            })

    return matched_products


def display_search_results(results, keyword):
    """显示搜索结果"""
    if not results:
        print(f"\n🔍 没有找到包含'{keyword}'的产品")
        return

    print(f"\n✅ 找到 {len(results)} 个包含'{keyword}'的产品：")
    print("=" * 80)
    for i, product in enumerate(results, 1):
        print(f"{i}. 【{product['产品名称']}】")
        print(f"   主要成分: {product['主要成分']}")
        print(f"   截图路径: {product['截图路径']}")
        print("-" * 80)

    return results  # 返回结果以便后续下载


def display_image(image_path):
    """展示图片"""
    if not image_path or image_path == '无截图路径':
        print("⚠️ 无截图路径，无法展示")
        return False

    # 如果是本地文件路径
    if os.path.exists(image_path):
        try:
            # 根据不同操作系统打开图片
            if platform.system() == 'Darwin':  # macOS
                subprocess.call(('open', image_path))
            elif platform.system() == 'Windows':  # Windows
                os.startfile(image_path)
            else:  # Linux
                subprocess.call(('xdg-open', image_path))
            return True
        except Exception as e:
            print(f"❌ 打开图片失败: {str(e)}")
            return False

    # 如果是URL
    try:
        # 尝试解析为URL
        parsed = urlparse(image_path)
        if parsed.scheme and parsed.netloc:  # 是有效的URL
            webbrowser.open(image_path)
            return True
        else:
            print(f"❌ 无效的图片路径: {image_path}")
            return False
    except Exception as e:
        print(f"❌ 打开图片失败: {str(e)}")
        return False


def download_image(product, download_dir):
    """下载单个产品的图片"""
    img_path = product.get('截图路径', '')
    product_name = product.get('产品名称', '未知产品')

    if not img_path or img_path == '无截图路径':
        print(f"⏭️ 跳过产品 '{product_name}' (无截图路径)")
        return False

    # 清理文件名
    safe_name = re.sub(r'[\\/*?:"<>|]', '', product_name)

    # 获取文件扩展名
    if os.path.exists(img_path):  # 本地文件路径
        ext = os.path.splitext(img_path)[1]
        dest_path = os.path.join(download_dir, f"{safe_name}{ext}")

        try:
            # 复制本地文件
            shutil.copy2(img_path, dest_path)
            print(f"✅ 已下载图片: {os.path.basename(dest_path)}")
            return True
        except Exception as e:
            print(f"❌ 下载图片失败: {product_name} - {str(e)}")
            return False
    else:  # 可能是URL
        try:
            # 尝试解析为URL
            parsed = urlparse(img_path)
            if parsed.scheme and parsed.netloc:  # 是有效的URL
                response = requests.get(img_path, stream=True)
                response.raise_for_status()

                # 从内容类型获取扩展名
                content_type = response.headers.get('content-type', '')
                ext = '.jpg'  # 默认
                if 'image/jpeg' in content_type:
                    ext = '.jpg'
                elif 'image/png' in content_type:
                    ext = '.png'
                elif 'image/gif' in content_type:
                    ext = '.gif'

                dest_path = os.path.join(download_dir, f"{safe_name}{ext}")

                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print(f"✅ 已下载图片: {os.path.basename(dest_path)}")
                return True
            else:
                print(f"❌ 无效的图片路径: {img_path}")
                return False
        except Exception as e:
            print(f"❌ 下载图片失败: {product_name} - {str(e)}")
            return False


def find_product_by_name(results, product_name):
    """根据产品名称查找产品"""
    exact_matches = []
    partial_matches = []

    # 清理输入的产品名称
    cleaned_input = product_name.strip().lower()

    for product in results:
        # 清理产品名称
        cleaned_product = product['产品名称'].strip().lower()

        # 精确匹配
        if cleaned_input == cleaned_product:
            exact_matches.append(product)

        # 部分匹配
        elif cleaned_input in cleaned_product:
            partial_matches.append(product)

    # 返回最佳匹配结果
    if exact_matches:
        return exact_matches[0]  # 返回第一个精确匹配
    elif partial_matches:
        return partial_matches[0]  # 返回第一个部分匹配
    else:
        return None


def download_selected_products(results, download_dir):
    """下载用户选择的产品图片"""
    if not results:
        print("⚠️ 没有可下载的产品图片")
        return

    # 创建下载目录
    os.makedirs(download_dir, exist_ok=True)
    print(f"📁 图片将下载到: {os.path.abspath(download_dir)}")

    # 显示产品列表
    print("\n可下载的产品列表:")
    for i, product in enumerate(results, 1):
        print(f"{i}. {product['产品名称']}")

    # 获取用户输入
    selected = input("\n请输入要下载的产品编号（多个用逗号分隔，或输入'all'下载全部）: ").strip()

    downloaded_count = 0
    total_selected = 0

    if selected.lower() == 'all':
        # 下载所有产品
        print("\n开始下载所有产品图片...")
        for product in results:
            if download_image(product, download_dir):
                downloaded_count += 1
        total_selected = len(results)
    else:
        # 处理用户选择的编号
        try:
            selected_indices = [int(idx.strip()) for idx in selected.split(',') if idx.strip().isdigit()]
            selected_indices = [idx for idx in selected_indices if 1 <= idx <= len(results)]

            if not selected_indices:
                print("⚠️ 未选择有效产品编号")
                return

            print("\n开始下载选中的产品图片...")
            for idx in selected_indices:
                product = results[idx - 1]
                if download_image(product, download_dir):
                    downloaded_count += 1
            total_selected = len(selected_indices)
        except Exception as e:
            print(f"❌ 输入格式错误: {str(e)}")
            return

    print(f"\n📊 下载完成: 成功 {downloaded_count}/{total_selected} 张图片")
    print(f"💾 图片保存位置: {os.path.abspath(download_dir)}")


def main():
    print("=" * 60)
    print("保健食品成分搜索与图片下载工具")
    print("=" * 60)

    # 手动输入JSON文件路径
    json_path = input("请输入JSON文件的完整路径: ").strip()

    # 验证文件是否存在
    while not os.path.exists(json_path):
        print(f"❌ 文件 '{json_path}' 不存在，请重新输入")
        json_path = input("请输入JSON文件的完整路径: ").strip()

    # 验证是否是JSON文件
    while not json_path.lower().endswith('.json'):
        print(f"❌ '{json_path}' 不是JSON文件，请重新输入")
        json_path = input("请输入JSON文件的完整路径: ").strip()

    while True:
        keyword = input("\n请输入要搜索的成分关键词（输入'q'退出）: ").strip()
        if keyword.lower() == 'q':
            print("👋 感谢使用，再见！")
            break

        if not keyword:
            print("⚠️ 请输入有效的关键词")
            continue

        results = search_products_by_ingredient(json_path, keyword)
        displayed_results = display_search_results(results, keyword)

        # 如果有匹配结果，询问用户操作
        if displayed_results:
            print("\n请选择操作:")
            print("1. 输入产品名称查看截图")
            print("2. 批量下载产品图片")
            print("3. 返回搜索")

            action = input("请输入操作编号 (1/2/3): ").strip()

            if action == '1':
                # 用户输入产品名称
                product_name = input("\n请输入要查看的产品名称: ").strip()
                if not product_name:
                    print("⚠️ 请输入产品名称")
                    continue

                # 查找产品
                product = find_product_by_name(displayed_results, product_name)

                if not product:
                    print(f"❌ 未找到产品: {product_name}")
                    continue

                print(f"\n✅ 找到产品: {product['产品名称']}")
                print(f"📄 成分: {product['完整成分']}")

                # 展示图片
                print("\n正在尝试打开产品截图...")
                if display_image(product['截图路径']):
                    print("👀 请在打开的窗口中查看产品截图")

                    # 询问是否下载
                    download_choice = input("\n是否下载此产品图片? (y/n): ").lower().strip()
                    if download_choice == 'y':
                        default_dir = os.path.join(os.path.dirname(json_path), f"{keyword}_产品图片")
                        download_dir = input(f"请输入下载目录 (回车使用默认目录 '{default_dir}'): ").strip()
                        if not download_dir:
                            download_dir = default_dir

                        # 下载图片
                        os.makedirs(download_dir, exist_ok=True)
                        if download_image(product, download_dir):
                            print(f"✅ 图片已保存到: {download_dir}")
                        else:
                            print("❌ 图片下载失败")

            elif action == '2':
                # 批量下载
                default_dir = os.path.join(os.path.dirname(json_path), f"{keyword}_产品图片")
                download_dir = input(f"请输入下载目录 (回车使用默认目录 '{default_dir}'): ").strip()
                if not download_dir:
                    download_dir = default_dir

                # 下载图片
                download_selected_products(displayed_results, download_dir)
        else:
            print("没有匹配的产品，无法操作")


if __name__ == "__main__":
    main()