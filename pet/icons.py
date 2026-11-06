"""Application avatar drawn from the active character's QPainter geometry."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QIcon, QPainter, QPixmap


def character_icon(renderer):
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        margin = max(1, size*.04)
        if hasattr(renderer, 'part_cache'):
            head, rect = renderer.part_cache['head']
            ratio = min((size-2*margin)/head.width(), (size-2*margin)/head.height())
            w, h = head.width()*ratio, head.height()*ratio
            painter.drawPixmap(QRectF((size-w)/2, (size-h)/2, w, h), head, QRectF(head.rect()))
        else:
            # A vector face occupies this portion of its 120x140 canvas.
            painter.setClipRect(QRectF(margin, margin, size-2*margin, size-2*margin))
            painter.translate(margin, margin)
            painter.scale((size-2*margin)/96, (size-2*margin)/96)
            painter.translate(-12, -3)
            renderer.paint(painter, 'idle', 1.2, 1)
        painter.end()
        icon.addPixmap(pixmap)
    return icon
