"""Windows startup, foreground identity and lifetime single-instance lock."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_VALUE = 'Vynn Notify'


def set_app_identity():
    if sys.platform == 'win32':
        shell = ctypes.WinDLL('shell32')
        shell.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]
        shell.SetCurrentProcessExplicitAppUserModelID('Vynn.Notify.DesktopPet')


def startup_command():
    if getattr(sys, 'frozen', False):
        args = [sys.executable, '--background']
    else:
        executable = Path(sys.executable)
        windowless = executable.with_name('pythonw.exe')
        args = [str(windowless if windowless.exists() else executable),
                str(Path(__file__).resolve().parents[1] / 'main.py'), '--background']
    return subprocess.list2cmdline(args)


def autostart_enabled():
    if sys.platform != 'win32':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            command, _ = winreg.QueryValueEx(key, RUN_VALUE)
        return command == startup_command()
    except OSError:
        return False


def set_autostart(enabled):
    if sys.platform != 'win32':
        raise OSError('Chỉ hỗ trợ tự khởi động trên Windows.')
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass


class SingleInstance:
    def __init__(self, name=r'Local\VynnNotify.DesktopPet.v2'):
        self.handle = None
        self.acquired = True
        if sys.platform == 'win32':
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
            self.kernel.CreateMutexW.restype = wintypes.HANDLE
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.handle = self.kernel.CreateMutexW(None, False, name)
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
            self.acquired = ctypes.get_last_error() != 183

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def foreground():
    if sys.platform != 'win32':
        return None
    user = ctypes.WinDLL('user32')
    user.GetForegroundWindow.restype = wintypes.HWND
    return user.GetForegroundWindow()


def window_identity(hwnd):
    if sys.platform != 'win32' or not isinstance(hwnd, int):
        return str(hwnd)
    user = ctypes.WinDLL('user32')
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    name = ctypes.create_unicode_buffer(256)
    user.GetClassNameW(hwnd, name, len(name))
    return name.value or 'window'
