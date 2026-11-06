"""Losslessly trace opaque GIF pixels into coloured QPainter rectangles.

Run with the project venv: python tools/trace_gif.py [source.png or source.gif]
Only used to author vector data; the application does not load the source.
"""
import hashlib
import json
from pathlib import Path
import sys
from PySide6.QtGui import QImage, QImageReader

ROOT = Path(__file__).resolve().parents[1]


def trace(source):
    reader = QImageReader(str(source))
    frames = []
    canvas = None
    while reader.canRead():
        image = reader.read().convertToFormat(QImage.Format_RGBA8888)
        if image.isNull():
            raise ValueError(reader.errorString())
        canvas = [image.width(), image.height()]
        raw, stride = image.constBits(), image.bytesPerLine()
        palette, lookup, rectangles = [], {}, []
        active = {}
        left, top, right, bottom = image.width(), image.height(), 0, 0
        vl, vt, vr, vb = image.width(), image.height(), 0, 0
        for y in range(image.height()):
            current = {}
            x = 0
            while x < image.width():
                offset = y * stride + 4 * x
                color = tuple(raw[offset:offset + 4])
                start = x
                x += 1
                while x < image.width() and tuple(raw[y * stride + 4*x:y * stride + 4*x + 4]) == color:
                    x += 1
                if color[3] == 0:
                    continue
                left, right = min(left, start), max(right, x)
                top, bottom = min(top, y), max(bottom, y + 1)
                if color[3] > 32:
                    vl, vr = min(vl, start), max(vr, x)
                    vt, vb = min(vt, y), max(vb, y+1)
                if color not in lookup:
                    lookup[color] = len(palette)
                    palette.append(color)
                    rectangles.append([])
                index = lookup[color]
                key = (index, start, x - start)
                if key in active:
                    rect = active[key]
                    rect[3] += 1
                else:
                    rect = [start, y, x - start, 1]
                    rectangles[index].append(rect)
                current[key] = rect
            active = current
        frames.append(dict(delay_ms=max(20, reader.nextImageDelay()),
                           bounds=[left, top, right - left, bottom - top],
                           visible_bounds=[vl, vt, vr-vl, vb-vt],
                           palette=palette, rectangles=rectangles))
    if not frames:
        raise ValueError('No GIF frames found')
    return dict(format=1, canvas=canvas, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), frames=frames)


if __name__ == '__main__':
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / 'chibi-boy.png'
    output = ROOT / 'characters/chibi_boy/vector.json'
    data = trace(source)
    output.write_text(json.dumps(data, separators=(',', ':')), encoding='utf-8')
    print(f'Traced {len(data["frames"])} frames to {output.name}: {output.stat().st_size:,} bytes')
