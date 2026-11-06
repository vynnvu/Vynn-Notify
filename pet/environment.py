"""Desktop versus app interiors, z-order and headroom for standable edges."""
from PySide6.QtCore import QRectF


class Scene:
    def __init__(self, windows, surfaces, metadata):
        self.windows = list(windows)
        self.surfaces = surfaces
        self.metadata = metadata
        self.rank = {key: i for i, (key, _) in enumerate(windows)}

    def covered(self, key, x, y):
        owner = self.metadata.get(key, {}).get('owner', key)
        rank = self.rank.get(owner, len(self.windows))
        return any(rect.contains(round(x), round(y)) for _, rect in self.windows[:rank])

    def inside_owner(self, x, y, perch=None):
        info = self.metadata.get(perch, {})
        if info.get('space') == 'inside':
            return info['owner']
        for owner, rect in self.windows:
            if rect.left() < x < rect.right() and rect.top() < y < rect.bottom():
                if any(i.get('owner') == owner and i.get('space') == 'inside' for i in self.metadata.values()):
                    return owner
                return None
        return None

    def headroom(self, key, x, top, width, height):
        body = QRectF(x-width/2+1, top-height, max(1, width-2), max(1, height-1))
        return not any(other != key and self.metadata.get(other, {}).get('solid', False)
                       and not self.covered(other, rect.center().x(), rect.top())
                       and body.intersects(QRectF(rect)) for other, rect in self.surfaces)

    def standable(self, key, x, top, width, height, inside=None, entering=None):
        info = self.metadata.get(key, {})
        if self.covered(key, x, top):
            return False
        if info.get('space') == 'inside' and info.get('owner') not in (inside, entering):
            return False
        if inside is not None and info.get('owner') != inside:
            # Objects behind the window's interior cannot catch the pet.
            return False
        return self.headroom(key, x, top, width, height)
