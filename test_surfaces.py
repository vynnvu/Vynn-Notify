"""Stable ledge matching, interior rules and isolated worker protocol."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import unittest
from unittest.mock import patch
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication
from pet.surfaces import SurfaceTracker, SurfaceScanner
from pet.environment import Scene
from pet.navigation import Ledge, plan_route
from pet.desktop_icons import read_icons
from pet.windows import map_physical_rect
from ctypes import wintypes

app = QApplication.instance() or QApplication([])


def rect(row):
    return QRect(round(row['x']), round(row['y']), round(row['w']), round(row['h']))


def snapshot(stamp, items, desktop=False):
    return dict(hwnd=101, x=100, y=100, w=500, h=500, items=items, scanned_at=stamp, desktop=desktop)


def item(identity='a', x=130, y=220, kind='button'):
    return dict(id=identity, x=x, y=y, w=120, h=30, kind=kind)


class SurfaceTests(unittest.TestCase):
    def setUp(self):
        self.conversion = patch('pet.surfaces.to_rect', side_effect=rect)
        self.kind = patch('pet.surfaces.window_kind', return_value='window')
        self.conversion.start()
        self.kind.start()
        self.addCleanup(self.conversion.stop)
        self.addCleanup(self.kind.stop)
        self.tracker = SurfaceTracker()
        self.windows = [(101, QRect(100, 100, 500, 500))]

    def test_runtime_id_changes_keep_overlapping_ledge(self):
        first, _ = self.tracker.update(self.windows, [snapshot(1, [item()])], now=1)
        key = first[0][0]
        second, _ = self.tracker.update(self.windows, [snapshot(2, [item('new-runtime-id', x=132)])], now=2)
        self.assertEqual(second[0][0], key)
        self.assertEqual(second[0][1].left(), 132)

    def test_mixed_dpi_monitor_origins_and_negative_coordinates(self):
        maps = [(QRect(-1920, 0, 1920, 1080), QRect(-1920, 0, 1920, 1080), 1),
                (QRect(0, 0, 2560, 1440), QRect(0, 0, 1280, 720), 2)]
        self.assertEqual(map_physical_rect(wintypes.RECT(200, 200, 600, 400), maps), QRect(100, 100, 200, 100))
        self.assertEqual(map_physical_rect(wintypes.RECT(-1800, 200, -1600, 400), maps), QRect(-1800, 200, 200, 200))

    def test_owner_movement_preserves_relative_bounds(self):
        row = snapshot(1, [item()])
        first, _ = self.tracker.update(self.windows, [row], now=1)
        moved, _ = self.tracker.update([(101, QRect(140, 120, 500, 500))], [row], now=1.5)
        self.assertEqual(moved[0][0], first[0][0])
        self.assertEqual(moved[0][1].topLeft(), first[0][1].translated(40, 20).topLeft())

    def test_only_occupied_disappeared_ledge_has_brief_grace(self):
        first, _ = self.tracker.update(self.windows, [snapshot(1, [item(), item('b', y=300)])], now=1)
        key = first[0][0]
        rows = [snapshot(1.3, [])]
        held, _ = self.tracker.update(self.windows, rows, retain_key=key, now=1.3)
        self.assertEqual([k for k, _ in held if isinstance(k, tuple)], [key])
        self.assertTrue(self.tracker.metadata[key]['remembered'])
        expired, _ = self.tracker.update(self.windows, rows, retain_key=key, now=2.5)
        self.assertNotIn(key, [k for k, _ in expired])

    def test_window_closure_and_stale_scans_remove_platforms(self):
        first, _ = self.tracker.update(self.windows, [snapshot(1, [item()])], now=1)
        key = first[0][0]
        stale, _ = self.tracker.update(self.windows, [snapshot(1, [item()])], retain_key=key, now=9)
        self.assertNotIn(key, [k for k, _ in stale])
        self.assertEqual(self.tracker.update([], [], retain_key=key, now=10)[0], [])

    def test_icons_are_solid_and_icon_host_not_a_floor(self):
        surfaces, _ = self.tracker.update(self.windows, [snapshot(1, [item(kind='icon')], desktop=True)], now=1)
        self.assertEqual(len(surfaces), 1)
        info = self.tracker.metadata[surfaces[0][0]]
        self.assertEqual((info['kind'], info['space'], info['solid']), ('icon', 'desktop', True))

    def test_scene_interior_does_not_catch_behind_window(self):
        inside, icon = (101, 'edit'), (202, 'icon')
        windows = [(101, QRect(100, 100, 500, 500)), (202, QRect(0, 0, 1000, 800))]
        surfaces = [(inside, QRect(130, 300, 150, 30)), (101, windows[0][1]), (icon, QRect(140, 400, 40, 40))]
        metadata = {inside: dict(owner=101, space='inside', solid=False), 101: dict(owner=101, space='desktop', solid=False),
                    icon: dict(owner=202, space='desktop', solid=True)}
        scene = Scene(windows, surfaces, metadata)
        self.assertFalse(scene.standable(inside, 170, 300, 20, 50))
        self.assertTrue(scene.standable(inside, 170, 300, 20, 50, inside=101))
        self.assertTrue(scene.standable(inside, 170, 300, 20, 50, entering=101))
        self.assertFalse(scene.standable(icon, 160, 400, 20, 50, inside=101))
        self.assertFalse(scene.covered(inside, 170, 300))

    def test_headroom_blocks_icon_column_with_insufficient_space(self):
        surfaces = [('upper', QRect(100, 100, 50, 30)), ('lower', QRect(100, 170, 50, 30))]
        metadata = {k: dict(owner=1, space='desktop', solid=True) for k, _ in surfaces}
        scene = Scene([(1, QRect(0, 0, 500, 500))], surfaces, metadata)
        self.assertFalse(scene.headroom('lower', 125, 170, 30, 60))
        self.assertTrue(scene.headroom('lower', 125, 170, 30, 30))

    def test_route_cannot_jump_between_two_app_interiors(self):
        ledges = [Ledge('a', 50, 300, 150, 320, False, 1, 'inside', 'edit'),
                  Ledge('b', 170, 270, 240, 290, False, 2, 'inside', 'edit')]
        route = plan_route(100, 300, 'a', 'b', ledges, 20, 30, 700, 0, 500, 0)
        self.assertEqual(route, [])

    @unittest.skipUnless(sys.platform == 'win32', 'Windows only')
    def test_persistent_worker_reuses_process_and_recovers(self):
        scanner = SurfaceScanner()
        try:
            self.assertIsInstance(scanner.query(0), list)
            pid = scanner.process.pid
            self.assertIsInstance(scanner.query(0), list)
            self.assertEqual(scanner.process.pid, pid)
            scanner.process.kill()
            scanner.process.wait(timeout=2)
            self.assertIsInstance(scanner.query(0), list)
            self.assertNotEqual(scanner.process.pid, pid)
            self.assertIsNone(read_icons(0))
        finally:
            scanner.close()
            scanner.thread.join(timeout=2)
            self.assertFalse(scanner.thread.is_alive())


if __name__ == '__main__':
    unittest.main()
