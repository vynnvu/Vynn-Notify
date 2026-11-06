"""Live controls for character, size, movement and routines."""
import math
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QCheckBox, QPushButton, QSpinBox, QApplication, QScrollArea, QMessageBox, QToolButton, QLineEdit, QPlainTextEdit, QTabWidget,
)
from pet.character_manager import available_characters
from pet.platform_services import autostart_enabled, set_autostart
from pet.dialogue import CATALOG, DEFAULT_ENABLED
from pet.theme import SETTINGS_STYLE
import sys


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class CollapsibleSection(QWidget):
    def __init__(self, title, collapsed, changed):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        self.header = QToolButton()
        self.header.setText(title)
        self.header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.header.setCheckable(True)
        self.header.setChecked(not collapsed)
        self.header.setObjectName('sectionHeader')
        self.body = QWidget()
        self.body.setObjectName('sectionBody')
        self.body.setAttribute(Qt.WA_StyledBackground)
        layout.addWidget(self.header)
        layout.addWidget(self.body)
        def toggle(expanded):
            self.header.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
            self.body.setVisible(expanded)
            changed(not expanded)
        self.header.toggled.connect(toggle)
        self.header.setArrowType(Qt.RightArrow if collapsed else Qt.DownArrow)
        self.body.setVisible(not collapsed)


