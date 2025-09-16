import os
import json
import mimetypes
from urllib.parse import quote  # 用于在生成 URL 时编码中文
from flask import Blueprint, request, jsonify, current_app, send_file
from flask_login import login_required

ingredient = Blueprint('ingredient', __name__)

# 缓存JSON数据
_cached_registration_data = None
_cached_filing_data = None
_cached_combined_data = None
_cache_registration_file_path = None
_cache_filing_file_path = None

def load_registration_data():
    """加载保健食品注册数据"""
    global _cached_registration_data, _cache_registration_file_path
    json_file_path = os.path.join(current_app.root_path, 'Ingredient_Search', '保健食品注册.json')
    json_file_path = os.path.abspath(json_file_path)
    if _cached_registration_data and _cache_registration_file_path == json_file_path:
        return _cached_registration_data
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            _cached_registration_data = json.load(f)
            _cache_registration_file_path = json_file_path
            return _cached_registration_data
    except Exception as e:
        current_app.logger.error(f"加载注册JSON文件失败: {e}")
        return {}

def load_filing_data():
    """加载保健食品备案数据"""
    global _cached_filing_data, _cache_filing_file_path
    json_file_path = os.path.join(current_app.root_path, 'Ingredient_Search', '保健食品备案.json')
    json_file_path = os.path.abspath(json_file_path)
    if _cached_filing_data and _cache_filing_file_path == json_file_path:
        return _cached_filing_data
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            _cached_filing_data = json.load(f)
            _cache_filing_file_path = json_file_path
            return _cached_filing_data
    except Exception as e:
        current_app.logger.error(f"加载备案JSON文件失败: {e}")
        return {}

def load_both_ingredient_data():
    """加载保健食品注册和备案数据并合并"""
    global _cached_combined_data
    if _cached_combined_data:
        return _cached_combined_data

    registration_data = load_registration_data()
    filing_data = load_filing_data()

    combined_data = {}
    for product_name, product_info in registration_data.items():
        combined_data[product_name] = {**product_info, 'data_source': '注册'}
    for product_name, product_info in filing_data.items():
        if product_name in combined_data:
            product_name = f"{product_name}(备案)"
        combined_data[product_name] = {**product_info, 'data_source': '备案'}

    _cached_combined_data = combined_data
    return combined_data

def _normalize_rel_url_path(p: str) -> str:
    """用于生成URL：把 \→/，去掉 ./ 前缀，不做安全判断（仅用于URL展示）"""
    if not p:
        return p
    p = p.replace('\\', '/')
    while p.startswith('./'):
        p = p[2:]
    return p

def get_image_url(image_path):
    """将本地图片路径转换为可访问的URL（供前端展示）"""
    if not image_path or image_path == '无截图路径':
        return None
    if not os.path.isabs(image_path):
        # 统一为 URL 友好的相对路径，并对中文做编码
        rel_url_path = _normalize_rel_url_path(image_path)
        return f"/ingredient/image/{quote(rel_url_path)}"
    return None

