import sys
import argparse
from PySide6.QtWidgets import QApplication, QMessageBox
from pet.app import DesktopPet
from pet.platform_services import SingleInstance, set_app_identity


def main():
    parser = argparse.ArgumentParser(description="Vynn Notify desktop companion")
    parser.add_argument("--character", default=None, choices=("chibi_boy",))
    parser.add_argument("--background", action="store_true")
    parser.add_argument('--self-test', action='store_true', help=argparse.SUPPRESS)
    options = parser.parse_args()
    set_app_identity()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if options.self_test:
        import tempfile
        from PySide6.QtGui import QImage, QPainter
        with tempfile.TemporaryDirectory() as directory:
            pet = DesktopPet(data_dir=directory)
            try:
                for state in ('idle', 'walk', 'nap', 'sad', 'sit', 'look', 'stretch'):
                    canvas = QImage(240, 280, QImage.Format_ARGB32_Premultiplied)
                    canvas.fill(0)
                    painter = QPainter(canvas)
                    painter.scale(2, 2)
                    pet.renderer.paint(painter, state, 1.2, 1)
                    painter.end()
                    assert any(bytes(canvas.constBits())), state
                pet.show_settings()
                app.processEvents()
                assert not pet.settings.grab().isNull()
                assert pet.settings.tabs.count() == 3
                assert not pet.windowIcon().isNull()
            finally:
                pet.timer.stop()
                pet.scanner.stop()
                pet.saver.stop()
                if pet.settings:
                    pet.settings.close()
                if pet.tray:
                    pet.tray.hide()
                pet.bubble.close()
                pet.close()
                pet.shutdown()
        return 0
    lock = SingleInstance()
    if not lock.acquired:
        lock.close()
        QMessageBox.information(None, "Vynn Notify", "Vynn Notify đang chạy. Bấm biểu tượng khay hệ thống để mở bảng điều chỉnh.")
        return 0
    try:
        pet = DesktopPet(options.character)
        pet.show()
        return app.exec()
    finally:
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
