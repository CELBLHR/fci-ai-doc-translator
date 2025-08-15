import sys
import fitz  # PyMuPDF
from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QPushButton, \
    QFileDialog
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QImage, QPixmap, QPainter


class PdfReader(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PDF Reader with Annotation Tool")
        self.setGeometry(100, 100, 800, 600)

        # Set up the PDF document
        self.pdf_document = None
        self.current_page = 0

        # Set up the graphics view and scene
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setCentralWidget(self.view)

        # Set up button to load PDF
        self.load_button = QPushButton("Open PDF", self)
        self.load_button.setGeometry(10, 10, 100, 40)
        self.load_button.clicked.connect(self.load_pdf)

        # Set up rectangle drawing tool
        self.drawing = False
        self.rect_start = None
        self.rect_item = None

    def load_pdf(self):
        """Load a PDF file and display the first page"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self.pdf_document = fitz.open(file_path)
            self.current_page = 0
            self.show_page(self.current_page)

    def show_page(self, page_num):
        """Render a specific page from the PDF"""
        if self.pdf_document:
            page = self.pdf_document.load_page(page_num)
            pix = page.get_pixmap()  # Render page to a pixmap
            image = QImage(pix.samples(), pix.width, pix.height, pix.stride(), QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(image)

            # Clear the scene and add the image
            self.scene.clear()
            self.scene.addPixmap(pixmap)

    def mousePressEvent(self, event):
        """Start drawing a rectangle on mouse press"""
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.rect_start = self.view.mapToScene(event.pos())  # Get the scene coordinates
            self.rect_item = QGraphicsRectItem(QRectF(self.rect_start, self.rect_start))
            self.rect_item.setPen(Qt.red)
            self.scene.addItem(self.rect_item)

    def mouseMoveEvent(self, event):
        """Update rectangle size while dragging"""
        if self.drawing and self.rect_item:
            rect_end = self.view.mapToScene(event.pos())
            self.rect_item.setRect(
                QRectF(self.rect_start, rect_end).normalized())  # Normalize to avoid negative width/height

    def mouseReleaseEvent(self, event):
        """Finalize rectangle when mouse is released"""
        if self.drawing:
            self.drawing = False
            rect_end = self.view.mapToScene(event.pos())
            # Here you can save the rectangle coordinates as annotations if needed
            print(f"Rectangle coordinates: {self.rect_start}, {rect_end}")

            # Optionally, save this annotation to the PDF as well:
            self.add_annotation(self.rect_start, rect_end)

    def add_annotation(self, start, end):
        """Add annotation to PDF"""
        if self.pdf_document:
            page = self.pdf_document.load_page(self.current_page)
            rect = fitz.Rect(start.x(), start.y(), end.x(), end.y())
            page.add_rect_annot(rect)
            self.pdf_document.save("annotated_output.pdf")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PdfReader()
    window.show()
    sys.exit(app.exec_())