class SettingsWindow(QWidget):
    def __init__(self, pet):
        super().__init__()
        self.pet = pet
        self.setObjectName('settingsRoot')
        self.setStyleSheet(SETTINGS_STYLE)
        self.sections = {}
        self.setWindowTitle("Vynn Notify · Điều khiển")
        self.setMinimumWidth(560)
        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName('settingsContent')
        layout = QVBoxLayout(content)
        columns = QHBoxLayout()
        self.left_column = QVBoxLayout()
        self.right_column = QVBoxLayout()
        columns.addLayout(self.left_column, 1)
        columns.addLayout(self.right_column, 1)
        scroll.setWidget(content)
        root.addWidget(scroll)
        self.resize(660, min(760, QApplication.primaryScreen().availableGeometry().height() - 60))
        title = QLabel("Bạn đồng hành trên desktop")
        title.setStyleSheet("font-size: 19px; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(title)
        layout.addLayout(columns)
        appearance = self.section('appearance', "Ngoại hình")
        form = QFormLayout(appearance.body)
        self.models = NoWheelComboBox()
        for char_id, spec in available_characters().items():
            self.models.addItem(spec["name"], char_id)
        self.models.setParent(self)
        self.models.hide()
        self.sizes = NoWheelComboBox()
        for label, key in [("Rất nhỏ · 35%", "Tiny"), ("Nhỏ · 50%", "Small"),
                           ("Vừa · 75%", "Medium"), ("Lớn · 100%", "Large")]:
            self.sizes.addItem(label, key)
        form.addRow("Kích thước", self.sizes)
        self.left_column.addWidget(appearance)
        movement = self.section('movement', "Di chuyển")
        moving = QVBoxLayout(movement.body)
        self.auto = QCheckBox("Tự đi lại")
        self.stay = QCheckBox("Đứng yên")
        self.pause = QCheckBox("Tạm dừng")
        self.pause.setToolTip('Dừng cả chuyển động và trọng lực')
        self.perches = QCheckBox("Bám bề mặt")
        self.perches.setToolTip('Đứng và leo trên cửa sổ, biểu tượng và các bề mặt được nhận diện')
        self.fullscreen = QCheckBox("Ẩn khi toàn màn hình")
        self.follow_active = QCheckBox("Theo cửa sổ đang dùng")
        self.follow_active.toggled.connect(lambda value: pet.toggle("follow_active", value))
        self.startup = QCheckBox("Mở cùng Windows")
        self.startup.setEnabled(sys.platform == 'win32')
        self.startup.setChecked(autostart_enabled())
        self.startup.toggled.connect(self.change_startup)
        for widget in (self.auto, self.stay, self.pause, self.perches, self.fullscreen, self.follow_active, self.startup):
            moving.addWidget(widget)
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Tốc độ đi lại"))
        self.speed = NoWheelSpinBox()
        self.speed.setRange(10, 300)
        self.speed.setSuffix(" px/giây")
        self.speed.valueChanged.connect(self.change_speed)
        speed_row.addWidget(self.speed)
        moving.addLayout(speed_row)
        self.speed_per_minute = QLabel()
        moving.addWidget(self.speed_per_minute)
        pause_row = QHBoxLayout()
        pause_row.addWidget(QLabel("Nghỉ giữa động tác"))
        self.action_pause = NoWheelSpinBox()
        self.action_pause.setRange(1, 15)
        self.action_pause.setSuffix(" giây")
        self.action_pause.valueChanged.connect(self.change_action_pause)
        pause_row.addWidget(self.action_pause)
        moving.addLayout(pause_row)
        explore = QPushButton("Khám phá")
        explore.clicked.connect(pet.explore)
        moving.addWidget(explore)
        active = QPushButton("Tới cửa sổ đang dùng")
        active.clicked.connect(pet.go_active_window)
        moving.addWidget(active)
        favourite = QPushButton("Tới chỗ yêu thích")
        favourite.clicked.connect(pet.go_favourite)
        moving.addWidget(favourite)
        buttons = QHBoxLayout()
        for label, callback in [("Gọi lại", pet.call), ("Nhảy", pet.jump), ("Đập tay", pet.high_five)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        moving.addLayout(buttons)
        self.right_column.addWidget(movement)
        activities = self.section('activities', "Hoạt động")
        activity_form = QFormLayout(activities.body)
        self.activity = NoWheelComboBox()
        for label, state in [("Đi bộ", "walk"),
                             ("Ngủ", "nap"),
                             ("Ngồi thiền (hoạt động)", "sleep"),
                             ("Vui / nhảy múa", "dance"),
                             ("Buồn", "sad"), ("Tìm chỗ leo", "climb"),
                             ("Ngồi nghỉ", "sit"), ("Quan sát", "look"),
                             ("Chải tóc", "groom"), ("Vươn vai", "stretch"), ("Đập tay", "high_five")]:
            self.activity.addItem(label, state)
        activity_form.addRow("Chọn hoạt động", self.activity)
        self.run_activity = QPushButton("Thực hiện")
        self.run_activity.setProperty('role', 'primary')
        self.run_activity.clicked.connect(self.perform_activity)
        activity_form.addRow(self.run_activity)
        self.current_activity = QLabel()
        activity_form.addRow("Hiện tại", self.current_activity)
        self.right_column.insertWidget(0, activities)
        self.right_column.addStretch()
        meditation = self.section('meditation', "Chế độ thiền")
        meditation_form = QFormLayout(meditation.body)
        self.meditation_minutes = NoWheelSpinBox()
        self.meditation_minutes.setRange(1, 180)
        self.meditation_minutes.setSuffix(" phút")
        self.meditation_minutes.valueChanged.connect(self.change_meditation_minutes)
        meditation_form.addRow("Thời gian", self.meditation_minutes)
        self.begin_meditation = QPushButton("Bắt đầu thiền")
        self.begin_meditation.setToolTip('Hẹn giờ thiền và khóa di chuyển trong thời gian đã chọn')
        self.begin_meditation.setProperty('role', 'primary')
        self.begin_meditation.clicked.connect(lambda: pet.start_meditation())
        meditation_form.addRow(self.begin_meditation)
        self.end_meditation = QPushButton("Dừng thiền")
        self.end_meditation.setProperty('role', 'stop')
        self.end_meditation.clicked.connect(pet.stop_meditation)
        meditation_form.addRow(self.end_meditation)
        meditation_hint = QLabel("Khóa di chuyển trong thời gian thiền.")
        meditation_hint.setWordWrap(True)
        meditation_form.addRow(meditation_hint)
        self.meditation_status = QLabel()
        meditation_form.addRow(self.meditation_status)
        self.left_column.addWidget(meditation)
        routines = self.section('routines', "Nhắc nghỉ và tập trung")
        routine_form = QFormLayout(routines.body)
        self.reminders = {}
        for key, label in [("eyes", "Nghỉ mắt"), ("stretch", "Giãn cơ"), ("water", "Uống nước")]:
            row = QHBoxLayout()
            check = QCheckBox(label)
            interval = NoWheelSpinBox()
            interval.setRange(1, 1440)
            interval.setSuffix(" phút")
            row.addWidget(check)
            row.addWidget(interval)
            routine_form.addRow(row)
            self.reminders[key] = (check, interval)
            check.toggled.connect(lambda value, k=key: pet.set_reminder(k, value))
            interval.valueChanged.connect(lambda value, k=key: self.change_interval(k, value))
        focus_row = QHBoxLayout()
        start = QPushButton("Tập trung 25 phút")
        start.clicked.connect(pet.start_focus)
        stop = QPushButton("Dừng hẹn giờ")
        stop.clicked.connect(pet.life.stop_focus)
        focus_row.addWidget(start)
        focus_row.addWidget(stop)
        routine_form.addRow(focus_row)
        self.left_column.addWidget(routines)
        messages = self.section('messages', "Lời thoại")
        message_form = QFormLayout(messages.body)
        self.message_enabled = QCheckBox("Hiện lời thoại")
        self.message_enabled.toggled.connect(lambda value: self.change_message('messages_enabled', value))
        message_form.addRow(self.message_enabled)
        self.message_controls = {}
        for key, label, low, high, suffix in [('message_seconds', 'Thời gian hiển thị', 1, 30, ' giây'),
                                              ('message_font', 'Cỡ chữ', 10, 24, ' px'),
                                              ('message_width', 'Chiều rộng', 180, 420, ' px')]:
            spin = NoWheelSpinBox()
            spin.setRange(low, high)
            spin.setSuffix(suffix)
            spin.valueChanged.connect(lambda value, k=key: self.change_message(k, value))
            self.message_controls[key] = spin
            message_form.addRow(label, spin)
        self.message_theme = NoWheelComboBox()
        self.message_theme.addItem('Sáng', 'light')
        self.message_theme.addItem('Tối', 'dark')
        self.message_theme.currentIndexChanged.connect(lambda: self.change_message('message_theme', self.message_theme.currentData()))
        message_form.addRow('Giao diện', self.message_theme)
        self.message_text = QLineEdit()
        self.message_text.setMaxLength(1200)
        self.message_text.editingFinished.connect(lambda: self.change_message('message_preview', self.message_text.text()))
        message_form.addRow('Nội dung thử', self.message_text)
        self.message_test = QPushButton('Xem thử lời thoại')
        self.message_test.clicked.connect(self.preview_message)
        message_form.addRow(self.message_test)
        dismiss = QPushButton('Ẩn lời thoại hiện tại')
        dismiss.clicked.connect(lambda: (pet.messages.clear(), pet.dismiss_message()))
        message_form.addRow(dismiss)
        self.dialogue_kind = NoWheelComboBox()
        for key, (label, _) in CATALOG.items():
            self.dialogue_kind.addItem(label, key)
        message_form.addRow('Lời thoại theo loại', self.dialogue_kind)
        self.dialogue_enabled = QCheckBox('Bật lời thoại cho loại này')
        message_form.addRow(self.dialogue_enabled)
        self.dialogue_editor = QPlainTextEdit()
        self.dialogue_editor.setMaximumHeight(110)
        self.dialogue_editor.setPlaceholderText('Nhập lời thoại; để trống để không nói.')
        message_form.addRow('Nội dung', self.dialogue_editor)
        tokens = QLabel('Biến: {minutes}, {summary}, {energy}, {affection}')
        tokens.setToolTip('Nội dung tự lưu. Để trống hoặc bỏ bật để tắt lời thoại đang chọn.')
        tokens.setWordWrap(True)
        message_form.addRow(tokens)
        dialogue_buttons = QHBoxLayout()
        self.dialogue_test = QPushButton('Xem thử loại đang chọn')
        self.dialogue_test.clicked.connect(self.preview_dialogue)
        self.dialogue_reset = QPushButton('Khôi phục mặc định')
        self.dialogue_reset.clicked.connect(self.reset_dialogue)
        dialogue_buttons.addWidget(self.dialogue_test)
        dialogue_buttons.addWidget(self.dialogue_reset)
        message_form.addRow(dialogue_buttons)
        self.dialogue_save_timer = QTimer(self)
        self.dialogue_save_timer.setSingleShot(True)
        self.dialogue_save_timer.setInterval(400)
        self.dialogue_save_timer.timeout.connect(pet.save)
        self._dialogue_loading = False
        self.dialogue_kind.currentIndexChanged.connect(self.load_dialogue)
        self.dialogue_editor.textChanged.connect(self.edit_dialogue)
        self.dialogue_enabled.toggled.connect(self.edit_dialogue)
        self.load_dialogue()
        self.left_column.addWidget(messages)
        self.left_column.addStretch()
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        management = QHBoxLayout()
        self.visibility = QPushButton()
        self.visibility.clicked.connect(self.toggle_visibility)
        self.save_button = QPushButton("Lưu")
        self.save_button.clicked.connect(pet.save)
        management.addWidget(self.visibility)
        management.addWidget(self.save_button)
        root.addLayout(management)
        hint = QLabel("Tự lưu thay đổi · Mở lại từ khay hệ thống")
        hint.setWordWrap(True)
        root.addWidget(hint)
        footer = QHBoxLayout()
        close = QPushButton("Đóng")
        close.clicked.connect(self.close)
        quit_button = QPushButton("Thoát Vynn Notify")
        quit_button.setProperty('role', 'stop')
        quit_button.clicked.connect(QApplication.instance().quit)
        footer.addWidget(close)
        footer.addWidget(quit_button)
        root.addLayout(footer)
        # Reuse the live controls in focused tabs instead of one long page.
        self.tabs = QTabWidget()
        general = self.section('general', 'Ứng dụng')
        general_layout = QVBoxLayout(general.body)
        for widget in (self.fullscreen, self.startup):
            general_layout.addWidget(widget)
        for name, sections in [('Vynn', (appearance, activities, movement)),
                               ('Nhắc nhở', (routines, meditation)),
                               ('Cài đặt', (general, messages))]:
            page = QWidget()
            page.setObjectName('settingsContent')
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(4, 12, 4, 4)
            page_layout.setSpacing(10)
            for section in sections:
                page_layout.addWidget(section)
            page_layout.addStretch()
            tab_scroll = QScrollArea()
            tab_scroll.setWidgetResizable(True)
            tab_scroll.setWidget(page)
            self.tabs.addTab(tab_scroll, name)
        root.removeWidget(scroll)
        scroll.hide()
        scroll.deleteLater()
        heading = QLabel('Vynn Notify')
        heading.setStyleSheet('font-size: 23px; font-weight: 600; padding: 4px 0;')
        root.insertWidget(0, heading)
        root.insertWidget(1, self.tabs, 1)
        self.models.currentIndexChanged.connect(self.change_character)
        self.sizes.currentIndexChanged.connect(self.change_size)
        self.auto.toggled.connect(self.change_auto)
        self.stay.toggled.connect(lambda checked: pet.toggle("stay", checked))
        self.pause.toggled.connect(lambda checked: setattr(pet, "floating", checked))
        self.perches.toggled.connect(lambda checked: pet.toggle("window_perches", checked))
        self.fullscreen.toggled.connect(lambda checked: pet.toggle("hide_fullscreen", checked))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sync)
        self.timer.start(500)

    def section(self, key, title):
        def changed(collapsed):
            self.pet.life.config['collapsed_sections'][key] = collapsed
            self.pet.save()
        section = CollapsibleSection(title, self.pet.life.config['collapsed_sections'].get(key, False), changed)
        self.sections[key] = section
        return section

    def change_message(self, key, value):
        self.pet.life.config[key] = value
        self.pet.apply_message_settings()
        self.pet.save()

    def preview_message(self):
        self.change_message('message_preview', self.message_text.text())
        self.pet.preview_message()

    def load_dialogue(self):
        key = self.dialogue_kind.currentData()
        self._dialogue_loading = True
        try:
            self.dialogue_editor.setPlainText(self.pet.life.config['dialogue'].get(key, CATALOG[key][1]))
            self.dialogue_enabled.setChecked(self.pet.life.config['dialogue_enabled'].get(key, DEFAULT_ENABLED[key]))
        finally:
            self._dialogue_loading = False

    def edit_dialogue(self):
        if self._dialogue_loading:
            return
        key = self.dialogue_kind.currentData()
        text = self.dialogue_editor.toPlainText()
        if len(text) > 1200:
            self._dialogue_loading = True
            self.dialogue_editor.setPlainText(text[:1200])
            self._dialogue_loading = False
        self.pet.life.config['dialogue'][key] = text[:1200]
        self.pet.life.config['dialogue_enabled'][key] = self.dialogue_enabled.isChecked()
        self.dialogue_save_timer.start()

    def preview_dialogue(self):
        self.pet.messages.clear()
        self.pet.dismiss_message()
        self.pet.say_event(self.dialogue_kind.currentData(), minutes=self.pet.life.config['meditation_min'])

    def reset_dialogue(self):
        key = self.dialogue_kind.currentData()
        self.pet.life.config['dialogue'].pop(key, None)
        self.pet.life.config['dialogue_enabled'].pop(key, None)
        self.load_dialogue()
        self.pet.save()

    def change_character(self):
        self.pet.set_character(self.models.currentData())

    def perform_activity(self):
        state = self.activity.currentData()
        if state == 'high_five':
            self.pet.high_five()
        elif not self.pet.motion_locked:
            self.pet.perform_action(state)

    def change_meditation_minutes(self, value):
        self.pet.life.config['meditation_min'] = value
        self.pet.save()

    def change_startup(self, enabled):
        try:
            set_autostart(enabled)
        except OSError as exc:
            self.update_value(self.startup, self.startup.setChecked, autostart_enabled())
            QMessageBox.warning(self, "Tự khởi động", str(exc))

    def toggle_visibility(self):
        self.pet.toggle_hidden()
        self.sync()

    def change_size(self):
        self.pet.set_size(self.sizes.currentData())
        self.pet.save()

    def change_auto(self, enabled):
        self.pet.set_auto_move(enabled)
        self.sync()

    def change_interval(self, key, value):
        self.pet.life.config[key + "_min"] = value
        self.pet.life.elapsed[key] = 0
        self.pet.save()

    def change_speed(self, value):
        self.pet.life.config["move_speed"] = value
        self.speed_per_minute.setText(f"Tương đương {value * 60:,} pixel/phút khi đi liên tục")
        self.pet.save()

    def change_action_pause(self, value):
        self.pet.life.config["action_pause"] = value
        if self.pet.state == "idle":
            self.pet.set_state("idle")
        self.pet.save()

    @staticmethod
    def update_value(widget, setter, value):
        previous = widget.blockSignals(True)
        try:
            setter(value)
        finally:
            widget.blockSignals(previous)

    def sync(self):
        config = self.pet.life.config
        self.update_value(self.message_enabled, self.message_enabled.setChecked, config['messages_enabled'])
        for key, spin in self.message_controls.items():
            if not spin.hasFocus():
                self.update_value(spin, spin.setValue, config[key])
        self.update_value(self.message_theme, self.message_theme.setCurrentIndex, self.message_theme.findData(config['message_theme']))
        if not self.message_text.hasFocus():
            self.message_text.setText(config['message_preview'])
        self.message_test.setEnabled(config['messages_enabled'])
        self.dialogue_test.setEnabled(config['messages_enabled'])
        locked = self.pet.motion_locked
        for widget in (self.models, self.sizes, self.run_activity, self.auto, self.stay, self.pause):
            widget.setEnabled(not locked)
        self.begin_meditation.setEnabled(not locked)
        self.end_meditation.setEnabled(self.pet.life.meditation > 0)
        seconds = math.ceil(self.pet.life.meditation)
        self.meditation_status.setText(f"Còn {seconds//60:02d}:{seconds%60:02d} — đang khóa di chuyển" if seconds else 'Chưa bật chế độ thiền')
        if not self.meditation_minutes.hasFocus():
            self.update_value(self.meditation_minutes, self.meditation_minutes.setValue, config['meditation_min'])
        if not self.action_pause.hasFocus():
            self.update_value(self.action_pause, self.action_pause.setValue, config["action_pause"])
        self.visibility.setText("Hiện nhân vật" if self.pet.user_hidden else "Ẩn nhân vật")
        index = self.activity.findData(self.pet.state)
        label = self.activity.itemText(index) if index >= 0 else {"sleep": "Đang thiền", "jump": "Đang nhảy", "fall": "Đang rơi", "hang": "Đang treo"}.get(self.pet.state, self.pet.state)
        self.current_activity.setText(label)
        self.speed_per_minute.hide()
        self.speed.setToolTip(f"Khoảng {config['move_speed'] * 60:,} px/phút khi đi liên tục")
        if not self.speed.hasFocus():
            self.update_value(self.speed, self.speed.setValue, config["move_speed"])
        self.update_value(self.models, self.models.setCurrentIndex, self.models.findData(self.pet.spec["id"]))
        self.update_value(self.sizes, self.sizes.setCurrentIndex, self.sizes.findData(config["size"]))
        for widget, value in [(self.auto, config["auto_move"]), (self.stay, config["stay"]),
                              (self.pause, self.pet.floating), (self.perches, config["window_perches"]),
                              (self.fullscreen, config["hide_fullscreen"]), (self.follow_active, config['follow_active'])]:
            self.update_value(widget, widget.setChecked, value)
        for key, (check, interval) in self.reminders.items():
            self.update_value(check, check.setChecked, config["reminders"][key])
            if not interval.hasFocus():
                self.update_value(interval, interval.setValue, config[key + "_min"])
        life = self.pet.life
        text = f"Năng lượng {life.energy:.0f}% • Tình cảm {life.affection:.0f}%"
        self.status.setToolTip('\n'.join(filter(None, (
            self.pet.surface_scanner.status, self.pet.navigation_status,
            f'{len(life.favourites)} chỗ yêu thích'))))
        if life.meditation:
            seconds = math.ceil(life.meditation)
            text += f"\nĐang thiền: {seconds//60:02d}:{seconds%60:02d} — khóa di chuyển"
        if life.focus:
            text += f"\nĐang tập trung: còn {math.ceil(life.focus / 60)} phút"
        elif life.break_left:
            text += f"\nĐang nghỉ: còn {math.ceil(life.break_left / 60)} phút"
        self.status.setText(text)
