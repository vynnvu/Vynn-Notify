"""Editable dialogue catalog; placeholders are replaced without executing code."""
CATALOG = {
    'action.walk': ('Hành động · Đi bộ', 'Mình đi dạo một chút nhé!'),
    'action.sleep': ('Hành động · Ngồi thiền', 'Hít thở nhẹ nhàng, thư giãn một chút.'),
    'action.nap': ('Hành động · Ngủ', 'Ngủ một giấc nào… z Z'),
    'action.jump': ('Hành động · Nhảy', 'Nhảy nào!'),
    'action.climb': ('Hành động · Leo', 'Mình leo lên chỗ này nhé.'),
    'action.hang': ('Hành động · Treo', 'Bám chắc rồi, lên thôi!'),
    'action.sit': ('Hành động · Ngồi nghỉ', 'Cho mình ngồi nghỉ một chút.'),
    'action.look': ('Hành động · Quan sát', 'Có gì thú vị quanh đây nhỉ?'),
    'action.groom': ('Hành động · Chải tóc', 'Chải tóc gọn gàng nào!'),
    'action.stretch': ('Hành động · Vươn vai', 'Vươn vai cho thoải mái!'),
    'action.dance': ('Hành động · Vui / nhảy múa', 'Hôm nay thật vui!'),
    'action.sad': ('Hành động · Buồn', 'Ở bên mình một chút nhé.'),
    'action.high_five': ('Hành động · Đập tay', 'Đập tay nào!'),
    'notice.startup': ('Thông báo · Khởi động', 'Kéo để di chuyển, bấm đúp để nhảy, chuột phải để mở bảng điều chỉnh.'),
    'notice.call': ('Thông báo · Gọi lại', 'Mình tới đây!'),
    'notice.meditation_start': ('Thông báo · Bắt đầu chế độ thiền', 'Bắt đầu thiền {minutes} phút. Mình sẽ ở yên tại đây.'),
    'notice.meditation_stop': ('Thông báo · Dừng chế độ thiền', 'Đã dừng chế độ thiền.'),
    'notice.meditation_done': ('Thông báo · Hết giờ thiền', 'Đã hoàn thành thời gian thiền.'),
    'notice.focus_start': ('Thông báo · Bắt đầu tập trung', 'Tập trung 25 phút nhé, mình sẽ ở bên bạn.'),
    'notice.focus_done': ('Thông báo · Hết giờ tập trung', 'Đã hoàn thành phiên tập trung! Nghỉ ngơi 5 phút nhé.'),
    'notice.break_done': ('Thông báo · Hết giờ nghỉ', 'Hết giờ nghỉ rồi. Bạn sẵn sàng tập trung tiếp chưa?'),
    'notice.eyes': ('Thông báo · Nhắc nghỉ mắt', 'Cho mắt nghỉ một chút: nhìn ra xa trong 20 giây nhé.'),
    'notice.stretch': ('Thông báo · Nhắc giãn cơ', 'Đến lúc giãn cơ rồi! Đứng dậy và vận động một chút nhé.'),
    'notice.water': ('Thông báo · Nhắc uống nước', 'Đến giờ uống nước rồi, uống một ly nhé!'),
    'notice.climb_unavailable': ('Thông báo · Chưa có chỗ leo', 'Đưa mình tới sát cạnh cửa sổ để leo nhé.'),
}

DEFAULT_ENABLED = {key: key.startswith('notice.') for key in CATALOG}

LEGACY_TEXT = {
    'notice.focus_done': 'Focus done! Take a 5 minute break.',
    'notice.break_done': 'Break finished. Ready for another focus session?',
    'notice.eyes': 'Rest your eyes: look far away for 20 seconds.',
    'notice.stretch': 'Stretch break! Stand up and move a little.',
    'notice.water': 'Time for a glass of water!',
}


def render(config, key, **values):
    if key not in CATALOG or not config.get('dialogue_enabled', {}).get(key, DEFAULT_ENABLED.get(key, False)):
        return ''
    text = config.get('dialogue', {}).get(key, CATALOG[key][1])
    for name in ('minutes', 'summary', 'energy', 'affection'):
        if name in values:
            text = text.replace('{'+name+'}', str(values[name]))
    return text.strip()[:1200]
