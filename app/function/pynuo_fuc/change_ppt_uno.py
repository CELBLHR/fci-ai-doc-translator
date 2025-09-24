import uno # type: ignore
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from read_ppt_page_uno import connect_to_libreoffice, read_slide_texts, extract_text_and_attrs

def clone_texts_in_ppt(context, ppt_path, save_path, page_index=0, translated_path="translated.txt"):
    desktop = context.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", context)
    file_url = uno.systemPathToFileUrl(os.path.abspath(ppt_path))
    properties = ()
    presentation = desktop.loadComponentFromURL(file_url, "_blank", 0, properties)
    slides = presentation.getDrawPages()

    # 只提取指定页内容和格式
    all_content_attrs = read_slide_texts(context, ppt_path, page_index=page_index)

    # 读取翻译片段
    with open(translated_path, "r", encoding="utf-8") as f:
        translated_fragments = [line.rstrip("\n") for line in f]
    frag_idx = 0

    # 收集检测用表格数据
    table_rows = []

    for i, slide_content_attrs in enumerate(all_content_attrs):
        slide = slides.getByIndex(page_index)
        for j, (content_queue, attr_queue) in enumerate(slide_content_attrs):
            shape = slide.getByIndex(j)
            text = shape.getText()
            cursor = text.createTextCursor()
            cursor.gotoEnd(False)  # 移到文本末尾
            # 先写入原文
            for frag, attrs in zip(content_queue, attr_queue):
                color, underline, bold, escapement, font_size = attrs
                text.insertString(cursor, frag, False)
                cursor.goLeft(len(frag), True)
                cursor.CharColor = color
                cursor.CharUnderline = 1 if underline else 0
                cursor.CharWeight = 150 if bold else 100
                cursor.CharEscapement = escapement
                if escapement != 0:
                    cursor.CharHeight = font_size * 0.6
                else:
                    cursor.CharHeight = font_size
                cursor.gotoEnd(False)
            # 收集译文及格式
            frag_attr_trans = []
            for frag, attrs in zip(content_queue, attr_queue):
                if frag_idx < len(translated_fragments):
                    trans_frag = translated_fragments[frag_idx]
                    frag_idx += 1
                else:
                    trans_frag = ""
                frag_attr_trans.append((trans_frag, attrs))
                color, underline, bold, escapement, font_size = attrs
                table_rows.append((frag, trans_frag, color, underline, bold, escapement, font_size))
            # 手动递减字号写入译文，直到适应文本框高度
            box_height = shape.getSize().Height
            min_font_size = 8
            # 取原字号最小值作为起点
            font_sizes = [attrs[-1] for _, attrs in frag_attr_trans if attrs[-1] > 0]
            if not font_sizes:
                font_size = 18
            else:
                font_size = min(font_sizes)
            while font_size >= min_font_size:
                # 先清除原有译文（只保留原文）
                text.setString("")
                cursor.gotoEnd(False)
                # 重新写入原文
                for frag, attrs in zip(content_queue, attr_queue):
                    color, underline, bold, escapement, orig_font_size = attrs
                    text.insertString(cursor, frag, False)
                    cursor.goLeft(len(frag), True)
                    cursor.CharColor = color
                    cursor.CharUnderline = 1 if underline else 0
                    cursor.CharWeight = 150 if bold else 100
                    cursor.CharEscapement = escapement
                    if escapement != 0:
                        cursor.CharHeight = orig_font_size * 0.6
                    else:
                        cursor.CharHeight = orig_font_size
                    cursor.gotoEnd(False)
                # 写入译文
                for trans_frag, attrs in frag_attr_trans:
                    color, underline, bold, escapement, _ = attrs
                    text.insertString(cursor, trans_frag, False)
                    cursor.goLeft(len(trans_frag), True)
                    cursor.CharColor = color
                    cursor.CharUnderline = 1 if underline else 0
                    cursor.CharWeight = 150 if bold else 100
                    cursor.CharEscapement = escapement
                    if escapement != 0:
                        cursor.CharHeight = font_size * 0.6
                    else:
                        cursor.CharHeight = font_size
                    cursor.gotoEnd(False)
                # 检查文本高度是否适应
                # 这里用文本框内容行数*字号估算高度（简化版）
                total_lines = (len(content_queue) + len(frag_attr_trans))
                if font_size * 1.5 * total_lines < box_height:
                    break
                font_size -= 1

    # 输出检测表格
    print(f"{'原文片段':<30} | {'译文片段':<30} | {'颜色':<8} | {'下划线':<4} | {'加粗':<4} | {'上下标':<6} | {'字号':<6}")
    print('-'*90)
    for row in table_rows:
        frag, trans_frag, color, underline, bold, escapement, font_size = row
        print(f"{frag:<30} | {trans_frag:<30} | {color:<8} | {str(underline):<4} | {str(bold):<4} | {escapement:<6} | {font_size:<6}")

    # 保存到新文件
    file_url_save = uno.systemPathToFileUrl(os.path.abspath(save_path))
    presentation.storeToURL(file_url_save, ())
    print(f"已保存到 {save_path}")

def main():
    context = connect_to_libreoffice()
    clone_texts_in_ppt(context, "F:/pptxTest/pyuno/test.pptx", "F:/pptxTest/pyuno/test_clone.pptx", page_index=0)

if __name__ == "__main__":
    main()
