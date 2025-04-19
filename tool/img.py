from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QPainter, QPainterPath

def create_rounded_corner_image(input_path, output_path):
    pixmap = QPixmap(input_path)

    diameter = min(pixmap.width(), pixmap.height())
    output_pixmap = QPixmap(diameter, diameter)
    output_pixmap.fill(Qt.transparent)

    painter = QPainter(output_pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)

    path = QPainterPath()
    path.addEllipse(0, 0, diameter, diameter)
    painter.setClipPath(path)

    clipped_pixmap = pixmap.scaled(diameter, diameter, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    x_offset = (diameter - clipped_pixmap.width()) // 2
    y_offset = (diameter - clipped_pixmap.height()) // 2
    painter.drawPixmap(x_offset, y_offset, clipped_pixmap)

    painter.end()

    output_pixmap.save(output_path, format="PNG")

