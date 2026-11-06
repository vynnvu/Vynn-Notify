"""Soft charcoal controls shared by the settings window and tray menu."""
from pathlib import Path
MENU_STYLE = """
QMenu { background: #232323; color: #e5e5e5; border: 1px solid #3c3c3c;
        border-radius: 10px; padding: 7px; font-family: 'Segoe UI'; font-size: 13px; }
QMenu::item { padding: 8px 24px 8px 12px; border-radius: 6px; }
QMenu::item:selected { background: #3a3a3a; color: #f0f0f0; }
QMenu::item:disabled { color: #858585; }
QMenu::separator { height: 1px; background: #383838; margin: 5px 8px; }
"""

SETTINGS_STYLE = """
QWidget { color: #e5e5e5; font-family: 'Segoe UI'; font-size: 13px; }
QWidget#settingsRoot, QWidget#settingsContent { background: #191919; }
QScrollArea { border: none; background: transparent; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #232323; color: #a9a9a9; padding: 10px 22px;
    margin-right: 6px; border-radius: 7px; }
QTabBar::tab:selected { background: #3a3a3a; color: #ffffff; }
QTabBar::tab:hover { background: #303030; }
QWidget#sectionBody { background: #232323; border: 1px solid #373737; border-radius: 10px; }
QToolButton#sectionHeader { background: #2c2c2c; color: #dedede;
    border: 1px solid #414141; border-radius: 8px; padding: 10px;
    font-weight: 600; text-align: left; }
QToolButton#sectionHeader:hover { background: #383838; }
QToolButton#sectionHeader:checked { background: #303030; }
QLabel { background: transparent; }
QPushButton { background: #303030; color: #dedede; border: 1px solid #484848;
    border-radius: 7px; padding: 8px 12px; font-weight: 500; }
QPushButton:hover { background: #3d3d3d; border-color: #666666; }
QPushButton:pressed { background: #484848; }
QPushButton:disabled { background: #262626; color: #7f7f7f; border-color: #373737; }
QPushButton[role="primary"] { background: #474747; color: #ffffff; border-color: #474747; }
QPushButton[role="primary"]:hover { background: #575757; }
QPushButton[role="primary"]:disabled { background: #333333; border-color: #333333; color: #858585; }
QPushButton[role="stop"] { background: #342c2c; color: #dfb9b4; border-color: #554242; }
QPushButton[role="stop"]:hover { background: #433232; }
QPushButton[role="stop"]:disabled { background: #292727; color: #8b8080; border-color: #3b3333; }
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox { background: #1e1e1e; color: #e5e5e5;
    border: 1px solid #454545; border-radius: 6px; padding: 6px; selection-background-color: #505050;
    selection-color: #e5e5e5; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #8a8a8a; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled { background: #252525; color: #7f7f7f; }
QComboBox QAbstractItemView { background: #232323; color: #e5e5e5; border: 1px solid #454545;
    selection-background-color: #404040; selection-color: #dedede; padding: 4px; }
QCheckBox { spacing: 8px; background: transparent; padding: 3px 0; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #606060; border-radius: 4px; background: #1e1e1e; }
QCheckBox::indicator:checked { background: #686868; border-color: #686868; image: url("__CHECK_ICON__"); }
QCheckBox::indicator:disabled { border-color: #414141; background: #2b2b2b; }
QCheckBox:disabled { color: #7f7f7f; }
QScrollBar:vertical { background: #1c1c1c; width: 9px; margin: 2px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #484848; min-height: 26px; border-radius: 3px; }
QScrollBar::handle:vertical:hover { background: #626262; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { background: #232323; color: #dedede; border: 1px solid #494949; padding: 5px; }
"""
SETTINGS_STYLE = SETTINGS_STYLE.replace('__CHECK_ICON__', Path(__file__).with_name('check.svg').as_posix())
