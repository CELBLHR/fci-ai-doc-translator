import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract

pdf_file = r"C:\Users\48846\Documents\pdf\FINAL_Role of HMOs in Preterm Nutrition Presentation_2.pdf"

# 将PDF文件转换为图像
pages = convert_from_path(pdf_file, 300)  # 300 DPI

# 打开PDF文件
doc = fitz.open(pdf_file)

# 遍历PDF中的每一页
for page_num in range(doc.page_count):
    page = doc.load_page(page_num)  # 获取每一页
    annotations = page.annots()  # 获取该页的所有注释

    if annotations:  # 如果有注释
        for annot in annotations:
            # 获取注释的矩形区域
            print(annot.type)
            rect = annot.rect
            print(f"注释区域（矩形）：{rect}")

            # 获取注释类型，并根据类型进行处理
            if annot.type[0] in [8, 9, 4]:  # 高亮（8）、圈（9）、下划线（4）
                # 获取PDF页面的坐标
                rect = annot.rect
                # 转换为图像坐标系（如果需要的话）
                img_width, img_height = pages[page_num].size  # 获取图像大小
                pdf_width = page.rect.width
                pdf_height = page.rect.height

                # 缩放注释区域坐标以匹配图像尺寸
                scale_x = img_width / pdf_width
                scale_y = img_height / pdf_height
                crop_box = (
                    rect.x0 * scale_x, rect.y0 * scale_y,  # 左上角
                    rect.x1 * scale_x, rect.y1 * scale_y   # 右下角
                )

                # 裁剪图像（将坐标转换为整数）
                cropped_image = pages[page_num].crop((int(crop_box[0]), int(crop_box[1]), int(crop_box[2]), int(crop_box[3])))

                # 使用pytesseract进行OCR识别
                text = pytesseract.image_to_string(cropped_image)
                print(f"提取的文本：{text}")
