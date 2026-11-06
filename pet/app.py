"""Vynn Notify transparent desktop companion."""
import math
import random
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QCursor
from PySide6.QtWidgets import QApplication, QWidget, QSystemTrayIcon, QLabel, QMenu
from pet.character_manager import load_character, available_characters
from pet.life import Life
from pet.windows import scan
from pet.surfaces import SurfaceScanner, SurfaceTracker
from pet.environment import Scene
from pet.behavior import GRAVITY, jump_velocity
from pet.navigation import Ledge, plan_route, plan_climb_route, clear_arc, integrate
from pet.platform_services import foreground, window_identity
from pet.message import MessageBubble
from pet.icons import character_icon
from pet.theme import MENU_STYLE


class DesktopPet(QWidget):
    def __init__(self, char_id=None, data_dir=None):
        super().__init__()
        self.life = Life(data_dir)
        self.route = deque()
        self.route_step = None
        self.route_goal = None
        self.route_future = None
        self.route_alternatives = deque()
        self.navigator = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vynn-notify-route")
        self.navigation_status = ""
        self.window_rects = {}
        self.last_foreground = None
        self.pending_foreground = None
        self.foreground_since = time.monotonic()
        self.last_memory = time.monotonic()
        chosen = char_id or self.life.config["character"]
        if chosen not in available_characters():
            chosen = "chibi_boy"
        self.spec, self.renderer = load_character(chosen)
        self.character_icon = character_icon(self.renderer)
        QApplication.instance().setWindowIcon(self.character_icon)
        self.setWindowIcon(self.character_icon)
        self.life.config["character"] = chosen
        self.settings = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setWindowTitle("Vynn Notify")
        self.state, self.facing = "idle", 1
        self.t0 = self.last_tick = self.state_start = time.monotonic()
        self.drag_offset = None
        self.press_position = None
        self.hold_timer = QTimer(self)
        self.hold_timer.setSingleShot(True)
        self.hold_timer.setInterval(200)
        self.hold_timer.timeout.connect(self.begin_drag)
        self.dragged = False
        self.high_five_target = None
        self.floating = False
        self.follow = False
        self.vy = 0.0
        self.vx = 0.0
        self.state_duration = self.activity_duration("idle")
        self.jump_target = None
        self.climb_target = None
        self.approach_target = None
        self.perch = None
        self.support_ref = None
        self.surfaces = []
        self.surface_owners = {}
        self.surface_tracker = SurfaceTracker()
        self.surface_metadata = {}
        self.scene = None
        self.surface_scanner = SurfaceScanner()
        self.user_hidden = False
        self.fullscreen = False
        self.messages = deque(maxlen=20)
        self.message_until = 0
        self.last_action_message = 0
        self.bubble = MessageBubble(self.dismiss_message)
        self.apply_message_settings()
        self.set_size(self.life.config["size"])
        bounds = QApplication.primaryScreen().availableGeometry()
        self.move(bounds.right() - self.width() - 60, bounds.bottom() - self.height() + 1)
        self.fx, self.fy = float(self.x()), float(self.y())
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.character_icon, self)
            self.tray.setToolTip(self.windowTitle())
            self.tray.setContextMenu(self.create_tray_controls())
            self.tray.activated.connect(self.tray_activated)
            self.tray.show()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.timer.start(33)
        self.scanner = QTimer(self)
        self.scanner.timeout.connect(self.scan_windows)
        self.scanner.start(500)
        self.saver = QTimer(self)
        self.saver.timeout.connect(self.save)
        self.saver.start(30000)
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        self.say_event('notice.startup')
        if self.motion_locked:
            self.set_state("sleep", force=True)

    def save(self):
        try:
            self.life.save()
        except OSError as exc:
            self.setToolTip(f"Could not save settings: {exc}")

    def shutdown(self):
        self.navigator.shutdown(wait=False, cancel_futures=True)
        self.surface_scanner.close()
        self.save()
        if self.settings:
            self.settings.close()
        self.bubble.close()
        if self.tray:
            self.tray.hide()

    def set_size(self, size):
        if hasattr(self, "fx") and self.motion_locked:
            return
        if hasattr(self, "route"):
            self.cancel_route()
        factor = {"Tiny": 0.35, "Small": 0.5, "Medium": 0.75, "Large": 1.0}.get(size, 0.5)
        old_bottom = self.y() + self.height()
        self.base_w = round(self.spec.get("width", 160) * factor)
        self.base_h = round(self.spec.get("height", 180) * factor)
        self.setFixedSize(self.base_w + 10, self.base_h + 10)
        if hasattr(self, "fy"):
            bounds = self.screen().availableGeometry()
            self.move(max(bounds.left(), min(self.x(), bounds.right() + 1 - self.width())),
                      max(bounds.top(), min(old_bottom - self.height(), bounds.bottom() + 1 - self.height())))
            self.fx = float(self.x())
            self.fy = float(self.y())
        self.life.config["size"] = size

    def show_settings(self):
        if self.settings is None:
            from pet.settings import SettingsWindow
            self.settings = SettingsWindow(self)
        self.settings.sync()
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def set_character(self, char_id):
        if self.motion_locked:
            return
        spec, renderer = load_character(char_id)
        self.spec, self.renderer = spec, renderer
        self.character_icon = character_icon(renderer)
        QApplication.instance().setWindowIcon(self.character_icon)
        self.setWindowIcon(self.character_icon)
        if self.settings:
            self.settings.setWindowIcon(self.character_icon)
        self.life.config["character"] = char_id
        self.setWindowTitle("Vynn Notify")
        if self.tray:
            self.tray.setIcon(self.character_icon)
            self.tray.setToolTip(self.windowTitle())
        self.set_size(self.life.config["size"])
        self.set_state("idle")
        self.follow, self.vy = False, 0
        self.update()
        self.save()

    def set_auto_move(self, enabled):
        self.life.config["auto_move"] = enabled
        self.life.config["stay"] = not enabled
        self.floating = False
        self.follow = False
        self.cancel_route()
        self.set_state("walk" if enabled else "idle")
        self.save()

    def say(self, text):
        if self.life.config['messages_enabled'] and str(text).strip():
            self.messages.append(str(text).strip()[:1200])

    def say_event(self, key, automatic=False, **values):
        text = self.life.dialogue(key, **values)
        if not text:
            return
        if automatic:
            now = time.monotonic()
            if self.messages or now < self.message_until or now-self.last_action_message < 5:
                return
            self.last_action_message = now
        self.say(text)

    def dismiss_message(self):
        self.message_until = 0
        self.bubble.hide()

    def apply_message_settings(self):
        self.bubble.configure(self.life.config, self.spec['name'].split(' - ')[0])
        if not self.life.config['messages_enabled']:
            self.messages.clear()
            self.dismiss_message()

    def preview_message(self):
        self.messages.clear()
        self.dismiss_message()
        self.say(self.life.config['message_preview'])

    def edge_visible(self, index, x, y):
        key = self.surfaces[index][0]
        if self.scene is not None and self.scene.surfaces is self.surfaces:
            return not self.scene.covered(key, x, y)
        owner = self.surface_owners.get(key, key)
        return not any(self.surface_owners.get(other, other) != owner and rect.contains(round(x), round(y))
                       for other, rect in self.surfaces[:index])

    def can_stand(self, key, x, y, inside=None, entering=None):
        if self.scene is None or self.scene.surfaces is not self.surfaces:
            return True
        return self.scene.standable(key, x, y, self.width()*.5, self.height(), inside, entering)

    def snap_to_edge(self, tolerance=16):
        """Catch a visible ledge even when the drop is slightly below its top."""
        if not self.life.config["window_perches"]:
            return False
        cx = self.fx + self.width() / 2
        feet = self.fy + self.height()
        inside = self.scene.inside_owner(cx, feet-1, self.perch) if self.scene and self.scene.surfaces is self.surfaces else None
        candidates = []
        for index, (key, rect) in enumerate(self.surfaces):
            if (rect.left() <= cx <= rect.right() and abs(feet - rect.top()) <= tolerance
                    and rect.top() - self.height() >= self.screen().availableGeometry().top()
                    and self.edge_visible(index, cx, rect.top()) and self.can_stand(key, cx, rect.top(), inside)):
                candidates.append((abs(feet - rect.top()), index, key, rect))
        if not candidates:
            return False
        _, _, self.perch, rect = min(candidates, key=lambda item: item[:2])
        self.fy = float(rect.top() - self.height())
        self.support_ref = (self.perch, rect)
        self.vy = 0
        self.move(round(self.fx), round(self.fy))
        self.set_state("idle")
        return True

    def activity_duration(self, state):
        if state == "high_five":
            return .65
        if state == "idle":
            pause = self.life.config["action_pause"]
            return random.uniform(pause * .7, pause * 1.3)
        ranges = {"walk": (1.5, 3), "sleep": (8, 12), "nap": (10, 16), "sit": (3, 6),
                  "look": (3, 5), "groom": (2, 4), "stretch": (2, 4),
                  "dance": (2, 4), "sad": (2, 4)}
        return random.uniform(*ranges.get(state, (3, 5)))

    @property
    def motion_locked(self):
        return self.life.meditation > 0 or self.life.focus > 0

    def start_meditation(self, minutes=None):
        self.hold_timer.stop()
        self.press_position = None
        self.cancel_route()
        self.life.meditation = 60 * (minutes if minutes is not None else self.life.config["meditation_min"])
        self.drag_offset = None
        self.follow = False
        self.vx = self.vy = 0
        self.set_state("sleep", force=True)
        self.say_event('notice.meditation_start', minutes=round(self.life.meditation/60))
        self.save()

    def stop_meditation(self):
        was_active = self.life.meditation > 0
        self.life.meditation = 0
        if not self.life.focus:
            self.set_state("look", force=True)
        self.save()
        if was_active:
            self.say_event('notice.meditation_stop')

    def set_state(self, state, force=False):
        if self.motion_locked and state != "sleep" and not force:
            return
        changed = self.state != state
        self.state = state
        self.state_start = time.monotonic()
        self.state_duration = self.activity_duration(state)
        if state not in ('walk', 'jump', 'climb', 'hang'):
            self.climb_target = None
        if state != "walk":
            self.approach_target = None
        if state not in ("jump", "fall"):
            self.vx = 0
            self.jump_target = None
        if changed and not force and state != 'high_five':
            self.say_event('action.'+state, automatic=True)

    def cancel_route(self):
        self.route.clear()
        self.route_step = self.route_goal = None
        self.route_alternatives.clear()
        if self.route_future is not None:
            self.route_future.cancel()
            self.route_future = None

    def nav_ledges(self):
        result = []
        for index, (key, rect) in enumerate(self.surfaces):
            if rect.width() < 20 or not self.edge_visible(index, rect.center().x(), rect.top()):
                continue
            # Large app/group backgrounds are enterable, not solid walls.
            info = self.surface_metadata.get(key)
            solid = info['solid'] if info else isinstance(key, tuple) and rect.height() <= 160 and rect.width() <= 500
            if self.scene and self.scene.surfaces is self.surfaces and not self.scene.headroom(key, rect.center().x(), rect.top(), self.width()*.5, self.height()):
                continue
            result.append(Ledge(key, rect.left(), rect.top(), rect.right()+1, rect.bottom()+1, solid,
                                info.get('owner') if info else None, info.get('space', 'desktop') if info else 'desktop', info.get('kind', 'object') if info else 'object'))
        return result

    def signature(self, key):
        rect = next((r for k, r in self.surfaces if k == key), None)
        if rect is None:
            return "desktop:floor"
        owner = self.surface_owners.get(key, key)
        window = self.window_rects.get(owner, rect)
        return f"{window_identity(owner)}:{round((rect.left()-window.left())/max(1,window.width())*20)}:{round((rect.top()-window.top())/max(1,window.height())*20)}:{round(rect.width()/max(1,window.width())*20)}"

    def request_route(self, target):
        if (self.motion_locked or self.floating or self.life.config["stay"] or not self.life.config["window_perches"]
                or self.state in ("jump", "fall", "climb", "hang") or self.drag_offset is not None):
            return False
        if self.route_future is not None or target == self.perch:
            return False
        self.cancel_route()
        self.route_goal = target
        bounds = self.screen().availableGeometry()
        self.route_future = self.navigator.submit(plan_route, self.fx+self.width()/2,
            self.fy+self.height(), self.perch, target, self.nav_ledges(), self.width()*.5, self.height(),
            bounds.bottom()+1, bounds.left(), bounds.right()+1, bounds.top())
        self.navigation_status = "Đang tìm đường…"
        return True

    def advance_route(self):
        if self.climb_target is not None:
            return
        if self.route_future is not None and self.route_future.done():
            try:
                self.route = deque(self.route_future.result())
            except Exception:
                self.route.clear()
            self.route_future = None
            self.navigation_status = f"Lộ trình: {len(self.route)} bước" if self.route else "Chưa có đường đi an toàn tới chỗ đó."
            if not self.route and self.route_alternatives:
                target = self.route_alternatives.popleft()
                remaining = list(self.route_alternatives)
                if self.request_route(target):
                    self.route_alternatives.extend(remaining)
        if not self.route or self.motion_locked or self.floating or self.life.config["stay"]:
            return
        for step in self.route:
            rect = next((r for key, r in self.surfaces if key == step.key), None)
            if step.key is not None and (rect is None or abs(rect.top()-step.y)>16 or not rect.left()-8 <= step.x <= rect.right()+8):
                self.cancel_route()
                self.navigation_status = "Đường đi thay đổi; đã hủy tuyến cũ."
                return
        if self.route_step is None:
            self.route_step = self.route[0]
            step = self.route_step
            rect = next((r for key, r in self.surfaces if key == step.key), None)
            if step.key is not None and (rect is None or abs(rect.top()-step.y)>8 or not rect.left() <= step.x <= rect.right()+1):
                self.cancel_route()
                self.navigation_status = "Bề mặt đã đổi; sẽ tìm đường lại."
                return
            if step.kind == "jump":
                velocity = jump_velocity(step.x-(self.fx+self.width()/2), step.y-(self.fy+self.height()))
                if velocity is None or not clear_arc(self.fx+self.width()/2, self.fy+self.height(), step.x, step.y,
                        velocity, self.nav_ledges(), self.width()*.5, self.height(), self.screen().availableGeometry().top()):
                    self.cancel_route()
                    return
                self.vx, self.vy = velocity
                self.jump_target = step.key
                self.perch, self.support_ref = None, None
                self.set_state("jump")
            elif step.kind == 'climb':
                remaining = deque(list(self.route)[1:])
                goal = self.route_goal
                if self.start_climb(target_key=step.key, allow_route=False):
                    self.route = remaining
                    self.route_goal = goal
                    self.route_step = None
                else:
                    self.cancel_route()
                return
            else:
                self.set_state("walk" if step.kind == "walk" else "climb")
        if self.route_step and self.route_step.kind == "walk":
            dx = self.route_step.x-(self.fx+self.width()/2)
            if abs(dx) < max(2, self.life.config["move_speed"]*.05):
                self.fx = self.route_step.x-self.width()/2
                self.route.popleft()
                self.route_step = None
                self.set_state("idle")
            else:
                self.facing = 1 if dx > 0 else -1
                if self.state != "walk":
                    self.set_state("walk")
                self.state_start = time.monotonic()
        if self.route_step and self.state == "idle" and self.route_step.kind != "walk":
            if self.perch == self.route_step.key:
                self.route.popleft()
                self.route_step = None
            else:
                self.cancel_route()

    def go_active_window(self):
        hwnd = self.pending_foreground or self.last_foreground or foreground()
        candidates = [key for key, _ in self.surfaces if self.surface_owners.get(key, key) == hwnd and key != self.perch]
        candidates.sort(key=lambda key: self.life.favourites.get(self.signature(key), 0), reverse=True)
        for key in candidates[:6]:
            if self.request_route(key):
                self.route_alternatives.extend(candidates[candidates.index(key)+1:6])
                return True
        self.navigation_status = "Chưa có bề mặt của cửa sổ đang dùng."
        return False

    def go_favourite(self):
        choices = sorted((key for key, _ in self.surfaces if key != self.perch),
                         key=lambda key: self.life.favourites.get(self.signature(key), 0), reverse=True)
        for key in choices:
            if self.life.favourites.get(self.signature(key), 0) and self.request_route(key):
                return True
        self.navigation_status = "Chưa thấy chỗ yêu thích trong các bề mặt hiện tại."
        return False

    def explore(self):
        """Pick one reachable perch; repeated choices allow gradual exploration."""
        if (not self.life.config["window_perches"] or self.life.config["stay"] or self.motion_locked
                or self.state in ("jump", "fall", "climb", "hang") or self.drag_offset is not None or self.floating):
            return False
        bounds = self.screen().availableGeometry()
        cx, feet = self.fx + self.width()/2, self.fy + self.height()
        candidates = []
        for index, (key, rect) in enumerate(self.surfaces):
            if key == self.perch or rect.width() < 30:
                continue
            tx = max(rect.left() + 10, min(cx, rect.right() - 10))
            if not bounds.left() + self.width()/2 <= tx <= bounds.right() - self.width()/2:
                continue
            dx, dy = tx - cx, rect.top() - feet
            velocity = jump_velocity(dx, dy)
            if velocity is None or (abs(dx) < 12 and abs(dy) < 8) or not self.edge_visible(index, tx, rect.top()):
                continue
            vx, vy = velocity
            if self.fy - vy * vy / (2 * GRAVITY) < bounds.top():
                continue
            if not clear_arc(cx, feet, tx, rect.top(), velocity, self.nav_ledges(), self.width()*.5, self.height(), bounds.top()):
                continue
            candidates.append((abs(dx) + abs(dy), key, velocity))
        if not candidates:
            choices = [key for key, _ in self.surfaces if key != self.perch]
            choices.sort(key=lambda key: self.life.favourites.get(self.signature(key), 0), reverse=True)
            if choices and self.request_route(choices[0]):
                return True
            # Approach a reachable-height ledge before jumping. Stay on the
            # current floor/perch and keep the same calm walking duration.
            for index, (key, rect) in enumerate(self.surfaces):
                tx = max(rect.left()+10, min(cx, rect.right()-10))
                dx, dy = tx-cx, rect.top()-feet
                current = next((r for k, r in self.surfaces if k == self.perch), bounds)
                if (key != self.perch and 120 < abs(dx) < 350 and -80 <= dy <= 80
                        and current.left() + 10 <= tx <= current.right() - 10
                        and self.edge_visible(index, tx, rect.top())):
                    self.approach_target = key
                    self.facing = 1 if dx > 0 else -1
                    self.set_state("walk")
                    return True
            return False
        _, self.jump_target, (self.vx, self.vy) = random.choice(sorted(candidates, key=lambda c: c[0])[:3])
        self.perch, self.support_ref = None, None
        if self.vx:
            self.facing = 1 if self.vx > 0 else -1
        self.set_state("jump")
        return True

    def choose_activity(self):
        if self.life.energy < 25 or self.life.focus:
            self.set_state("sleep" if self.life.focus else "nap")
            return
        if self.route or self.route_future:
            return
        # Free roaming stays on the current surface. Routes that need jumps
        # are only started by an explicit navigation command.
        feet = self.fy + self.height()
        if self.life.config["window_perches"] and random.random() < 0.15:
            walls = [rect for key, rect in self.surfaces
                     if key != self.perch and 0 < feet - rect.top() < 130 and rect.bottom() > feet
                     and min(abs(self.fx + self.width() - rect.left()), abs(self.fx - rect.right())) < 25]
            if walls:
                self.set_state("climb")
                return
        self.facing = random.choice((-1, 1))
        self.set_state(random.choices(["walk", "sit", "look", "groom", "stretch", "sleep"],
                                      weights=[25, 25, 20, 12, 10, 8])[0])

    def cross_to_neighbor(self, surface, next_x=None):
        """Walk across touching tab tops, or hop over a small gap/step."""
        if not self.life.config["window_perches"] or self.life.config["stay"] or self.life.focus:
            return False
        edge = surface.right() if self.facing > 0 else surface.left()
        cx = self.fx + self.width()/2
        candidates = []
        for index, (key, rect) in enumerate(self.surfaces):
            if key == self.perch or rect.width() < 24:
                continue
            near = rect.left() if self.facing > 0 else rect.right()
            gap = (near-edge)*self.facing
            if not -4 <= gap <= 45 or abs(rect.top()-surface.top()) > 70:
                continue
            tx = near + self.facing*min(14, rect.width()/2)
            bounds = self.screen().availableGeometry()
            if not bounds.left()+self.width()/2 <= tx <= bounds.right()-self.width()/2:
                continue
            if not self.edge_visible(index, tx, rect.top()):
                continue
            candidates.append((abs(gap)+abs(rect.top()-surface.top()), key, rect, tx))
        for _, key, rect, tx in sorted(candidates, key=lambda c: c[0]):
            if abs(rect.top()-surface.top()) <= 4 and (rect.left() <= edge+1 <= rect.right() or rect.left() <= edge-1 <= rect.right()):
                self.perch = key
                self.support_ref = (key, rect)
                self.fx = next_x if next_x is not None else tx-self.width()/2
                self.fy = float(rect.top()-self.height())
                return True
            velocity = jump_velocity(tx-cx, rect.top()-surface.top(), max_rise=95)
            if velocity:
                vx, vy = velocity
                if self.fy-vy*vy/(2*GRAVITY) < self.screen().availableGeometry().top():
                    continue
                self.vx, self.vy, self.jump_target = vx, vy, key
                self.perch, self.support_ref = None, None
                self.set_state("jump")
                return True
        return False

    def jump(self):
        if self.motion_locked or self.state in ("jump", "fall"):
            return
        self.perch = None
        self.vx = 0
        self.vy = -math.sqrt(2 * GRAVITY * self.spec["animation"].get("jump_height", 75))
        self.set_state("jump")

    def scan_windows(self):
        ignored = {int(self.winId()), int(self.bubble.winId())}
        if self.settings:
            ignored.add(int(self.settings.winId()))
        windows, self.fullscreen = scan(ignored)
        self.window_rects = dict(windows)
        # Scan the two front windows and the backmost desktop/icon surface.
        current = foreground()
        owner = self.surface_owners.get(self.perch)
        targets = [key for key in (current, owner) if key in self.window_rects]
        targets.extend(hwnd for hwnd, _ in windows[:4])
        targets.extend(hwnd for hwnd, _ in windows[-1:])
        self.surface_scanner.request(targets, foreground=current)
        self.surfaces, self.surface_owners = self.surface_tracker.update(windows, self.surface_scanner.snapshot(), retain_key=self.perch)
        self.surface_metadata = self.surface_tracker.metadata
        self.scene = Scene(windows, self.surfaces, self.surface_metadata)
        if current not in ignored and current in self.window_rects and current != self.last_foreground:
            self.last_foreground = self.pending_foreground = current
            self.foreground_since = time.monotonic()
        if (self.pending_foreground and time.monotonic()-self.foreground_since > 2
                and self.life.config["follow_active"] and self.life.config["auto_move"]
                and not self.route and self.route_future is None and self.state in ("idle", "look", "sit")):
            if self.go_active_window():
                self.pending_foreground = None
        hidden = self.user_hidden or (self.fullscreen and self.life.config["hide_fullscreen"])
        self.setVisible(not hidden)
        if hidden:
            self.bubble.hide()

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.user_hidden = False
            self.scan_windows()
            self.show_settings()

    def create_tray_controls(self):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        self.tray_actions = {}
        def add(key, label, callback, checkable=False):
            action = menu.addAction(label)
            action.setCheckable(checkable)
            action.triggered.connect(callback)
            self.tray_actions[key] = action
        add('settings', 'Mở bảng điều chỉnh', self.show_settings)
        add('visibility', 'Ẩn / hiện nhân vật', self.toggle_hidden)
        menu.addSeparator()
        add('auto', 'Tự động di chuyển', self.set_auto_move, True)
        add('pause', 'Tạm dừng chuyển động', self.set_paused, True)
        add('call', 'Gọi lại', self.call)
        add('active', 'Tới cửa sổ đang dùng', self.go_active_window)
        add('high_five', 'Đập tay', self.high_five)
        menu.addSeparator()
        add('meditate', 'Bắt đầu thiền', lambda: self.start_meditation())
        add('stop_meditate', 'Dừng thiền', self.stop_meditation)
        add('stop_focus', 'Dừng tập trung / nghỉ', self.life.stop_focus)
        menu.addSeparator()
        add('quit', 'Thoát Vynn Notify', QApplication.instance().quit)
        menu.aboutToShow.connect(self.sync_tray_controls)
        return menu

    def show_action_menu(self, position):
        previous = getattr(self, 'action_menu', None)
        if previous is not None:
            previous.close()
            previous.deleteLater()
        menu = self.action_menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        if self.life.meditation > 0:
            menu.addAction('Dừng thiền', self.stop_meditation)
        if self.life.focus > 0 or self.life.break_left > 0:
            menu.addAction('Dừng tập trung', self.life.stop_focus)
        if self.state == 'nap':
            menu.addAction('Đánh thức', lambda: self.perform_action('idle'))
        elif self.climb_target is not None or self.state in ('climb', 'hang'):
            menu.addAction('Dừng leo', self.stop_climbing)
        elif self.route or self.route_future is not None:
            menu.addAction('Dừng tìm đường', lambda: self.perform_action('idle'))
        if menu.actions():
            menu.addSeparator()
        for label, callback in [('Đập tay', self.high_five), ('Nhảy', self.jump),
                                ('Tìm chỗ leo', lambda: self.start_climb()),
                                ('Ngủ', lambda: self.perform_action('nap'))]:
            action = menu.addAction(label)
            action.triggered.connect(callback)
            action.setEnabled(not self.motion_locked)
        menu.addSeparator()
        activities = menu.addMenu('Hoạt động')
        activities.setStyleSheet(MENU_STYLE)
        for label, state in [('Đi bộ', 'walk'), ('Ngồi nghỉ', 'sit'),
                             ('Quan sát', 'look'), ('Vuốt tóc', 'groom'),
                             ('Vươn vai', 'stretch'), ('Nhảy múa', 'dance'),
                             ('Buồn', 'sad'), ('Ngồi thiền', 'sleep')]:
            action = activities.addAction(label)
            action.triggered.connect(lambda checked=False, state=state: self.perform_action(state))
            action.setEnabled(not self.motion_locked)
        activities.setEnabled(not self.motion_locked)
        menu.addAction('Gọi lại', self.call).setEnabled(not self.motion_locked)
        menu.popup(position)

    def stop_climbing(self):
        if not self.motion_locked:
            self.cancel_route()
            self.climb_target = None
            self.perch, self.support_ref = None, None
            self.vx = self.vy = 0
            self.set_state('fall')

    def perform_action(self, state):
        if not self.motion_locked:
            self.cancel_route()
            self.follow = False
            if state == 'climb':
                self.start_climb()
            else:
                self.set_state(state)

    def start_climb(self, target_key=None, allow_route=True):
        if self.motion_locked or self.drag_offset is not None:
            return False
        bounds = self.screen().availableGeometry()
        feet = self.fy+self.height()
        support = next((rect for key, rect in self.surfaces if key == self.perch), None)
        if support is None and abs(feet-(bounds.bottom()+1)) > 3:
            self.say_event('notice.climb_unavailable')
            return False
        choices = []
        if self.life.config['window_perches'] and not self.floating:
            for index, (key, rect) in enumerate(self.surfaces):
                if target_key is not None and key != target_key:
                    continue
                if key == self.perch or rect.top() < bounds.top()+self.height() or rect.width() < 30:
                    continue
                for side in (-1, 1):
                    x = rect.left()-self.width() if side < 0 else rect.right()+1
                    if not bounds.left() <= x <= bounds.right()+1-self.width():
                        continue
                    # Jump onto the side below the ledge, then climb vertically.
                    catch_y = max(rect.top()+self.height()*.6, feet-45)
                    if catch_y >= rect.bottom() or catch_y >= feet:
                        continue
                    edge_x = rect.left()+2 if side < 0 else rect.right()-2
                    if not self.edge_visible(index, edge_x, rect.top()):
                        continue
                    launch_x = self.fx
                    velocity = jump_velocity(x-launch_x, catch_y-feet, max_rise=None, max_duration=None)
                    if velocity is None:
                        launch_x = x+side*70
                        low = bounds.left() if support is None else max(bounds.left(), support.left()-self.width()/2+10)
                        high = bounds.right()+1-self.width() if support is None else min(bounds.right()+1-self.width(), support.right()-self.width()/2-10)
                        launch_x = max(low, min(high, launch_x))
                        # Walking to the jump point must stay on this support
                        # and must not pass through another solid object.
                        left = min(self.fx, launch_x)+self.width()*.25
                        right = max(self.fx, launch_x)+self.width()*.75
                        if any(r.solid and r.left < right and r.right > left
                               and r.top < feet-.5 and r.bottom > self.fy+.5
                               for r in self.nav_ledges()):
                            continue
                        velocity = jump_velocity(x-launch_x, catch_y-feet, max_rise=None, max_duration=None)
                    if velocity is None:
                        continue
                    if not clear_arc(launch_x+self.width()/2, feet, x+self.width()/2, catch_y,
                                     velocity, self.nav_ledges(), self.width()*.5, self.height(), bounds.top()):
                        continue
                    choices.append((abs(launch_x-self.fx)+abs(x-launch_x)+abs(catch_y-feet), key, rect, side, x, velocity, launch_x, catch_y))
        if not choices:
            if allow_route and self.life.config['window_perches'] and not self.floating and not self.life.config['stay']:
                self.cancel_route()
                self.follow = False
                self.route_future = self.navigator.submit(plan_climb_route,
                    self.fx+self.width()/2, feet, self.perch, self.nav_ledges(),
                    self.width()*.5, self.height(), bounds.bottom()+1,
                    bounds.left(), bounds.right()+1, bounds.top())
                self.navigation_status = 'Đang tìm đường qua các bề mặt…'
                return True
            self.say_event('notice.climb_unavailable')
            return False
        _, key, rect, side, x, velocity, launch_x, catch_y = min(choices, key=lambda item: item[0])
        self.cancel_route()
        self.follow = False
        approaching = abs(launch_x-self.fx) > 2
        self.set_state('walk' if approaching else 'jump')
        if not approaching:
            self.perch, self.support_ref = None, None
        self.vx, self.vy = velocity
        self.facing = (1 if launch_x > self.fx else -1) if approaching else -side
        self.climb_target = {'key': key, 'rect': rect, 'side': side, 'x': x, 'age': 0,
                             'launch_x': launch_x, 'velocity': velocity,
                             'jump_timeout': (-velocity[1]+math.sqrt(velocity[1]**2+2*GRAVITY*(catch_y-feet)))/GRAVITY+.5,
                             'support': (self.perch, support)}
        return True

    def advance_requested_climb(self, dt):
        target = self.climb_target
        rect = next((rect for key, rect in self.surfaces if key == target['key']), None)
        if rect is None or rect != target['rect'] or not self.life.config['window_perches']:
            self.set_state('fall')
            self.vx = self.vy = 0
            return
        target['age'] += dt
        if self.state == 'walk':
            support_key, original_support = target['support']
            current_support = next((r for key, r in self.surfaces if key == support_key), None)
            if current_support != original_support:
                self.set_state('fall')
                self.vx = self.vy = 0
                return
            delta = target['launch_x']-self.fx
            speed = self.life.config['move_speed']
            step_x = min(abs(delta), speed*dt)*(1 if delta > 0 else -1)
            margin = self.width()*.25
            resolved_x, _, _, _, _, hit = integrate(self.fx+margin, self.fy,
                step_x/max(dt, .001), 0, dt, self.width()*.5, self.height(), self.nav_ledges())
            self.fx = resolved_x-margin
            if hit:
                self.set_state('idle')
                self.say_event('notice.climb_unavailable')
            elif abs(target['launch_x']-self.fx) < 2:
                self.set_state('jump')
                self.vx, self.vy = target['velocity']
                self.perch, self.support_ref = None, None
                self.facing = -target['side']
                target['age'] = 0
        elif self.state == 'jump':
            margin = self.width()*.25
            self.fx, self.fy, self.vx, self.vy, landed, hit = integrate(
                self.fx+margin, self.fy, self.vx, self.vy, dt,
                self.width()*.5, self.height(), self.nav_ledges())
            self.fx -= margin
            if abs(self.fx-target['x']) <= 10 and rect.top() < self.fy+self.height() < rect.bottom():
                self.fx = float(target['x'])
                self.set_state('climb')
                self.vx = self.vy = 0
            elif landed is not None or hit or target['age'] > target['jump_timeout']:
                self.set_state('fall')
                self.vx = 0
        elif self.state == 'climb':
            self.fy -= 65*dt
            if self.fy+self.height() <= rect.top()+self.height()*.4:
                target['from'] = (self.fx, self.fy)
                target['mantle'] = 0
                self.set_state('hang')
        elif self.state == 'hang':
            target['mantle'] = min(1, target['mantle']+dt/.35)
            progress = target['mantle']
            progress = progress*progress*(3-2*progress)
            cx = (rect.left()+min(self.width()/2, rect.width()/2) if target['side'] < 0
                  else rect.right()+1-min(self.width()/2, rect.width()/2))
            self.fx = target['from'][0]+(cx-self.width()/2-target['from'][0])*progress
            self.fy = target['from'][1]+(rect.top()-self.height()-target['from'][1])*progress
            if target['mantle'] >= 1:
                if self.can_stand(target['key'], cx, rect.top()):
                    self.perch = target['key']
                    self.support_ref = (self.perch, rect)
                    self.set_state('idle')
                else:
                    self.set_state('fall')
        self.move(round(self.fx), round(self.fy))

    def set_paused(self, paused):
        if not self.motion_locked:
            self.floating = paused

    def sync_tray_controls(self):
        actions = self.tray_actions
        actions['visibility'].setText('Hiện nhân vật' if self.user_hidden else 'Ẩn nhân vật')
        actions['auto'].setChecked(self.life.config['auto_move'])
        actions['pause'].setChecked(self.floating)
        for key in ('auto', 'pause', 'call', 'active', 'high_five', 'meditate'):
            actions[key].setEnabled(not self.motion_locked)
        actions['stop_meditate'].setEnabled(self.life.meditation > 0)
        actions['stop_focus'].setEnabled(self.life.focus > 0 or self.life.break_left > 0)
        actions['meditate'].setText(f"Thiền {self.life.config['meditation_min']} phút")

    def toggle(self, key, value):
        self.life.config[key] = value
        if key == "stay" and value:
            self.cancel_route()
            self.follow = False
            self.set_state("idle")
        if key == "window_perches" and not value:
            self.cancel_route()
            self.perch = None
        if key == "hide_fullscreen":
            self.scan_windows()
        self.save()

    def set_reminder(self, key, checked):
        self.life.config["reminders"][key] = checked
        self.save()

    def toggle_hidden(self):
        self.user_hidden = not self.user_hidden
        self.scan_windows()

    def start_focus(self):
        self.cancel_route()
        self.life.start_focus()
        self.set_state("sleep")
        self.say_event('notice.focus_start')

    def call(self):
        if self.motion_locked:
            return
        self.cancel_route()
        self.follow = True
        self.set_state("walk")
        self.say_event('notice.call')

    def high_five(self):
        if self.motion_locked:
            return
        self.cancel_route()
        self.follow = False
        self.high_five_target = QPointF(self.mapFromGlobal(QCursor.pos()))
        self.life.affection = min(100, self.life.affection + 5)
        self.life.remember(self.signature(self.perch), 5)
        self.set_state("high_five")
        self.say_event('action.high_five')

    def advance(self):
        now = time.monotonic()
        real_dt = max(0, now-self.last_tick)
        dt = min(0.1, real_dt)
        self.last_tick = now
        for message in self.life.tick(real_dt, self.state in ("sleep", "nap")):
            self.say(message)
        bounds = self.screen().availableGeometry()
        elapsed = now - self.state_start
        if self.route and any(step.key is not None and not any(key == step.key for key, _ in self.surfaces) for step in self.route):
            self.cancel_route()
        if self.motion_locked:
            self.state = "sleep"
            self.vx = self.vy = 0
        else:
            self.advance_route()
        if self.perch is not None and now-self.last_memory > 10 and not self.motion_locked:
            self.life.remember(self.signature(self.perch))
            self.last_memory = now
        requested_climb = self.climb_target is not None
        if requested_climb and self.drag_offset is None and self.press_position is None and not self.floating and not self.motion_locked:
            self.advance_requested_climb(dt)
        if not requested_climb and self.drag_offset is None and self.press_position is None and not self.floating and not self.motion_locked:
            old_bottom = self.fy + self.height()
            support_index = next((i for i, (key, _) in enumerate(self.surfaces) if key == self.perch), None)
            surface = self.surfaces[support_index][1] if support_index is not None else None
            if surface is not None and self.support_ref is not None and self.support_ref[0] == self.perch:
                # A dragged window is not a moving platform: leave Vynn in
                # screen coordinates and let gravity find the next support.
                if surface.topLeft() != self.support_ref[1].topLeft():
                    self.cancel_route()
                    self.perch, self.support_ref = None, None
                    self.vx = self.vy = 0
                    surface = None
            supported = (self.life.config["window_perches"] and surface is not None
                         and surface.left()-10 <= self.fx + self.width()/2 <= surface.right()+10
                         and surface.top() >= bounds.top() + self.height()
                         and self.edge_visible(support_index, self.fx + self.width()/2, surface.top()))
            if supported:
                info = self.surface_metadata.get(self.perch, {})
                supported = self.can_stand(self.perch, self.fx+self.width()/2, surface.top(),
                                           inside=info.get('owner') if info.get('space') == 'inside' else None)
            if supported:
                self.fy = float(surface.top() - self.height() * (0.4 if self.state == "hang" else 1))
                self.support_ref = (self.perch, surface)
            elif self.perch is not None:
                self.perch = None
                self.vy = 0
                self.support_ref = None
            else:
                self.support_ref = None
            floor = bounds.bottom() + 1 - self.height()
            if not supported and self.fy < floor - 1 and self.state not in ("jump", "climb"):
                self.set_state("fall")
            if self.state == "walk" and not self.life.config["stay"]:
                if self.approach_target is not None:
                    target = next((r for k, r in self.surfaces if k == self.approach_target), None)
                    if target is None:
                        self.set_state("idle")
                    else:
                        delta = max(target.left()+10, min(self.fx+self.width()/2, target.right()-10)) - (self.fx+self.width()/2)
                        self.facing = 1 if delta > 0 else -1
                        if abs(delta) < 120:
                            self.approach_target = None
                            self.explore()
                if self.follow:
                    from PySide6.QtGui import QCursor
                    delta = QCursor.pos().x() - (self.fx + self.width()/2)
                    self.facing = 1 if delta > 0 else -1
                    if abs(delta) < 15:
                        self.follow = False
                        self.set_state("idle")
                nx = self.fx + self.facing * self.life.config["move_speed"] * dt
                at_edge = supported and (nx+self.width()/2 > surface.right()-8 if self.facing > 0 else nx+self.width()/2 < surface.left()+8)
                if at_edge:
                    if not self.cross_to_neighbor(surface, nx):
                        self.facing *= -1
                        self.follow = False
                        self.set_state("idle")
                elif self.state == "walk":
                    body_w = self.width()*.5
                    margin = (self.width()-body_w)/2
                    resolved_x, _, _, _, _, hit = integrate(self.fx+margin, self.fy,
                        self.facing*self.life.config["move_speed"], 0, dt, body_w, self.height(), self.nav_ledges())
                    self.fx = resolved_x-margin
                    if hit:
                        self.cancel_route()
                        self.facing *= -1
                        self.set_state("look")
                if self.fx <= bounds.left() or self.fx >= bounds.right() + 1 - self.width():
                    self.facing *= -1
                if self.state == "walk" and elapsed > self.state_duration:
                    self.follow = False
                    self.set_state("idle")
            elif self.state == "idle" and elapsed > self.state_duration and not self.life.focus and self.life.config["auto_move"] and not self.life.config["stay"]:
                self.choose_activity()
            elif self.state == "high_five" and elapsed > self.state_duration:
                self.set_state("idle")
            elif self.state in ("sleep", "nap", "dance", "sad", "sit", "look", "groom", "stretch") and elapsed > self.state_duration and not self.motion_locked:
                if self.life.config["auto_move"] and not self.life.config["stay"]:
                    self.choose_activity()
                else:
                    self.set_state("idle")
            elif self.state == "hang" and elapsed > 1.0:
                self.set_state("idle")
            elif self.state == "climb":
                candidates = [r for key, r in self.surfaces if r.bottom() > old_bottom > r.top()
                              and (not self.route_step or self.route_step.kind != "climb" or key == self.route_step.key)
                              and min(abs(self.fx + self.width() - r.left()), abs(self.fx - r.right())) < 100]
                if candidates and self.life.config["window_perches"]:
                    wall = candidates[0]
                    self.fy -= 28 * dt
                    if self.fy + self.height() <= wall.top() + 2:
                        self.fx = float(wall.left())
                        self.fy = float(wall.top() - self.height())
                        self.perch = next(k for k, r in self.surfaces if r == wall)
                        self.set_state("hang")
                else:
                    self.set_state("idle")
                    self.say_event('notice.climb_unavailable')
            if self.state in ("jump", "fall"):
                if self.jump_target is not None and not any(key == self.jump_target for key, _ in self.surfaces):
                    self.jump_target = None
                    self.vx = 0
                body_w = self.width()*.5
                margin = (self.width()-body_w)/2
                self.fx, self.fy, self.vx, self.vy, collision_landing, hit = integrate(
                    self.fx+margin, self.fy, self.vx, self.vy, dt, body_w, self.height(), self.nav_ledges())
                self.fx -= margin
                if hit:
                    self.cancel_route()
                    self.navigation_status = "Va chạm; dừng tuyến để chọn đường khác."
                landing = []
                if collision_landing is not None:
                    landing.append((self.fy, collision_landing))
                if self.vy >= 0 and self.life.config["window_perches"]:
                    cx = self.fx + self.width()/2
                    inside = self.scene.inside_owner(cx, old_bottom-1, self.perch) if self.scene and self.scene.surfaces is self.surfaces else None
                    entering = self.surface_owners.get(self.jump_target)
                    for key, rect in self.surfaces:
                        if rect.left() <= cx <= rect.right() and old_bottom <= rect.top() <= self.fy + self.height():
                            # A foreground window that covers this edge blocks landing.
                            if (rect.top() >= bounds.top() + self.height()
                                    and self.edge_visible(self.surfaces.index((key, rect)), cx, rect.top())
                                    and self.can_stand(key, cx, rect.top(), inside, entering)):
                                landing.append((rect.top() - self.height(), key))
                if landing:
                    self.fy, self.perch = min(landing, key=lambda candidate: candidate[0])
                    self.support_ref = next(((key, rect) for key, rect in self.surfaces
                                             if key == self.perch), None)
                    self.vy = 0
                    self.set_state("idle")
                elif self.fy >= floor:
                    self.fy, self.vy, self.perch = float(floor), 0, None
                    self.set_state("idle")
            if self.fy < bounds.top() and self.vy < 0:
                self.vy = -self.vy*.15
                self.cancel_route()
            if (self.fx < bounds.left() and self.vx < 0) or (self.fx > bounds.right()+1-self.width() and self.vx > 0):
                self.vx *= -.2
                self.facing *= -1
                self.cancel_route()
            self.fx = max(bounds.left(), min(bounds.right() + 1 - self.width(), self.fx))
            self.fy = max(bounds.top(), min(floor, self.fy))
            self.move(round(self.fx), round(self.fy))
        if self.isVisible() and self.life.config['messages_enabled']:
            if now >= self.message_until and self.messages:
                self.bubble.setText(self.messages.popleft())
                self.bubble.adjustSize()
                self.message_until = now + self.life.config['message_seconds']
            if now < self.message_until:
                x = max(bounds.left(), min(bounds.right()+1-self.bubble.width(), self.x()+self.width()/2-self.bubble.width()/2))
                y = self.y()-self.bubble.height()-8
                below = y < bounds.top()
                if below:
                    y = self.y()+self.height()+8
                self.bubble.move(round(x), max(bounds.top(), min(bounds.bottom()+1-self.bubble.height(), y)))
                self.bubble.point_to(self.x()+self.width()/2, upward=below)
                self.bubble.show()
            else:
                self.bubble.hide()
        self.setToolTip(self.life.summary() + (f" | Focus {math.ceil(self.life.focus/60)} min" if self.life.focus else ""))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.save()
        bottom_aligned = getattr(self.renderer, "grounded", False)
        painter.translate(5, self.height() - self.base_h if bottom_aligned else 5)
        painter.scale(self.base_w / 120, self.base_h / 140)
        if self.state == "dance":
            painter.translate(3 * math.sin((time.monotonic()-self.t0)*12), 0)
        render_state = "grabbed" if self.drag_offset is not None else (
            "high_five_cursor" if self.state == "high_five" else self.state)
        self.renderer.paint(painter, render_state,
                            time.monotonic() - self.t0, self.facing)
        if self.state == "sleep":
            painter.drawText(90, 20, "…")
        elif self.state in ("sit", "look", "groom", "stretch"):
            painter.drawText(5, 14, {"sit": "…", "look": "?", "groom": "♡", "stretch": "↟"}[self.state])
        painter.restore()
        if self.drag_offset is not None:
            self.paint_gripping_hands(painter, bottom_aligned)
        elif self.state == 'high_five':
            self.paint_high_five(painter, bottom_aligned)

    def paint_high_five(self, painter, bottom_aligned):
        """Draw the reaching arm last so the palm always covers the hair."""
        unit = self.base_w / 120
        top = self.height() - self.base_h if bottom_aligned else 5
        shoulder = QPointF(5 + 75 * unit, top + self.base_h * .60)
        cursor = self.high_five_target if self.high_five_target is not None else shoulder
        target = QPointF(max(12*unit, min(self.width()-12*unit, cursor.x())),
                         max(16*unit, min(self.height()-10*unit, cursor.y())))
        elapsed = max(0, time.monotonic() - self.state_start)
        reach = min(1, elapsed / .22)
        reach = 1 - (1-reach)**3
        if elapsed > .35:
            reach *= max(0, 1 - (elapsed-.35)/.30)
        palm = shoulder + (target-shoulder)*reach
        wrist = palm + QPointF(0, 6*unit)
        elbow = (shoulder+wrist)*.5 + QPointF(10*unit, 7*unit)
        arm = QPainterPath(shoulder)
        arm.lineTo(elbow)
        arm.lineTo(wrist)
        painter.setBrush(Qt.NoBrush)
        for color, width in (('#30252a', 7), ('#efac7e', 5)):
            painter.setPen(QPen(QColor(color), width*unit, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(arm)
        sleeve = shoulder + (elbow-shoulder)*.35
        painter.setPen(QPen(QColor('#30252a'), 9*unit, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(shoulder, sleeve)
        painter.setPen(QPen(QColor('#39343c'), 6.5*unit, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(shoulder, sleeve)
        # Open fingers and thumb form a high-five palm instead of a fist.
        for x, length in ((-4.5, 7), (-1.5, 10), (1.5, 11), (4.5, 8)):
            start = palm + QPointF(x*unit, -unit)
            end = start + QPointF(0, -length*unit)
            for color, width in (('#bc7956', 3.6), ('#ffc18f', 2.2)):
                painter.setPen(QPen(QColor(color), width*unit, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(start, end)
        painter.setPen(QPen(QColor('#bc7956'), .8*unit))
        painter.setBrush(QColor('#ffc18f'))
        painter.drawRoundedRect(QRectF(palm.x()-6*unit, palm.y()-3*unit,
                                      12*unit, 11*unit), 3*unit, 3*unit)
        painter.drawEllipse(QRectF(palm.x()-9*unit, palm.y(), 5*unit, 4*unit))

    def paint_gripping_hands(self, painter, bottom_aligned):
        """Articulated arms with sleeves, bent elbows and curled fingers."""
        unit = self.base_w / 120
        top = self.height() - self.base_h if bottom_aligned else 5
        grip = QPointF(self.drag_offset)
        for side in (-1, 1):
            shoulder = QPointF(5 + (60 + side * 15) * unit,
                               top + self.base_h * .60)
            wrist = grip + QPointF(side * 5 * unit, 7 * unit)
            elbow = (shoulder + wrist) * .5 + QPointF(side * 10 * unit, 8 * unit)
            arm = QPainterPath(shoulder)
            arm.lineTo(elbow)
            arm.lineTo(wrist)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor('#30252a'), 7 * unit, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(arm)
            painter.setPen(QPen(QColor('#efac7e'), 5 * unit, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(arm)
            # A short sleeve covers the shoulder seam instead of a bare tube.
            sleeve_end = shoulder + (elbow - shoulder) * .36
            painter.setPen(QPen(QColor('#252127'), 9 * unit, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(shoulder, sleeve_end)
            painter.setPen(QPen(QColor('#39343c'), 6.5 * unit, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(shoulder, sleeve_end)
            painter.setPen(QPen(QColor('#bc7956'), .8 * unit, Qt.SolidLine, Qt.RoundCap))
            painter.setBrush(QColor('#ffc18f'))
            painter.drawRoundedRect(QRectF(wrist.x()-3.5*unit, wrist.y()-5*unit,
                                          7*unit, 8*unit), 2.5*unit, 2.5*unit)
            # Three curled fingers face inward, leaving space for the cursor.
            for row in range(3):
                finger = wrist + QPointF(-side*2*unit, (row*2-4)*unit)
                painter.drawRoundedRect(QRectF(finger.x()-2*unit, finger.y(),
                                              4*unit, 2.4*unit), unit, unit)
            thumb = wrist + QPointF(side*2*unit, 0)
            painter.drawEllipse(QRectF(thumb.x()-1.5*unit, thumb.y()-2*unit,
                                      3*unit, 4*unit))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.motion_locked:
                return
            self.cancel_route()
            self.press_position = event.globalPosition().toPoint()
            self.dragged = False
            self.follow = False
            if self.state == 'high_five':
                self.high_five_target = None
                self.set_state('idle')
                self.update()
            self.hold_timer.start()
        elif event.button() == Qt.RightButton:
            self.show_action_menu(event.globalPosition().toPoint())

    def begin_drag(self):
        if self.press_position is None or self.motion_locked:
            return
        self.cancel_route()
        # Keep the original grab point even if the cursor moved while waiting.
        self.drag_offset = self.press_position - self.pos()
        self.press_position = None
        self.vx = self.vy = 0
        self.set_state('idle')
        self.setCursor(Qt.ClosedHandCursor)
        target = QCursor.pos() - self.drag_offset
        if (target - self.pos()).manhattanLength() > 3:
            self.dragged = True
        self.move(target)
        self.fx, self.fy = float(self.x()), float(self.y())
        self.perch, self.support_ref = None, None
        self.update()

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and not self.motion_locked:
            target = event.globalPosition().toPoint() - self.drag_offset
            if (target - self.pos()).manhattanLength() > 3:
                self.dragged = True
            self.move(target)
            self.fx, self.fy = float(self.x()), float(self.y())
            self.perch, self.vy = None, 0

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.hold_timer.stop()
            was_pressed = self.press_position is not None
            was_grabbing = self.drag_offset is not None
            self.press_position = None
            self.drag_offset = None
            self.setCursor(Qt.ArrowCursor)
            if self.motion_locked:
                return
            if not was_pressed and not was_grabbing:
                return
            if was_grabbing:
                self.scan_windows()
                self.snap_to_edge()
            if self.state != "jump":
                self.set_state("idle")
            if was_pressed:
                self.high_five()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Qt delivers the second press here; use the same hold-to-drag
            # transition as a normal press, including after a quick high-five.
            self.mousePressEvent(event)
