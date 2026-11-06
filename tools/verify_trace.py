"""Compare native QPainter geometry against the current PNG reference."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import hashlib
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QImageReader, QPainter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pet.character_manager import load_character

app = QApplication([])
source = ROOT.parent / 'chibi-boy.png'
_, renderer = load_character('chibi_boy')
assert hashlib.sha256(source.read_bytes()).hexdigest() == renderer.source_sha256
reader = QImageReader(str(source))
index = 0
while reader.canRead():
    original = reader.read().convertToFormat(QImage.Format_ARGB32_Premultiplied)
    rendered = QImage(*renderer.canvas, QImage.Format_ARGB32_Premultiplied)
    rendered.fill(0)
    painter = QPainter(rendered)
    renderer.paint_native(painter, index)
    painter.end()
    a, b = original.constBits(), rendered.constBits()
    mismatches = 0
    max_error = 0
    for pos in range(0, original.sizeInBytes(), 4):
        if a[pos:pos+4] != b[pos:pos+4]:
            mismatches += 1
            max_error = max(max_error, *(abs(a[pos+c]-b[pos+c]) for c in range(4)))
    # QPainter and QImage conversion can round premultiplied alpha differently.
    assert max_error <= 1, (index, mismatches, max_error)
    print(f'Frame {index + 1}: maximum channel error {max_error}/255; {mismatches} pixels with rounding differences')
    if index == 0:
        rendered.save(str(ROOT / 'qpainter_preview.png'))
    index += 1
assert index == len(renderer.vector_frames) == 1
print('PASS: native QPainter geometry matches chibi-boy.png')
