from app import db, create_app
from app.models.translation import Translation
import os


def export_dictionary(output_dir='../../temp'):
    """
    将词库中的词条导出为平行语料文件
    
    Args:
        output_dir: 输出目录路径，默认为temp
        
    Returns:
        tuple: (en_file_path, zh_file_path) 导出文件的路径
    """
    try:
        # 创建应用上下文
        app = create_app()
        with app.app_context():
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)

            # 设置输出文件路径
            en_file_path = os.path.join(output_dir, 'temp.en')
            zh_file_path = os.path.join(output_dir, 'temp.zh')

            # 从数据库获取所有翻译记录
            translations = Translation.query.order_by(Translation.id).all()

            # 分别写入英文和中文文件
            with open(en_file_path, 'w', encoding='utf-8') as en_file, \
                    open(zh_file_path, 'w', encoding='utf-8') as zh_file:

                for trans in translations:
                    # 去除可能的换行符，确保一行一个词条
                    en_text = trans.english.strip().replace('\n', ' ')
                    zh_text = trans.chinese.strip().replace('\n', ' ')

                    # 写入文件
                    en_file.write(en_text + '\n')
                    zh_file.write(zh_text + '\n')

            print(f"成功导出 {len(translations)} 条翻译记录")
            print(f"英文文件：{en_file_path}")
            print(f"中文文件：{zh_file_path}")

            return en_file_path, zh_file_path

    except Exception as e:
        print(f"导出过程中发生错误：{str(e)}")
        return None, None


if __name__ == '__main__':
    export_dictionary()