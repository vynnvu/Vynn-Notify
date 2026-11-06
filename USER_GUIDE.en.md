# Vynn Notify — English user guide

The application currently has a **Vietnamese interface**. This guide explains its controls in English; installing the app does not switch its interface language.

[Download Windows Lite](https://github.com/vynnvu/VynnNotifyQPainter/raw/refs/heads/main/dist/Vynn_Notify_Lite.exe) · [Vietnamese guide](USER_GUIDE.md) · [Back to README](README.md)

## Download and start

Save `Vynn_Notify_Lite.exe` in a folder of your choice and open it on Windows 64-bit. No Python installation is required. Startup may take a few seconds while the standalone package extracts its resources.

If Windows shows a publisher warning, verify the download source and run it only if you trust that source. You do not need to turn off your security software.

## Mouse controls

| Gesture | Action |
| --- | --- |
| Quick left click on Vynn | One high-five toward the click-time cursor position |
| Hold the left button for about 0.2 seconds | Pick Vynn up |
| Hold, drag, then release | Move Vynn; he lands on a suitable surface or falls |
| Right-click Vynn | Open the action menu |
| Click the tray icon next to the Windows clock | Open settings |
| Right-click the tray icon | Quick controls and quit |

If the tray icon is missing, check the hidden-icons area next to the clock. Double-clicking Vynn is not a jump shortcut.

## Action menu translations

| Vietnamese label | English meaning |
| --- | --- |
| Đập tay | High-five |
| Nhảy | Jump |
| Tìm chỗ leo | Find somewhere to climb |
| Ngủ / Đánh thức | Sleep / Wake up |
| Hoạt động | Activities submenu |
| Đi bộ / Ngồi nghỉ | Walk / Sit |
| Quan sát | Look around |
| Vuốt tóc / Chải tóc | Groom hair |
| Vươn vai / Nhảy múa | Stretch / Dance |
| Buồn | Sad |
| Ngồi thiền | Meditation pose |
| Gọi lại | Walk toward the cursor’s horizontal position |
| Dừng leo / Dừng tìm đường | Stop climbing / Stop route |
| Dừng thiền / Dừng tập trung | Stop meditation / Stop focus timer |
| Thoát Vynn Notify | Quit Vynn Notify |

Climbing depends on detected, reachable surfaces and available paths. Vynn may walk to a takeoff point or use intermediate surfaces. Some applications do not expose usable surfaces. Moving a supporting window can make Vynn lose his footing and fall.

## Settings tabs

### Vynn

- **Ngoại hình / Kích thước:** appearance and size. Choose Rất nhỏ (Tiny), Nhỏ (Small), Vừa (Medium) or Lớn (Large).
- **Hoạt động / Thực hiện:** select an activity and run it.
- **Tự đi lại:** automatically move when idle.
- **Đứng yên:** stay in place.
- **Tạm dừng:** pause movement and gravity.
- **Bám bề mặt:** enable detected surfaces for standing and climbing.
- **Theo cửa sổ đang dùng:** follow the active window when possible.
- **Tốc độ đi lại / Nghỉ giữa động tác:** walking speed and pauses between actions.

### Nhắc nhở — Reminders

Toggle **Nghỉ mắt** (eye rest), **Giãn cơ** (stretching) or **Uống nước** (water) and set the interval in minutes.

**Tập trung 25 phút** starts a 25-minute focus session followed by a 5-minute break. **Bắt đầu thiền** starts a meditation timer using the selected duration. These modes lock movement; use their stop buttons to end early.

The **Ngồi thiền** activity is only a pose, not the timed meditation mode. Reminders follow your configured timers; the app does not check whether you drank water or assess your health.

### Cài đặt — Settings

- **Mở cùng Windows:** start with Windows.
- **Ẩn khi toàn màn hình:** hide during detected fullscreen applications.
- **Hiện lời thoại:** show speech bubbles.
- Adjust bubble duration, font size, width and light/dark theme.
- Edit dialogue by event. You can replace Vietnamese messages with your own English text and preview them.

Changes apply immediately and save automatically. Closing settings keeps Vynn running. Use **Thoát Vynn Notify** to quit.

## Preferences and updates

Preferences and character state are stored in `%APPDATA%\Vynn Notify`. Back up this folder if needed. Quit the existing instance before replacing the EXE with a new version, then open the new file. Do not run two versions simultaneously.

## Troubleshooting

| Problem | Check |
| --- | --- |
| Vynn is missing | Tray icon, hidden-icons area, visibility and fullscreen settings |
| Dragging does not work | Hold for 0.2 seconds; stop meditation/focus if active |
| Vynn does not move | Automatic movement, stay-in-place and pause settings |
| Climbing does not work | Enable surfaces; try a different window or location |
| Reminders are missing | Enable speech bubbles and the reminder; check its interval |
| Slow first launch | Allow time for bundled resource extraction |

Report issues at [GitHub Issues](https://github.com/vynnvu/VynnNotifyQPainter/issues). Include Windows version, EXE filename, reproduction steps and screenshots if useful. Avoid sharing personal information or sensitive window content.
