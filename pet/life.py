"""Persistent settings, mood, and monotonic focus/reminder timers."""
import json
import os
from pathlib import Path
from pet.dialogue import CATALOG, DEFAULT_ENABLED, LEGACY_TEXT, render

DEFAULTS = {"size": "Small", "character": "chibi_boy", "auto_move": True, "stay": False, "hide_fullscreen": True,
            "window_perches": True, "reminders": {"eyes": True, "stretch": True, "water": True},
            "eyes_min": 20, "stretch_min": 45, "water_min": 60, "move_speed": 28, "action_pause": 3,
            "follow_active": True, "meditation_min": 5, "collapsed_sections": {},
            "messages_enabled": True, "message_seconds": 5, "message_font": 14,
            "message_width": 280, "message_theme": "light", "message_preview": "Chào bạn! Chúc bạn một ngày vui vẻ.",
            "dialogue": {}, "dialogue_enabled": DEFAULT_ENABLED, "dialogue_defaults_version": 1}


class Life:
    def __init__(self, directory=None):
        base = Path(os.getenv("APPDATA", str(Path.home())))
        self.directory = Path(directory) if directory else base / "Vynn Notify"
        self.config = dict(DEFAULTS, reminders=dict(DEFAULTS["reminders"]))
        saved = self.read("config.json")
        for key, default in DEFAULTS.items():
            value = saved.get(key)
            if type(value) is type(default):
                self.config[key] = value
        for key in ("eyes_min", "stretch_min", "water_min"):
            self.config[key] = max(1, min(1440, self.config[key]))
        self.config["move_speed"] = max(10, min(300, self.config["move_speed"]))
        self.config["action_pause"] = max(1, min(15, self.config["action_pause"]))
        self.config["meditation_min"] = max(1, min(180, self.config["meditation_min"]))
        for key, low, high in (("message_seconds", 1, 30), ("message_font", 10, 24), ("message_width", 180, 420)):
            self.config[key] = max(low, min(high, self.config[key]))
        if self.config['message_theme'] not in ('light', 'dark'):
            self.config['message_theme'] = 'light'
        self.config['collapsed_sections'] = {k: v for k, v in self.config['collapsed_sections'].items() if isinstance(k, str) and type(v) is bool}
        self.config['dialogue'] = {k: v[:1200] for k, v in self.config['dialogue'].items() if k in CATALOG and isinstance(v, str)}
        self.config['dialogue_enabled'] = {k: v for k, v in self.config['dialogue_enabled'].items() if k in CATALOG and type(v) is bool}
        if saved.get('dialogue_defaults_version') != 1:
            self.config['dialogue_enabled'] = dict(DEFAULT_ENABLED)
            self.config['messages_enabled'] = True
            for key, old in LEGACY_TEXT.items():
                if self.config['dialogue'].get(key) == old:
                    self.config['dialogue'].pop(key)
            self.config['dialogue_defaults_version'] = 1
        self.config["reminders"] = {k: self.config["reminders"].get(k, True) is True for k in DEFAULTS["reminders"]}
        saved = self.read("state.json")
        self.energy = self.number(saved.get("energy"), 80)
        self.fullness = self.number(saved.get("fullness"), 80)
        self.affection = self.number(saved.get("affection"), 50)
        self.focus = self.number(saved.get("focus"), 0, 1500)
        self.break_left = self.number(saved.get("break_left"), 0, 300)
        self.meditation = self.number(saved.get("meditation"), 0, 10800)
        favourites = saved.get("favourites", {})
        self.favourites = {k: self.number(v, 0, 1000) for k, v in favourites.items() if isinstance(k, str)} if isinstance(favourites, dict) else {}
        self.elapsed = {key: self.number(saved.get("elapsed", {}).get(key), 0, 86400)
                        for key in DEFAULTS["reminders"]} if isinstance(saved.get("elapsed", {}), dict) else dict.fromkeys(DEFAULTS["reminders"], 0)

    @staticmethod
    def number(value, default, upper=100):
        return max(0, min(upper, float(value))) if type(value) in (int, float) else default

    def read(self, name):
        try:
            value = json.loads((self.directory / name).read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        state = dict(energy=self.energy, fullness=self.fullness, affection=self.affection,
                     focus=self.focus, break_left=self.break_left, elapsed=self.elapsed,
                     meditation=self.meditation, favourites=self.favourites)
        for name, value in (("config.json", self.config), ("state.json", state)):
            target = self.directory / name
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
            temporary.replace(target)

    def start_focus(self):
        self.focus, self.break_left = 25 * 60, 0

    def stop_focus(self):
        self.focus = self.break_left = 0

    def tick(self, dt, sleeping=False):
        self.energy = max(0, min(100, self.energy + dt * (0.1 if sleeping else -0.008)))
        self.fullness = max(0, self.fullness - dt * 0.006)
        events = []
        if self.meditation > 0:
            self.meditation = max(0, self.meditation-dt)
            if self.meditation == 0:
                events.append(self.dialogue('notice.meditation_done'))
        if self.focus > 0:
            self.focus = max(0, self.focus - dt)
            if self.focus == 0:
                self.break_left = 300
                events.append(self.dialogue('notice.focus_done'))
        elif self.break_left > 0:
            self.break_left = max(0, self.break_left - dt)
            if self.break_left == 0:
                events.append(self.dialogue('notice.break_done'))
        for key in ("eyes", "stretch", "water"):
            if self.config["reminders"][key]:
                self.elapsed[key] += dt
                interval = self.config[key + "_min"] * 60
                if self.elapsed[key] >= interval:
                    self.elapsed[key] %= interval
                    events.append(self.dialogue('notice.'+key))
        return [text for text in events if text]

    def dialogue(self, key, **values):
        context = dict(summary=self.summary(), energy=round(self.energy),
                       affection=round(self.affection), minutes=self.config['meditation_min'])
        context.update(values)
        return render(self.config, key, **context)

    def remember(self, signature, reward=1):
        self.favourites[signature] = min(1000, self.favourites.get(signature, 0)+reward)
        if len(self.favourites) > 200:
            self.favourites = dict(sorted(self.favourites.items(), key=lambda pair: pair[1], reverse=True)[:200])

    def summary(self):
        return f"Năng lượng {self.energy:.0f}% | Tình cảm {self.affection:.0f}%"
