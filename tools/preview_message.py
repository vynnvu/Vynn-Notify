"""Export light/dark message cards for visual review."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor, QFontDatabase

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pet.message import MessageBubble
from pet.life import DEFAULTS

app = QApplication([])
# Offscreen Qt does not enumerate Windows fonts automatically.
for name in ('segoeui.ttf', 'seguisb.ttf'):
    font = Path(os.getenv('WINDIR', 'C:/Windows')) / 'Fonts' / name
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))
out = QImage(660, 230, QImage.Format_ARGB32)
out.fill(QColor('#e5e3ea'))
painter = QPainter(out)
for index, theme in enumerate(('light', 'dark')):
    card = MessageBubble(lambda: None)
    card.configure(dict(DEFAULTS, message_theme=theme, message_width=300, message_font=15), 'Vynn')
    card.setText('Chào bạn! Nghỉ mắt một chút nhé.\nMình vẫn ở đây cùng bạn.')
    card.show()
    app.processEvents()
    card.point_to(card.x()+150)
    painter.drawPixmap(15+index*325, 20, card.grab())
    card.close()
painter.end()
out.save(str(ROOT / 'message_preview.png'))
