"""Read visible Windows surfaces, converted from physical to Qt coordinates."""
import ctypes
import sys
import time
from ctypes import wintypes
from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication

_monitor_cache = (0, [])


def monitor_mappings():
    global _monitor_cache
    now = time.monotonic()
    if now-_monitor_cache[0] < 1:
        return _monitor_cache[1]
    screens = QGuiApplication.screens()
    mappings = []
    if sys.platform == 'win32':
        class MonitorInfo(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                        ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD), ('szDevice', wintypes.WCHAR*32)]
        user = ctypes.WinDLL('user32')
        user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
                                          ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
        @callback_type
        def callback(handle, dc, rect, data):
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(info)
            if user.GetMonitorInfoW(handle, ctypes.byref(info)):
                screen = next((screen for screen in screens if screen.name().casefold() == info.szDevice.casefold()), None)
                if screen:
                    r = info.rcMonitor
                    mappings.append((QRect(r.left, r.top, r.right-r.left, r.bottom-r.top),
                                     screen.geometry(), screen.devicePixelRatio()))
            return True
        user.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.c_void_p, callback_type, wintypes.LPARAM]
        user.EnumDisplayMonitors(None, None, callback, 0)
    if not mappings:
        mappings = [(QRect(screen.geometry().left(), screen.geometry().top(),
                           round(screen.geometry().width()*screen.devicePixelRatio()),
                           round(screen.geometry().height()*screen.devicePixelRatio())),
                     screen.geometry(), screen.devicePixelRatio()) for screen in screens]
    _monitor_cache = (now, mappings)
    return mappings


def map_physical_rect(rect, mappings):
    if not mappings:
        return QRect(rect.left, rect.top, rect.right-rect.left, rect.bottom-rect.top)
    raw = QRect(rect.left, rect.top, rect.right-rect.left, rect.bottom-rect.top)
    def score(mapping):
        intersection = raw.intersected(mapping[0])
        return max(0, intersection.width())*max(0, intersection.height())
    physical, logical, ratio = max(mappings, key=score)
    return QRect(round(logical.left()+(rect.left-physical.left())/ratio),
                 round(logical.top()+(rect.top-physical.top())/ratio),
                 round((rect.right-rect.left)/ratio), round((rect.bottom-rect.top)/ratio))


def window_kind(hwnd):
    if sys.platform != 'win32':
        return 'window'
    user = ctypes.WinDLL('user32')
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    name = ctypes.create_unicode_buffer(256)
    user.GetClassNameW(hwnd, name, len(name))
    if name.value in ('Shell_TrayWnd', 'Shell_SecondaryTrayWnd'):
        return 'taskbar'
    if name.value == 'SysListView32':
        return 'desktop'
    return 'widget' if user.GetWindowLongW(hwnd, -20) & 0x80 else 'window'


def logical_rect(rect):
    return map_physical_rect(rect, monitor_mappings())


def scan(ignore):
    if sys.platform != "win32":
        return [], False
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsIconic.argtypes = [wintypes.HWND]
    user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    user.FindWindowExW.restype = wintypes.HWND
    dwm = ctypes.WinDLL("dwmapi")
    dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    front = user.GetForegroundWindow()
    surfaces, fullscreen = [], False
    desktop = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd, _):
        nonlocal fullscreen
        if hwnd in ignore or not user.IsWindowVisible(hwnd) or user.IsIconic(hwnd):
            return True
        class_name = ctypes.create_unicode_buffer(256)
        user.GetClassNameW(hwnd, class_name, len(class_name))
        if class_name.value in ("Progman", "WorkerW"):
            view = user.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
            icons = user.FindWindowExW(view, None, "SysListView32", None) if view else None
            rect = wintypes.RECT()
            if icons and user.GetWindowRect(icons, ctypes.byref(rect)):
                desktop.append((icons, logical_rect(rect)))
        if class_name.value in ('Shell_TrayWnd', 'Shell_SecondaryTrayWnd'):
            rect = wintypes.RECT()
            if user.GetWindowRect(hwnd, ctypes.byref(rect)):
                surfaces.append((hwnd, logical_rect(rect)))
            return True
        if class_name.value in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            return True
        if not user.GetWindowTextLengthW(hwnd):
            return True
        cloaked = wintypes.DWORD()
        if dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)) == 0 and cloaked.value:
            return True
        rect = wintypes.RECT()
        # GetWindowRect includes invisible resize borders; use the visible edge.
        if dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)) != 0:
            if not user.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True
        bounds = logical_rect(rect)
        if user.GetWindowLongW(hwnd, -20) & 0x80 and (bounds.width() > 600 or bounds.height() > 500):
            return True
        if bounds.width() < 100 or bounds.height() < 60:
            return True
        surfaces.append((hwnd, bounds))
        if hwnd == front:
            fullscreen = any(bounds.contains(s.geometry()) for s in QGuiApplication.screens())
        return True

    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.EnumWindows.restype = wintypes.BOOL
    user.EnumWindows(callback, 0)
    return surfaces + desktop, fullscreen
