"""Pixel-faithful QPainter character rig based on chibi-boy.png.

Source geometry is split into articulated parts. Facing changes limb motion,
never mirrors the asymmetric hairstyle or the C printed on the shorts.
"""
import json
from math import sin, pi
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QTransform, QPen, QPixmap, QImage


class ChibiBoyRenderer:
    grounded = True
    parts = ('left_leg', 'right_leg', 'shorts', 'left_arm', 'right_arm', 'torso', 'head')

    def __init__(self, spec):
        data = json.loads(Path(__file__).with_name('vector.json').read_text(encoding='utf-8'))
        self.canvas = data['canvas']
        self.source_sha256 = data['source_sha256']
        self.vector_frames = []
        self.duration, self.ends, self.bounds = 0.0, [], []
        self.rig = {part: [] for part in self.parts}
        for frame in data['frames']:
            layers = []
            for rgba, rectangles in zip(frame['palette'], frame['rectangles']):
                color = QColor(*rgba)
                path = QPainterPath()
                path.setFillRule(Qt.WindingFill)
                partition = {part: QPainterPath() for part in self.parts}
                for x, y, w, h in rectangles:
                    path.addRect(x, y, w, h)
                    if self.vector_frames:
                        continue
                    if y+h <= 690:
                        partition['head'].addRect(x, y, w, h)
                        continue
                    # Most spans do not cross a seam: avoid allocating sets,
                    # sorting coordinates and nested loops for those pixels.
                    xs = [x] + [cut for cut in (510, 530, 625, 730, 750) if x < cut < x+w] + [x+w]
                    ys = [y] + [cut for cut in (690, 930, 980, 1045) if y < cut < y+h] + [y+h]
                    for x1, x2 in zip(xs, xs[1:]):
                        for y1, y2 in zip(ys, ys[1:]):
                            part = ('head' if y1 < 690 else
                                    ('left_leg' if x1 < 625 else 'right_leg') if y1 >= 1045 else
                                    'shorts' if y1 >= 980 else
                                    ('left_arm' if x1 < 510 else 'right_arm' if x1 >= 750 else 'shorts') if y1 >= 930 else
                                    'left_arm' if x1 < 530 else
                                    'right_arm' if x1 >= 730 else 'torso')
                            partition[part].addRect(x1, y1, x2-x1, y2-y1)
                layers.append((color, path))
                if not self.vector_frames:
                    for part, shape in partition.items():
                        if not shape.isEmpty():
                            shape.setFillRule(Qt.WindingFill)
                            self.rig[part].append((color, shape))
            self.vector_frames.append(layers)
            self.bounds.append(frame.get('visible_bounds', frame['bounds']))
            self.duration += frame['delay_ms'] / 1000
            self.ends.append(self.duration)
        b = self.bounds[0]
        self.scale = min(120/b[2], 140/b[3])
        self.center_x = b[0] + b[2]/2
        self.part_bounds = {}
        for part, layers in self.rig.items():
            rect = QRectF()
            for color, shape in layers:
                if color.alpha() > 32:
                    rect = rect.united(shape.boundingRect())
            self.part_bounds[part] = rect
        # Rasterize authored QPainter paths once per part. Animation only moves
        # these caches, rather than replaying 50,000 source colours every tick.
        self.part_cache = {}
        for part, layers in self.rig.items():
            rect = self.part_bounds[part].adjusted(-2, -2, 2, 2).toAlignedRect()
            tile = QPixmap(rect.size())
            tile.fill(Qt.transparent)
            painter = QPainter(tile)
            painter.translate(-rect.left(), -rect.top())
            painter.setPen(Qt.NoPen)
            for color, shape in layers:
                painter.setBrush(color)
                painter.drawPath(shape)
            painter.end()
            self.part_cache[part] = (tile, rect)

    def paint_native(self, painter, index=0):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(Qt.NoPen)
        for color, path in self.vector_frames[index]:
            painter.setBrush(color)
            painter.drawPath(path)
        painter.restore()

    @staticmethod
    def transform(x, y, angle=0, dy=0, sy=1):
        t = QTransform()
        t.translate(x, y + dy)
        t.rotate(angle)
        t.scale(1, sy)
        t.translate(-x, -y)
        return t

    def pose(self, state, tick, facing):
        transforms = {part: QTransform() for part in self.parts}
        wave = sin(tick*(7 if state == 'walk' else 5))
        arms, legs, head_y, body_y = [0, 0], [0, 0], 0, 0
        if state == 'walk':
            arms = [wave*18*facing, -wave*18*facing]
            legs = [-wave*13*facing, wave*13*facing]
            head_y = -abs(wave)*5
            body_y = -abs(wave)*3
        elif state in ('jump', 'fall'):
            arms = [38, -38] if state == 'jump' else [65, -65]
            legs = [-13, 15] if state == 'jump' else [-7, 7]
        elif state in ('climb', 'hang'):
            arms = [150+wave*8, -150+wave*8] if state == 'climb' else [165, -165]
            legs = [wave*12, -wave*12] if state == 'climb' else [-8, 8]
        elif state == 'sit':
            head_y, body_y = 135, 85
            arms = [-12+sin(tick*2)*2, 12-sin(tick*2)*2]
            for part, x, angle in (('left_leg', 565, 65), ('right_leg', 690, -65)):
                transforms[part] = self.transform(x, 1045, angle=angle, dy=20, sy=.65)
            transforms['shorts'] = self.transform(625, 1045, dy=15, sy=.75)
        elif state == 'sleep':
            head_y, body_y = 90, 65
            arms = [-18, 18]
            for part, x in (('left_leg', 565), ('right_leg', 690)):
                transforms[part] = self.transform(x, 1180, sy=.65)
            transforms['shorts'] = self.transform(625, 1045, dy=20, sy=.8)
        elif state == 'sad':
            head_y, body_y = 205, 145
            arms = [-25, 25]
            for part, x, angle in (('left_leg', 565, 62), ('right_leg', 690, -62)):
                transforms[part] = self.transform(x, 1045, angle=angle, dy=40, sy=.55)
            transforms['shorts'] = self.transform(625, 1045, dy=35, sy=.65)
        elif state == 'groom':
            arms = [158+sin(tick*3)*12, 0]
            head_y = 5
        elif state == 'high_five':
            arms = [0, -140+sin(tick*4)*4]
        elif state == 'stretch':
            lift = sin(tick*2)*4
            arms = [100+lift, -100-lift]
            head_y, body_y = -3, -2
        elif state == 'dance':
            arms = [80+wave*25, -80+wave*25]
            legs = [wave*5, -wave*5]
            head_y = -abs(wave)*8
        transforms['left_arm'] = self.transform(530, 740, arms[0], body_y)
        transforms['right_arm'] = self.transform(730, 740, arms[1], body_y)
        if state not in ('sit', 'sleep', 'sad'):
            transforms['left_leg'] = self.transform(565, 1045, legs[0], -max(0, wave)*28 if state == 'walk' else 0)
            transforms['right_leg'] = self.transform(690, 1045, legs[1], -max(0, -wave)*28 if state == 'walk' else 0)
        transforms['torso'] = self.transform(625, 930, dy=body_y)
        transforms['head'] = self.transform(625, 690, dy=head_y)
        if state == 'look':
            gaze = sin(tick*1.5)
            transforms['head'] = self.transform(625, 690, angle=gaze*4)
            transforms['head'].translate(gaze*22, 0)
        elif state == 'sad':
            transforms['head'] = self.transform(625, 690, angle=5, dy=head_y)
        return transforms

    def paint_sad_face(self, p):
        """Replace the cheerful eyes, brows and smile in head coordinates."""
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#ffc18f'))
        for x in (477, 672):
            p.drawRoundedRect(QRectF(x-5, 416, 119, 172), 23, 23)
        p.drawRoundedRect(QRectF(574, 608, 113, 53), 20, 20)
        # Inner brows lift and drooping lids turn the expression downcast.
        for x, side in ((480, -1), (675, 1)):
            brow = QPainterPath(QPointF(x+4, 460+(16 if side < 0 else -22)))
            brow.quadTo(x+50, 442, x+98, 460+(-22 if side < 0 else 16))
            p.setPen(QPen(QColor('#44312d'), 17, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(brow)
            p.setPen(QPen(QColor('#513023'), 8))
            p.setBrush(QColor('#fff5e9'))
            p.drawEllipse(QRectF(x+7, 493, 88, 72))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#52372d'))
            p.drawEllipse(QRectF(x+27, 505, 48, 57))
            p.setBrush(QColor('#ffffff'))
            p.drawEllipse(QRectF(x+33, 510, 19, 23))
            p.drawEllipse(QRectF(x+58, 540, 9, 10))
            p.setPen(QPen(QColor('#64bce8'), 14, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(x+15, 562), QPointF(x+87, 562))
        mouth = QPainterPath(QPointF(587, 649))
        mouth.quadTo(628, 598, 670, 649)
        mouth.quadTo(630, 628, 587, 649)
        p.setBrush(QColor('#874737'))
        p.setPen(QPen(QColor('#804537'), 8, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(mouth)
        for x in (490, 753):
            p.setPen(QPen(QColor('#65afd6'), 3))
            p.setBrush(QColor('#9edfff'))
            tear = QPainterPath(QPointF(x, 568))
            tear.cubicTo(x-7, 591, x-22, 606, x-17, 621)
            tear.cubicTo(x-11, 643, x+18, 635, x+17, 617)
            tear.cubicTo(x+16, 599, x+4, 582, x, 568)
            p.drawPath(tear)
            p.setPen(QPen(QColor('#e5f8ff'), 5, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(x-8, 606), QPointF(x-8, 619))

    def paint_rest_or_stretch_arms(self, p, state, tick):
        """Foreground arms keep both gestures readable beside the head/body."""
        p.setRenderHint(QPainter.Antialiasing, True)
        for side in (-1, 1):
            if state == 'sit':
                shoulder = QPointF(625+side*92, 825)
                elbow = QPointF(625+side*137, 967)
                wrist = QPointF(625+side*100, 1050)
            else:
                sway = sin(tick*2)*8
                shoulder = QPointF(625+side*96, 737)
                elbow = QPointF(625+side*230, 685+sway)
                wrist = QPointF(625+side*252, 550+sway)
            arm = QPainterPath(shoulder)
            arm.lineTo(elbow)
            arm.lineTo(wrist)
            p.setBrush(Qt.NoBrush)
            for color, width in (('#29242a', 43), ('#f3ae7e', 30)):
                p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawPath(arm)
            sleeve = shoulder+(elbow-shoulder)*.32
            for color, width in (('#252127', 56), ('#39343c', 42)):
                p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(shoulder, sleeve)
            p.setPen(QPen(QColor('#b87854'), 4, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(QColor('#ffc18f'))
            if state == 'sit':
                p.drawRoundedRect(QRectF(wrist.x()-29, wrist.y()-12, 58, 32), 13, 13)
                for offset in (-12, 0, 12):
                    p.drawLine(QPointF(wrist.x()+offset, wrist.y()+3),
                               QPointF(wrist.x()+offset, wrist.y()+15))
            else:
                p.drawRoundedRect(QRectF(wrist.x()-22, wrist.y()-35, 44, 53), 15, 15)
                for offset, length in ((-15, 23), (-5, 36), (5, 39), (15, 28)):
                    start = wrist+QPointF(offset, -25)
                    for color, width in (('#b87854', 12), ('#ffc18f', 8)):
                        p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap))
                        p.drawLine(start, start+QPointF(offset*.18, -length))

    def paint_meditation(self, p):
        """Crossed legs in source coordinates; prayer hands render over shirt."""
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(QColor('#211f25'), 8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor('#343238'))
        legs = QPainterPath()
        legs.moveTo(548, 994)
        legs.cubicTo(510, 994, 445, 1035, 452, 1080)
        legs.cubicTo(465, 1135, 576, 1145, 628, 1110)
        legs.cubicTo(683, 1150, 790, 1130, 800, 1080)
        legs.cubicTo(806, 1035, 743, 995, 705, 994)
        legs.closeSubpath()
        p.drawPath(legs)
        p.setPen(QPen(QColor('#4b484f'), 12, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(480, 1080), QPointF(650, 1115))
        p.drawLine(QPointF(773, 1080), QPointF(600, 1117))
        p.setPen(QPen(QColor('#211e24'), 7, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(480, 1096), QPointF(650, 1130))
        p.drawLine(QPointF(773, 1096), QPointF(605, 1132))
        p.setPen(QPen(QColor('#fff2df'), 9, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(485, 1054, 30, 30), 45*16, 270*16)
        # Two bent shins crossing in front, with bare feet at opposite knees.
        for start, control, end in (((493, 1070), (575, 1140), (706, 1098)),
                                    ((758, 1070), (680, 1148), (548, 1108))):
            shin = QPainterPath(QPointF(*start))
            shin.quadTo(QPointF(*control), QPointF(*end))
            p.setPen(QPen(QColor('#242127'), 43, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(shin)
            p.setPen(QPen(QColor('#49464e'), 30, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(shin)
            p.setPen(QPen(QColor('#b47b5c'), 4))
            p.setBrush(QColor('#f5ba8e'))
            p.drawEllipse(QRectF(end[0]-24, end[1]-12, 48, 24))

    def paint_prayer_hands(self, p):
        p.setRenderHint(QPainter.Antialiasing, True)
        for side in (-1, 1):
            shoulder = QPointF(625+side*88, 852)
            elbow = QPointF(625+side*111, 947)
            wrist = QPointF(625+side*15, 916)
            p.setPen(QPen(QColor('#252127'), 48, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(shoulder, elbow)
            p.drawLine(elbow, wrist)
            p.setPen(QPen(QColor('#f3ae7e'), 34, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(elbow, wrist)
            p.setPen(QPen(QColor('#333037'), 51, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(shoulder, QPointF(625+side*100, 889))
            hand = QPainterPath(QPointF(625, 837))
            hand.cubicTo(625+side*12, 831, 625+side*17, 852, 625+side*19, 881)
            hand.cubicTo(625+side*35, 892, 625+side*28, 918, 625+side*13, 926)
            hand.lineTo(625, 915)
            hand.closeSubpath()
            p.setPen(QPen(QColor('#bc7956'), 3, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(QColor('#ffc18f'))
            p.drawPath(hand)
            p.drawLine(QPointF(625+side*9, 853), QPointF(625+side*10, 888))

    def paint(self, painter, state, tick, facing):
        if state == 'nap':
            self.paint_nap(painter, tick)
            return
        transforms = self.pose(state, tick, facing)
        bottom = 1148 if state == 'sleep' else max(transforms[part].mapRect(rect).bottom() for part, rect in self.part_bounds.items())
        painter.save()
        painter.translate(60, 140)
        painter.scale(self.scale, self.scale)
        painter.translate(-self.center_x, -bottom)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(Qt.NoPen)
        if state == 'sleep':
            self.paint_meditation(painter)
        draw_order = self.parts
        if state in ('sit', 'sad', 'groom'):
            draw_order = tuple(part for part in self.parts if part not in ('left_arm', 'right_arm')) + ('left_arm', 'right_arm')
        for part in draw_order:
            if state == 'look' and part == ('right_arm' if sin(tick*1.5) >= 0 else 'left_arm'):
                continue
            if state == 'high_five_cursor' and part == 'right_arm':
                continue
            if state == 'grabbed' and part in ('left_arm', 'right_arm'):
                continue
            if state == 'sleep' and part in ('left_leg', 'right_leg', 'shorts', 'left_arm', 'right_arm'):
                continue
            painter.save()
            painter.setTransform(transforms[part], True)
            tile, rect = self.part_cache[part]
            if state == 'sit' and part in ('left_arm', 'right_arm'):
                # Bend the original forearm at its elbow, preserving the
                # authored hand, shading and rounded silhouette.
                elbow_y = 845
                elbow_x = 490 if part == 'left_arm' else 770
                angle = -24 if part == 'left_arm' else 24
                upper = QRectF(rect.left(), rect.top(), rect.width(), elbow_y-rect.top()+2)
                lower = QRectF(rect.left(), elbow_y-2, rect.width(), rect.bottom()-elbow_y+3)
                painter.drawPixmap(upper, tile, QRectF(0, 0, upper.width(), upper.height()))
                painter.setTransform(self.transform(elbow_x, elbow_y, angle), True)
                painter.drawPixmap(lower, tile, QRectF(0, lower.top()-rect.top(),
                                                       lower.width(), lower.height()))
            else:
                painter.drawPixmap(QPointF(rect.left(), rect.top()), tile)
            if part == 'head' and state == 'sad':
                self.paint_sad_face(painter)
            elif part == 'head' and state == 'look':
                self.paint_looking_eyes(painter, sin(tick*1.5))
            elif part == 'head' and (state == 'sleep' or tick % 6 < .12):
                # Eyelids animate independently while keeping the original hair.
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor('#ffc18f'))
                for x in (480, 675):
                    painter.drawRoundedRect(QRectF(x, 480, 107, 105), 20, 20)
                    painter.setPen(QPen(QColor('#513023'), 9, Qt.SolidLine, Qt.RoundCap))
                    painter.drawArc(QRectF(x+8, 506, 86, 48), 190*16, 160*16)
                    painter.setPen(Qt.NoPen)
            painter.restore()
        if state == 'groom':
            painter.save()
            painter.setTransform(transforms['left_arm'], True)
            painter.setPen(QPen(QColor('#a67543'), 12, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(478, 943), QPointF(540, 943))
            painter.setPen(QPen(QColor('#5d4028'), 4))
            for x in range(480, 540, 8):
                painter.drawLine(QPointF(x, 943), QPointF(x, 966))
            painter.restore()
        if state == 'sleep':
            self.paint_prayer_hands(painter)
        elif state == 'look':
            self.paint_looking_hand(painter, transforms['head'], tick)
        painter.restore()

    def paint_nap(self, p, tick):
        # Render onto a low-resolution grid, then enlarge with nearest-neighbor
        # sampling so all outlines and motion use the same crisp pixel scale.
        frame = QImage(60, 70, QImage.Format_ARGB32_Premultiplied)
        frame.fill(Qt.transparent)
        pixel_painter = QPainter(frame)
        pixel_painter.scale(.5, .5)
        self.paint_nap_geometry(pixel_painter, tick)
        pixel_painter.end()
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(QRectF(0, 0, 120, 140), frame)
        p.restore()

    def paint_nap_geometry(self, p, tick):
        """Rear view, lying down in clothes with an occasional sleepy scratch."""
        p.save()
        p.setRenderHint(QPainter.Antialiasing, False)
        breath = round(sin(tick*1.8))
        outline = QColor('#29242a')
        p.setPen(QPen(outline, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        # Bent legs and shoes rest on the same baseline as the other poses.
        p.setBrush(QColor('#efb187'))
        p.drawRoundedRect(QRectF(88, 124, 21, 9), 4, 4)
        p.drawRoundedRect(QRectF(85, 131, 24, 8), 4, 4)
        p.setBrush(QColor('#44434a'))
        p.drawRoundedRect(QRectF(103, 123, 12, 11), 4, 4)
        p.drawRoundedRect(QRectF(104, 130, 13, 9), 4, 4)
        p.setPen(QPen(QColor('#eee9e4'), 2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(105, 138), QPointF(115, 138))
        p.setPen(QPen(outline, 1.5))
        p.setBrush(QColor('#353239'))
        p.drawRoundedRect(QRectF(70, 113, 26, 25), 9, 9)
        p.setPen(QPen(QColor('#514b55'), 1.2))
        p.drawArc(QRectF(77, 117, 15, 17), -70*16, 160*16)
        # Shirt back, with folds and a soft breathing movement.
        p.setPen(QPen(outline, 1.5))
        p.setBrush(QColor('#333037'))
        p.drawRoundedRect(QRectF(32, 110-breath, 47, 28+breath), 12, 12)
        p.setPen(QPen(QColor('#48434c'), 1.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(54, 116-breath), QPointF(68, 119))
        p.drawLine(QPointF(50, 132), QPointF(65, 134))
        # Only the back of the head is visible; no face or mirrored front.
        p.setPen(QPen(outline, 1.5))
        p.setBrush(QColor('#efb187'))
        p.drawEllipse(QRectF(30, 122, 9, 11))
        p.setBrush(QColor('#353238'))
        hair = QPainterPath(QPointF(9, 125))
        hair.cubicTo(3, 113, 10, 98, 22, 98)
        hair.lineTo(17, 94)
        hair.cubicTo(31, 93, 46, 103, 44, 119)
        hair.cubicTo(46, 132, 34, 140, 21, 137)
        hair.cubicTo(12, 138, 7, 133, 9, 125)
        p.drawPath(hair)
        p.setPen(QPen(QColor('#55505a'), 1.5, Qt.SolidLine, Qt.RoundCap))
        for offset in (0, 7, 14):
            strand = QPainterPath(QPointF(12+offset, 105))
            strand.cubicTo(26+offset, 110, 29+offset*.5, 124, 20+offset*.4, 132)
            p.drawPath(strand)
        # The hand scratches over the shorts, never exposing skin beneath them.
        scratch = round(sin(tick*13))*2 if tick % 5 < 1.4 else 0
        arm = QPainterPath(QPointF(47, 119))
        arm.quadTo(57, 108, 65, 116)
        arm.quadTo(73, 124, 83, 125+scratch)
        p.setBrush(Qt.NoBrush)
        for color, width in ((outline, 6), (QColor('#ffc18f'), 3.8)):
            p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(arm)
        p.setPen(QPen(QColor('#b87854'), .7))
        p.setBrush(QColor('#ffc18f'))
        p.drawEllipse(QRectF(80, 121+scratch, 8, 6))
        p.setPen(QPen(QColor('#81758b'), 1))
        for x, y, size in ((17, 86, 5), (29, 77, 7)):
            z = QPainterPath(QPointF(x, y+breath))
            z.lineTo(x+size, y+breath)
            z.lineTo(x, y+size+breath)
            z.lineTo(x+size, y+size+breath)
            p.drawPath(z)
        p.restore()

    def paint_looking_eyes(self, p, gaze):
        p.setRenderHint(QPainter.Antialiasing, True)
        for x in (480, 675):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#ffc18f'))
            p.drawRoundedRect(QRectF(x-3, 480, 113, 109), 22, 22)
            p.setPen(QPen(QColor('#513023'), 6))
            p.setBrush(QColor('#fff8ee'))
            p.drawEllipse(QRectF(x+5, 492, 94, 79))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor('#493126'))
            p.drawEllipse(QRectF(x+27+gaze*16, 503, 49, 63))
            p.setBrush(QColor('#ffffff'))
            p.drawEllipse(QRectF(x+34+gaze*16, 510, 16, 19))

    def paint_looking_hand(self, p, head_transform, tick):
        side = 1 if sin(tick*1.5) >= 0 else -1
        shoulder = QPointF(625+side*100, 740)
        elbow = QPointF(625+side*170, 625)
        wrist = head_transform.map(QPointF(625+side*103, 451))
        p.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath(shoulder)
        path.quadTo(elbow+QPointF(side*8, 10), elbow)
        path.quadTo(elbow+QPointF(-side*15, -70), wrist)
        p.setBrush(Qt.NoBrush)
        for color, width in (('#29242a', 39), ('#f3ae7e', 28)):
            p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
        for color, width in (('#252127', 53), ('#39343c', 40)):
            p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(shoulder, shoulder+(elbow-shoulder)*.35)
        # Reuse the original rounded hand, including its pixel shading.
        part = 'right_arm' if side > 0 else 'left_arm'
        tile, rect = self.part_cache[part]
        hand_x = 790 if side > 0 else 478
        hand = QRectF(hand_x-37, 906, 74, 73)
        p.save()
        p.translate(wrist)
        p.rotate(side*90)
        p.scale(.85, .85)
        p.drawPixmap(QRectF(-37, -22, 74, 73), tile,
                     QRectF(hand.left()-rect.left(), hand.top()-rect.top(),
                            hand.width(), hand.height()))
        p.restore()
