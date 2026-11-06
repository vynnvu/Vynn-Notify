"""Generate the EXE icon from the authored Chibi QPainter head."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pet.character_manager import load_character
from pet.icons import character_icon

app = QApplication([])
_, renderer = load_character('chibi_boy')
icon = character_icon(renderer)
target = ROOT / 'assets' / 'chibi.ico'
target.parent.mkdir(exist_ok=True)
if not icon.pixmap(256, 256).save(str(target), 'ICO'):
    raise RuntimeError('Could not create EXE icon')
print('Saved assets/chibi.ico')
