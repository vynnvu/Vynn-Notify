"""Export a contact sheet of the current articulated QPainter character."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pet.character_manager import load_character

app = QApplication([])
_, renderer = load_character('chibi_boy')
states = ('look', 'nap', 'jump', 'climb', 'sit', 'sleep', 'groom', 'stretch', 'dance', 'sad')
image = QImage(1200, 560, QImage.Format_ARGB32)
image.fill(QColor('#e8e5df'))
painter = QPainter(image)
for index, state in enumerate(states):
    painter.save()
    painter.translate((index % 5)*240 + 12, (index // 5)*280 + 10)
    painter.scale(1.8, 1.8)
    renderer.paint(painter, state, 1.2, 1)
    painter.restore()
painter.end()
image.save(str(ROOT / 'qpainter_actions_preview.png'))
print('Saved qpainter_actions_preview.png. Order:', ', '.join(states))
