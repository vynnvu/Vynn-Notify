"""Rounded speech card with a pointer, soft shadow and bounded text scrolling."""
from PySide6.QtCore import Qt, QRect, QRectF
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QFrame,
)


class MessageBubble(QWidget):
    def __init__(self, dismiss):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.dark = False
        self.tail_up = False
        self.tail_x = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 17, 25, 29)
        layout.setSpacing(9)
        header = QHBoxLayout()
        header.setSpacing(7)
        self.dot = QLabel()
        self.dot.setFixedSize(7, 7)
        header.addWidget(self.dot)
        self.title = QLabel('Vynn Notify')
        self.title.setTextFormat(Qt.PlainText)
        header.addWidget(self.title, 1)
        self.close_button = QPushButton('×')
        self.close_button.setFixedSize(23, 23)
        self.close_button.setFocusPolicy(Qt.NoFocus)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setToolTip('Đóng lời thoại')
        self.close_button.clicked.connect(dismiss)
        header.addWidget(self.close_button)
        layout.addLayout(header)
        self.body = QLabel()
        self.body.setTextFormat(Qt.PlainText)
        self.body.setWordWrap(True)
        self.body.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.text_area = QScrollArea()
        self.text_area.setWidgetResizable(True)
        self.text_area.setFrameShape(QFrame.NoFrame)
        self.text_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_area.setWidget(self.body)
        layout.addWidget(self.text_area)

    def configure(self, config, name):
        self.dark = config['message_theme'] == 'dark'
        self.setFixedWidth(config['message_width'])
        self.title.setText(name)
        foreground, muted, accent, hover = ('#edf1fa', '#a9b5cc', '#b5adff', '#363d52') if self.dark else ('#333448', '#797887', '#8b78bd', '#eee9f7')
        self.setStyleSheet(f'''
            QLabel, QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{
                background: transparent; border: none; color: {foreground};
            }}
            QPushButton {{color: {muted}; background: transparent; border: none;
                border-radius: 8px; font-size: 20px; padding: 0;}}
            QPushButton:hover {{background: {hover}; color: {foreground};}}
            QScrollBar:vertical {{background: transparent; width: 5px; margin: 0;}}
            QScrollBar::handle:vertical {{background: {accent}; border-radius: 2px; min-height: 20px;}}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height: 0;}}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{background: transparent;}}
        ''')
        font = QFont('Segoe UI')
        font.setPixelSize(config['message_font'])
        self.body.setFont(font)
        font.setPixelSize(12)
        font.setWeight(QFont.DemiBold)
        self.title.setFont(font)
        self.title.setStyleSheet(f'color: {muted};')
        self.dot.setStyleSheet(f'background: {accent}; border-radius: 3px;')
        self.fit_text()
        self.update()

    def setText(self, text):
        self.body.setText(text)
        self.body.setToolTip(text)
        self.text_area.verticalScrollBar().setValue(0)
        self.fit_text()

    def fit_text(self):
        # Reserve scrollbar width before measuring so wrapped text never clips.
        width = max(60, self.width()-56)
        height = self.body.fontMetrics().boundingRect(QRect(0, 0, width, 100000),
                  Qt.TextWordWrap, self.body.text() or ' ').height()+5
        limit = max(80, min(260, QApplication.primaryScreen().availableGeometry().height()//3))
        self.body.setMinimumHeight(height)
        self.text_area.setFixedHeight(min(height, limit))
        self.adjustSize()

    def point_to(self, global_x, upward=False):
        self.tail_x = max(35, min(self.width()-35, global_x-self.x()))
        self.tail_up = upward
        self.layout().setContentsMargins(25, 27 if upward else 17, 25, 19 if upward else 29)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        top, bottom = (17, 8) if self.tail_up else (7, 18)
        card = QRectF(10, top, self.width()-20, self.height()-top-bottom)
        path = QPainterPath()
        path.addRoundedRect(card, 17, 17)
        pointer = QPainterPath()
        x = self.tail_x or self.width()/2
        edge = card.top()+1 if self.tail_up else card.bottom()-1
        tip = card.top()-10 if self.tail_up else card.bottom()+10
        pointer.moveTo(x-8, edge)
        pointer.quadTo(x-3, (edge+tip)/2, x, tip)
        pointer.quadTo(x+3, (edge+tip)/2, x+8, edge)
        pointer.closeSubpath()
        path = path.united(pointer)
        p.setBrush(Qt.NoBrush)
        for width, alpha in ((13, 3), (9, 5), (5, 8)):
            p.setPen(QPen(QColor(20, 17, 40, alpha), width))
            p.drawPath(path.translated(0, 2))
        gradient = QLinearGradient(card.topLeft(), card.bottomRight())
        gradient.setColorAt(0, QColor('#2b3042' if self.dark else '#fffdf9'))
        gradient.setColorAt(1, QColor('#222737' if self.dark else '#f4f0fc'))
        p.setPen(QPen(QColor('#454b61' if self.dark else '#e3dced'), 1))
        p.setBrush(gradient)
        p.drawPath(path)
