"""Persistent, isolated UI Automation worker and stable ledge tracking."""
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from ctypes import wintypes
from PySide6.QtCore import QRect
from pet.windows import logical_rect, window_kind
from pet.desktop_icons import read_icons, class_name


class SurfaceScanner:
    def __init__(self):
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.targets, self.results = [], {}
        self.front = None
        self.process = None
        self.status = 'Đang khởi tạo bộ dò bề mặt…'
        self.thread = threading.Thread(target=self.run, daemon=True, name='vynn-notify-surfaces')
        self.thread.start()

    def request(self, handles, foreground=None):
        with self.lock:
            self.targets = list(dict.fromkeys(handles))[:8]
            self.front = foreground
            self.results = {key: value for key, value in self.results.items() if key in self.targets}

    def snapshot(self):
        with self.lock:
            return [dict(row) for row in self.results.values()]

    def stop_process(self):
        process, self.process = self.process, None
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=.5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
            for stream in (process.stdin, process.stdout):
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass

    def close(self):
        self.stop_event.set()
        process = self.process
        if process is not None:
            try:
                process.terminate()
            except OSError:
                pass

    def start_process(self):
        self.stop_process()
        self.output = queue.Queue()
        process = subprocess.Popen(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
             '-File', str(Path(__file__).with_name('surface_scan.ps1'))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding='utf-8', errors='replace', bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.process = process
        output = self.output
        def reader():
            try:
                for line in process.stdout:
                    output.put(line)
            except (OSError, ValueError):
                pass
            output.put(None)
        threading.Thread(target=reader, daemon=True, name='vynn-notify-uia-pipe').start()

    def query(self, hwnd):
        if self.process is None or self.process.poll() is not None:
            self.start_process()
        self.process.stdin.write(json.dumps([hwnd])+'\n')
        self.process.stdin.flush()
        deadline = time.monotonic()+5
        while not self.stop_event.is_set() and time.monotonic() < deadline:
            try:
                line = self.output.get(timeout=.1)
            except queue.Empty:
                continue
            if line is None:
                raise OSError('UI Automation worker exited')
            rows = json.loads(line.lstrip('\ufeff'))
            if not isinstance(rows, list):
                raise ValueError('Unexpected surface data')
            return rows
        raise TimeoutError('UI Automation provider timed out')

    def run(self):
        due = {}
        try:
            while not self.stop_event.is_set():
                with self.lock:
                    targets, front = list(self.targets), self.front
                now = time.monotonic()
                due = {key: due.get(key, now) for key in targets}
                ready = [key for key in targets if due.get(key, 0) <= now]
                ready.sort(key=lambda key: (0 if key != front and now-due[key] >= 3 else 1,
                                           key != front, due[key], targets.index(key)))
                if ready and sys.platform == 'win32':
                    hwnd = ready[0]
                    due[hwnd] = now+(1 if hwnd == front else 3)
                    try:
                        if class_name(hwnd) == 'SysListView32':
                            row = read_icons(hwnd)
                            rows = [row] if row is not None else []
                        elif window_kind(hwnd) == 'taskbar':
                            rows = []
                        else:
                            rows = self.query(hwnd)
                        now = time.monotonic()
                        for row in rows:
                            row['scanned_at'] = now
                        with self.lock:
                            for row in rows:
                                if row['hwnd'] in self.targets:
                                    self.results[row['hwnd']] = row
                            count = sum(len(row['items']) for row in self.results.values())
                        self.status = f'Đã dò {count} bề mặt · UIA nền / icon Win32'
                    except (OSError, ValueError, TimeoutError):
                        self.stop_process()
                        self.status = 'Một ứng dụng chưa phản hồi; đang giữ dữ liệu mới nhất và thử lại.'
                        due[hwnd] = time.monotonic()+4
                self.stop_event.wait(.1)
        finally:
            self.stop_process()


def to_rect(row):
    return logical_rect(wintypes.RECT(round(row['x']), round(row['y']),
                                     round(row['x']+row['w']), round(row['y']+row['h'])))


def merge_surfaces(windows, rows):
    """Compatibility helper for untracked snapshots; live app uses SurfaceTracker."""
    by_owner = {row['hwnd']: row for row in rows}
    surfaces, owners = [], {}
    for hwnd, window in windows:
        row = by_owner.get(hwnd)
        if row:
            scanned_window = to_rect(row)
            delta = window.topLeft()-scanned_window.topLeft()
            seen = set()
            for item in row['items']:
                rect = to_rect(item).translated(delta).intersected(window)
                edge = (rect.left(), rect.top(), rect.right())
                if rect.width() < 20 or rect.height() < 4 or edge in seen:
                    continue
                seen.add(edge)
                key = (hwnd, item['id'])
                surfaces.append((key, rect))
                owners[key] = hwnd
        surfaces.append((hwnd, window))
        owners[hwnd] = hwnd
    return surfaces, owners


class SurfaceTracker:
    """Match relative ledges by runtime ID, overlap and nearby geometry."""
    def __init__(self, grace=1.25, stale_after=7):
        self.grace, self.stale_after = grace, stale_after
        self.history, self.tokens, self.serial = {}, {}, 0
        self.metadata = {}

    @staticmethod
    def similarity(a, b):
        intersection = a.intersected(b)
        area = max(0, intersection.width())*max(0, intersection.height())
        union = a.width()*a.height()+b.width()*b.height()-area
        overlap = area/max(1, union)
        # A control's height can change while its standable top stays put.
        horizontal = max(0, min(a.right(), b.right())-max(a.left(), b.left())+1)
        edge = horizontal/max(1, max(a.width(), b.width())) if abs(a.top()-b.top()) <= 6 else 0
        return max(overlap, edge*.8)

    def update(self, windows, rows, retain_key=None, now=None):
        now = time.monotonic() if now is None else now
        live = dict(windows)
        for owner in list(self.history):
            if owner not in live:
                self.history.pop(owner, None)
                self.tokens.pop(owner, None)
        by_owner = {row['hwnd']: row for row in rows if row['hwnd'] in live}
        metadata, surfaces, owners = {}, [], {}
        for owner, window in windows:
            row = by_owner.get(owner)
            history = self.history.setdefault(owner, {})
            if row and now-row.get('scanned_at', now) > self.stale_after:
                row = None
                history.clear()
            if row:
                token = row.get('scanned_at', id(row))
                if self.tokens.get(owner) != token:
                    self.tokens[owner] = token
                    scanned = to_rect(row)
                    fresh, used, seen = {}, set(), set()
                    for item in row['items']:
                        relative = to_rect(item).translated(-scanned.left(), -scanned.top())
                        edge = (relative.left(), relative.top(), relative.right())
                        if relative.width() < 20 or relative.height() < 4 or edge in seen:
                            continue
                        seen.add(edge)
                        kind = item.get('kind', 'element')
                        best, score = None, .3
                        for key, old in history.items():
                            if key in used or now-old['seen'] > self.stale_after or old['kind'] != kind:
                                continue
                            value = self.similarity(relative, old['rect'])
                            if item['id'] == old['source']:
                                value = max(value, .95)
                            if value > score:
                                best, score = key, value
                        if best is None:
                            self.serial += 1
                            best = (owner, f'ledge:{self.serial}')
                        used.add(best)
                        fresh[best] = dict(rect=relative, source=item['id'], kind=kind, seen=now,
                                           observed=True, desktop=row.get('desktop', False))
                    for key, old in history.items():
                        if key not in fresh and now-old['seen'] <= self.grace:
                            fresh[key] = dict(old, observed=False)
                    self.history[owner] = history = fresh
            for key, item in history.items():
                age = now-item['seen']
                if age > self.stale_after or (not item['observed'] and (key != retain_key or age > self.grace)):
                    continue
                rect = item['rect'].translated(window.topLeft()).intersected(window)
                if rect.width() < 20 or rect.height() < 4:
                    continue
                desktop = item['desktop'] or item['kind'] == 'icon'
                surfaces.append((key, rect))
                owners[key] = owner
                metadata[key] = dict(owner=owner, kind=item['kind'],
                                     space='desktop' if desktop else 'inside', solid=desktop,
                                     remembered=not item['observed'])
            is_desktop = bool(row and row.get('desktop'))
            # Explorer's full-screen icon host is not itself a platform.
            kind = window_kind(owner)
            if not is_desktop and kind != 'desktop':
                surfaces.append((owner, window))
                owners[owner] = owner
                metadata[owner] = dict(owner=owner, kind=kind, space='desktop', solid=kind == 'widget', remembered=False)
        self.metadata = metadata
        return surfaces, owners
