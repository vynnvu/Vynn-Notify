"""Read Explorer icon image rectangles via its documented ListView messages."""
import ctypes
from ctypes import wintypes
import sys
import time


def class_name(hwnd):
    if sys.platform != 'win32':
        return ''
    user = ctypes.WinDLL('user32')
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    text = ctypes.create_unicode_buffer(256)
    user.GetClassNameW(hwnd, text, len(text))
    return text.value


def read_icons(hwnd, limit=200):
    """Return physical image bounds, not labels; never read file contents."""
    if sys.platform != 'win32' or class_name(hwnd) != 'SysListView32':
        return None
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t,
                                       wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    user.SendMessageTimeoutW.restype = ctypes.c_ssize_t
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    kernel.VirtualAllocEx.restype = ctypes.c_void_p
    for name in ('ReadProcessMemory', 'WriteProcessMemory'):
        getattr(kernel, name).argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    area = wintypes.RECT()
    if not user.GetWindowRect(hwnd, ctypes.byref(area)):
        return None
    row = dict(hwnd=hwnd, x=area.left, y=area.top, w=area.right-area.left, h=area.bottom-area.top,
               desktop=True, items=[])
    if not user.IsWindowVisible(hwnd):
        return row
    result = ctypes.c_size_t()
    if not user.SendMessageTimeoutW(hwnd, 0x1004, 0, 0, 2, 100, ctypes.byref(result)):
        return None
    count = min(limit, result.value)
    pid = wintypes.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process = kernel.OpenProcess(0x1038, False, pid.value)
    if not process:
        return None
    remote = None
    try:
        remote = kernel.VirtualAllocEx(process, None, ctypes.sizeof(wintypes.RECT), 0x3000, 4)
        if not remote:
            return None
        origin = wintypes.POINT()
        if not user.ClientToScreen(hwnd, ctypes.byref(origin)):
            return None
        deadline = time.monotonic()+.8
        for index in range(count):
            if time.monotonic() > deadline:
                break
            rect = wintypes.RECT(1, 0, 0, 0)  # LVIR_ICON, excludes label text.
            copied = ctypes.c_size_t()
            if not kernel.WriteProcessMemory(process, remote, ctypes.byref(rect), ctypes.sizeof(rect), ctypes.byref(copied)):
                continue
            if not user.SendMessageTimeoutW(hwnd, 0x100E, index, remote, 2, 80, ctypes.byref(result)) or not result.value:
                continue
            if not kernel.ReadProcessMemory(process, remote, ctypes.byref(rect), ctypes.sizeof(rect), ctypes.byref(copied)):
                continue
            if rect.right <= rect.left or rect.bottom <= rect.top:
                continue
            row['items'].append(dict(id=f'icon:{index}', kind='icon',
                x=origin.x+rect.left, y=origin.y+rect.top, w=rect.right-rect.left, h=rect.bottom-rect.top))
        return row
    finally:
        if remote:
            kernel.VirtualFreeEx(process, remote, 0, 0x8000)
        kernel.CloseHandle(process)