@ingredient.route('/api/ingredient/search', methods=['GET'])
@login_required
def search_ingredient():
    """搜索保健食品成分API"""
    try:
        keyword = request.args.get('keyword', '').strip()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 12))
        data_source = request.args.get('data_source', 'all')

        if not keyword:
            return jsonify({'success': False, 'message': '请输入搜索关键词'}), 400

        if data_source == 'registration':
            data = {k: {**v, 'data_source': '注册'} for k, v in load_registration_data().items()}
        elif data_source == 'filing':
            data = {k: {**v, 'data_source': '备案'} for k, v in load_filing_data().items()}
        else:
            data = load_both_ingredient_data()

        if not data:
            return jsonify({'success': False, 'message': '数据加载失败'}), 500

        matched_products = []
        for product_name, product_info in data.items():
            ingredients = product_info.get('ingredient', '') or ''
            data_source_label = product_info.get('data_source', '未知')
            if keyword.lower() in ingredients.lower() or keyword.lower() in product_name.lower():
                if ingredients:
                    parts = [ing.strip() for ing in ingredients.split(',')]
                    main_ingredients = parts[:3]
                    main_ingredients_str = "、".join(main_ingredients) + ("等" if len(parts) > 3 else "")
                else:
                    main_ingredients_str = "无成分信息"

                image_path = product_info.get('path', '无截图路径')
                image_url = get_image_url(image_path) if image_path != '无截图路径' else None

                matched_products.append({
                    '产品名称': product_name,
                    '主要成分': main_ingredients_str,
                    '完整成分': ingredients,
                    '截图路径': image_path,
                    '图片URL': image_url,
                    '数据源': data_source_label,
                    'detail_url': product_info.get('detail_url', '')
                })

        total = len(matched_products)
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_products = matched_products[start_index:end_index]

        return jsonify({
            'success': True,
            'data': paginated_products,
            'pagination': {
                'current_page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        current_app.logger.error(f"搜索出错: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'搜索出错: {str(e)}'}), 500

def _resolve_safe_path(rel_path: str, base_dir: str) -> str:
    """
    将传入的相对路径规范化为 base_dir 下的绝对路径，并做安全校验。
    兼容反斜杠与 './' 前缀；禁止越权访问（..、绝对路径）。
    """
    rel_path = (rel_path or '').replace('\\', '/')
    while rel_path.startswith('./'):
        rel_path = rel_path[2:]

    rel_path_norm = os.path.normpath(rel_path)

    if os.path.isabs(rel_path_norm) or rel_path_norm.startswith('..'):
        raise ValueError('非法路径')

    full_path = os.path.abspath(os.path.join(base_dir, rel_path_norm))

    base_dir_abs = os.path.abspath(base_dir)
    if not (full_path == base_dir_abs or full_path.startswith(base_dir_abs + os.sep)):
        raise ValueError('非法路径')

    return full_path

@ingredient.route('/image/<path:image_path>')
@login_required
def serve_ingredient_image(image_path):
    """提供成分图片访问（支持子目录与中文文件名）"""
    try:
        base_dir = os.path.join(current_app.root_path, 'Ingredient_Search')
        full_image_path = _resolve_safe_path(image_path, base_dir)

        if not os.path.exists(full_image_path) or not os.path.isfile(full_image_path):
            return jsonify({'error': '图片不存在'}), 404

        return send_file(full_image_path)
    except ValueError:
        return jsonify({'error': '非法路径'}), 400
    except Exception as e:
        current_app.logger.error(f"提供图片出错: {e}", exc_info=True)
        return jsonify({'error': '无法提供图片'}), 500

# —— 下载接口（两种写法都支持）——

@ingredient.route('/api/ingredient/download', methods=['GET'])
@login_required
def download_ingredient_file_qs():
    """下载/预览（QueryString版）：/api/ingredient/download?path=..."""
    try:
        raw = request.args.get('path', '')
        return _download_impl(raw)
    except Exception as e:
        current_app.logger.error(f"下载文件出错: {e}", exc_info=True)
        return jsonify({'error': f'无法下载文件: {str(e)}'}), 500

@ingredient.route('/api/ingredient/download/<path:image_path>', methods=['GET'])
@login_required
def download_ingredient_file(image_path):
    """下载/预览（路径段版，保留兼容）"""
    try:
        return _download_impl(image_path)
    except Exception as e:
        current_app.logger.error(f"下载文件出错: {e}", exc_info=True)
        return jsonify({'error': f'无法下载文件: {str(e)}'}), 500

def _download_impl(rel_path: str):
    """核心下载逻辑：统一安全解析与返回"""
    print(rel_path)
    base_dir = os.path.join(current_app.root_path, 'Ingredient_Search')
    print(base_dir)
    # 统一分隔符 + 去掉 ./ 前缀
    rel_path = (rel_path or '').replace('\\', '/')
    while rel_path.startswith('./'):
        rel_path = rel_path[2:]

    full_path = _resolve_safe_path(rel_path, base_dir)
    print(full_path)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return jsonify({'error': '文件不存在'}), 404

    filename = os.path.basename(full_path)
    guessed_mime, _ = mimetypes.guess_type(full_path)
    download_flag = request.args.get('download', '1') != '0'

    return send_file(
        full_path,
        as_attachment=download_flag,
        download_name=filename,
        mimetype=guessed_mime
    )
