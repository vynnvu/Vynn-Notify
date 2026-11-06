import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import tempfile
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect
from pet.app import DesktopPet
from pet.life import Life
from pet.windows import scan
from pet.surfaces import merge_surfaces
from pet.behavior import jump_velocity
from PySide6.QtGui import QImage, QPainter, QCursor
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QSystemTrayIcon
from unittest.mock import patch

app = QApplication([])
with tempfile.TemporaryDirectory() as directory:
    pet = DesktopPet(data_dir=directory)
    pet.show()
    assert not hasattr(pet.renderer, 'frames')
    assert pet.spec['id'] == 'chibi_boy'
    assert pet.spec['name'] == 'Vynn'
    assert not pet.windowIcon().isNull()
    assert not pet.character_icon.pixmap(32, 32).isNull()
    def render_pose(state, facing=1):
        image = QImage(240, 280, QImage.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter = QPainter(image)
        painter.scale(2, 2)
        pet.renderer.paint(painter, state, 1.2, facing)
        painter.end()
        return bytes(image.constBits())
    assert render_pose('idle', -1) == render_pose('idle', 1), 'Hair and C must never mirror'
    assert len({render_pose(state) for state in ('idle', 'walk', 'jump', 'sleep', 'climb', 'sit', 'groom', 'stretch', 'dance')}) == 9
    assert render_pose('nap') != render_pose('sleep')
    # Regression: actual opaque feet must touch the widget's physical surface,
    # for different procedural animation phases and sizes.
    pet.timer.stop()
    pet.scanner.stop()
    pet.set_state('idle')
    for size in ('Tiny', 'Small', 'Medium', 'Large'):
        pet.set_size(size)
        for phase in (0.3, 1.2, 2.7, 4.3):
            pet.t0 = time.monotonic() - phase
            for facing in (-1, 1):
                pet.facing = facing
                image = pet.grab().toImage()
                ratio = image.devicePixelRatio()
                last_opaque = max(y for y in range(image.height())
                                  if any(image.pixelColor(x, y).alpha() > 32 for x in range(image.width())))
                assert image.height() - 1 - last_opaque <= max(1, round(ratio)), (size, phase, last_opaque, image.height())
    pet.t0 = time.monotonic()
    for state in ('idle', 'walk', 'sleep', 'dance', 'sad', 'climb', 'sit', 'look', 'groom', 'stretch', 'jump', 'fall'):
        pet.set_state(state, force=True)
        pet.last_tick -= .033
        pet.advance()
        assert not pet.grab().isNull()
    pet.set_state('idle')
    pet.jump()
    start_y = pet.y()
    for _ in range(60):
        pet.last_tick -= .033
        pet.advance()
    assert pet.state != 'jump'
    # Land on a window, then fall in screen coordinates when it moves away.
    bounds = pet.screen().availableGeometry()
    edge = bounds.top() + 300
    pet.fx = float(bounds.left() + 100)
    pet.fy = float(edge - pet.height() - 1)
    pet.perch = None
    pet.surfaces = [(123, QRect(bounds.left(), edge, 600, 300))]
    pet.vy = 200
    pet.set_state('fall')
    pet.last_tick -= .033
    pet.advance()
    assert pet.perch == 123 and pet.y() + pet.height() == edge
    landing_x, landing_y = pet.fx, pet.fy
    pet.surfaces = [(123, QRect(bounds.left(), edge - 10, 600, 300))]
    pet.last_tick -= .033
    pet.advance()
    assert pet.perch is None and pet.state == 'fall'
    assert pet.fx == landing_x and 0 < pet.fy - landing_y < 3
    pet.surfaces = []
    pet.last_tick -= .033
    pet.advance()
    assert pet.perch is None and pet.state == 'fall'
    # A manual drop slightly BELOW the ledge must snap back onto it.
    # Explicit climbing jumps to either side, grabs, and mantles onto the top.
    for side in (-1, 1):
        wall = QRect(bounds.left()+400, bounds.bottom()+1-180, 220, 300)
        pet.surfaces = [('climb_wall', wall)]
        pet.fx = float(wall.left()-pet.width()-60 if side < 0 else wall.right()+61)
        pet.fy = float(bounds.bottom()+1-pet.height())
        pet.perch, pet.support_ref = None, None
        pet.set_state('idle')
        with patch.object(pet, 'edge_visible', return_value=True), patch.object(pet, 'can_stand', return_value=True):
            assert pet.start_climb(), side
            assert pet.state == 'jump'
            stages = set()
            for _ in range(600):
                stages.add(pet.state)
                pet.advance_requested_climb(.016)
                if pet.climb_target is None:
                    break
            assert {'jump', 'climb', 'hang'} <= stages, (side, stages)
            assert pet.perch == 'climb_wall' and pet.state == 'idle'
            assert abs(pet.fy+pet.height()-wall.top()) < 1
            pet.fx = float(wall.left()-pet.width()-60)
            pet.fy = float(bounds.bottom()+1-pet.height())
            pet.perch, pet.support_ref = None, None
            assert pet.start_climb()
            previous_x, previous_y = pet.fx, pet.fy
            pet.surfaces = [('climb_wall', wall.translated(50, 20))]
            pet.advance_requested_climb(.016)
            assert pet.climb_target is None and pet.state == 'fall'
            assert (pet.fx, pet.fy) == (previous_x, previous_y)
    # Search also works beyond jump range by walking to a launch point first.
    pet.surfaces = [('distant_wall', wall)]
    pet.fx = float(bounds.left()+15)
    pet.fy = float(bounds.bottom()+1-pet.height())
    pet.perch, pet.support_ref = None, None
    pet.set_state('idle')
    with patch.object(pet, 'edge_visible', return_value=True), patch.object(pet, 'can_stand', return_value=True):
        assert pet.start_climb() and pet.state == 'walk'
        stages = set()
        for _ in range(2000):
            stages.add(pet.state)
            old_x = pet.fx
            walking = pet.state == 'walk'
            pet.advance_requested_climb(.016)
            if walking:
                assert abs(pet.fx-old_x) <= pet.life.config['move_speed']*.016+.01
            if pet.climb_target is None:
                break
        assert {'walk', 'jump', 'climb', 'hang'} <= stages, stages
        assert pet.perch == 'distant_wall' and pet.state == 'idle'
    pet.surfaces = [(123, QRect(bounds.left(), edge, 600, 300))]
    pet.fx = float(bounds.left() + 100)
    pet.fy = float(edge - pet.height() + 8)
    assert pet.snap_to_edge()
    assert pet.perch == 123 and pet.y() + pet.height() == edge
    for _ in range(20):
        pet.last_tick -= .033
        pet.advance()
        assert pet.perch == 123 and pet.y() + pet.height() == edge
    # Don't catch a hidden ledge or one beyond the drop tolerance.
    pet.surfaces.insert(0, (456, QRect(bounds.left(), edge - 50, 600, 400)))
    assert not pet.snap_to_edge()
    pet.last_tick -= .033
    pet.advance()
    assert pet.perch is None and pet.state == 'fall'
    pet.surfaces = [(123, QRect(bounds.left(), edge, 600, 300))]
    pet.fy = float(edge - pet.height() + 30)
    assert not pet.snap_to_edge()
    pet.fy = float(edge - pet.height() + 8)
    pet.life.config['window_perches'] = False
    assert not pet.snap_to_edge()
    pet.life.config['window_perches'] = True
    pet.surfaces = []
    # Internal controls must not be occluded by their OWN containing window.
    owner = QRect(bounds.left(), edge - 100, 600, 400)
    rows = [{'hwnd': 777, 'x': owner.left(), 'y': owner.top(), 'w': 600, 'h': 400,
             'items': [{'id': 'edit1', 'x': owner.left() + 50, 'y': edge,
                        'w': 300, 'h': 40}]}]
    pet.surfaces, pet.surface_owners = merge_surfaces([(777, owner)], rows)
    pet.fx = float(owner.left() + 100)
    pet.fy = float(edge - pet.height() + 5)
    assert pet.snap_to_edge() and pet.perch == (777, 'edit1')
    pet.last_tick -= .033
    pet.advance()
    assert pet.perch == (777, 'edit1')
    previous_x = pet.fx
    moved = owner.translated(20, 10)
    pet.surfaces, pet.surface_owners = merge_surfaces([(777, moved)], rows)
    pet.last_tick -= .033
    pet.advance()
    assert pet.perch is None and pet.state == 'fall'
    assert pet.fx == previous_x and edge < pet.fy + pet.height() < edge + 10
    pet.surfaces, pet.surface_owners = [], {}
    pet.perch = None
    prior_affection = pet.life.affection
    pet.high_five()
    assert pet.life.affection > prior_affection and pet.state == 'high_five'
    pet.start_focus()
    assert pet.life.focus == 1500
    assert 'phiên tập trung' in pet.life.tick(1500)[0]
    assert pet.life.break_left == 300
    pet.life.tick(300)
    assert pet.life.break_left == 0
    pet.life.elapsed['eyes'] = pet.life.config['eyes_min'] * 60 - 1
    assert any('mắt' in message for message in pet.life.tick(2))
    pet.set_size('Large')
    pet.save()
    restored = Life(directory)
    assert restored.config['size'] == 'Large'
    assert restored.fullness == pet.life.fullness
    pet.show_settings()
    panel = pet.settings
    assert panel.models.findData('shin') == -1
    assert panel.models.count() == 1
    assert not pet.windowIcon().isNull()
    panel.models.setCurrentIndex(panel.models.findData('chibi_boy'))
    assert pet.spec['id'] == 'chibi_boy'
    panel.sizes.setCurrentIndex(panel.sizes.findData('Tiny'))
    assert pet.base_w == 56 and pet.base_h == 63
    panel.auto.setChecked(False)
    assert not pet.life.config['auto_move'] and pet.life.config['stay']
    panel.auto.setChecked(True)
    assert pet.life.config['auto_move'] and not pet.life.config['stay']
    assert pet.state == 'walk'
    before_x = pet.fx
    pet.last_tick -= .033
    pet.advance()
    # Surface/fall tests above left the pet in the air; land before walking.
    pet.perch = None
    pet.fy = float(pet.screen().availableGeometry().bottom() + 1 - pet.height())
    pet.fx = float(pet.screen().availableGeometry().left() + 100)
    pet.set_auto_move(True)
    before_x = pet.fx
    pet.last_tick -= .033
    pet.advance()
    assert pet.fx != before_x
    panel.reminders['water'][1].setValue(30)
    assert pet.life.config['water_min'] == 30
    panel.close()
    assert pet.isVisible()
    QTest.mouseClick(pet, Qt.RightButton)
    assert not panel.isVisible() and pet.action_menu.isVisible()
    actions = {action.text(): action for action in pet.action_menu.actions()}
    assert 'Nhảy' in actions and 'Đập tay' in actions and 'Mở bảng điều chỉnh' not in actions
    activities = {action.text(): action for action in actions['Hoạt động'].menu().actions()}
    activities['Ngồi nghỉ'].trigger()
    assert pet.state == 'sit'
    pet.action_menu.close()
    pet.set_state('nap')
    pet.show_action_menu(pet.pos())
    wake = next(action for action in pet.action_menu.actions() if action.text() == 'Đánh thức')
    wake.trigger()
    assert pet.state == 'idle'
    pet.action_menu.close()
    pet.set_state('climb')
    pet.show_action_menu(pet.pos())
    stop_climb = next(action for action in pet.action_menu.actions() if action.text() == 'Dừng leo')
    stop_climb.trigger()
    assert pet.state == 'fall' and pet.climb_target is None
    pet.action_menu.close()
    pet.tray_activated(QSystemTrayIcon.Trigger)
    assert panel.isVisible() and pet.settings is panel
    assert panel.tabs.count() == 3
    assert [panel.tabs.tabText(i) for i in range(3)] == ['Vynn', 'Nhắc nhở', 'Cài đặt']
    assert panel.models.isHidden()
    panel.activity.setCurrentIndex(panel.activity.findData('sad'))
    panel.run_activity.click()
    assert pet.state == 'sad'
    panel.visibility.click()
    assert pet.user_hidden and not pet.isVisible() and panel.isVisible()
    panel.visibility.click()
    assert not pet.user_hidden and pet.isVisible()
    panel.close()
    pet.tray_activated(QSystemTrayIcon.Trigger)
    assert panel.isVisible()
    if pet.tray:
        assert pet.tray.contextMenu() is not None
    if not hasattr(pet, 'tray_actions'):
        tray_menu = pet.create_tray_controls()
    pet.sync_tray_controls()
    assert pet.tray_actions['settings'].isEnabled()
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtCore import QPoint, QPointF
    for spin in (panel.speed, panel.action_pause, panel.meditation_minutes,
                 *(pair[1] for pair in panel.reminders.values())):
        prior_value = spin.value()
        spin.setFocus()
        event = QWheelEvent(QPointF(5, 5), QPointF(spin.mapToGlobal(QPoint(5, 5))),
                            QPoint(), QPoint(0, 120), Qt.NoButton, Qt.NoModifier,
                            Qt.ScrollUpdate, False)
        QApplication.sendEvent(spin, event)
        assert spin.value() == prior_value
    pet.save()
    restored = Life(directory)
    assert restored.config['size'] == 'Tiny'
    assert restored.config['character'] == 'chibi_boy'
    assert restored.config['auto_move']
    # A short automatic jump must reach and land on a nearby internal ledge.
    pet.life.stop_focus()
    # Meditation locks commands and dragging, counts down, then can be stopped.
    panel.meditation_minutes.setValue(2)
    pet.start_meditation()
    assert pet.life.meditation == 120 and pet.motion_locked
    pet.sync_tray_controls()
    assert not pet.tray_actions['call'].isEnabled()
    assert not pet.tray_actions['pause'].isEnabled()
    assert pet.tray_actions['stop_meditate'].isEnabled()
    frozen_position = (pet.fx, pet.fy)
    pet.jump()
    pet.call()
    pet.high_five()
    pet.set_state('walk')
    QTest.mousePress(pet, Qt.LeftButton)
    assert pet.drag_offset is None
    for _ in range(5):
        pet.last_tick -= .033
        pet.advance()
    assert (pet.fx, pet.fy) == frozen_position and pet.state == 'sleep'
    assert 119 < pet.life.meditation < 120
    pet.stop_meditation()
    assert not pet.motion_locked
    assert panel.activity.findData('idle') == -1
    assert panel.activity.findData('sleep') >= 0
    panel.activity.setCurrentIndex(panel.activity.findData('sleep'))
    panel.sync()
    panel.run_activity.click()
    assert pet.state == 'sleep' and pet.life.meditation == 0 and not pet.motion_locked
    pet.jump()
    assert pet.state == 'jump', 'Ordinary meditation pose must allow actions'
    pet.set_state('sleep')
    assert pet.life.meditation == 0 and not pet.motion_locked
    panel.sections['messages'].header.setChecked(False)
    assert pet.life.config['collapsed_sections']['messages']
    assert panel.sections['messages'].body.isHidden()
    panel.sections['messages'].header.setChecked(True)
    panel.message_controls['message_seconds'].setValue(8)
    panel.message_controls['message_font'].setValue(16)
    panel.message_theme.setCurrentIndex(panel.message_theme.findData('dark'))
    panel.message_text.setText('Xin chào <b>literal</b>\nThông báo mới')
    panel.message_test.click()
    pet.last_tick -= .033
    pet.advance()
    assert pet.bubble.body.text() == 'Xin chào <b>literal</b>\nThông báo mới'
    assert pet.bubble.body.textFormat() == Qt.PlainText
    assert 7 < pet.message_until-time.monotonic() <= 8
    panel.message_enabled.setChecked(False)
    assert not pet.messages and not pet.bubble.isVisible()
    pet.say('Should stay hidden')
    assert not pet.messages
    panel.message_enabled.setChecked(True)
    panel.dialogue_kind.setCurrentIndex(panel.dialogue_kind.findData('action.walk'))
    assert not panel.dialogue_enabled.isChecked()
    panel.dialogue_enabled.setChecked(True)
    panel.dialogue_editor.setPlainText('Đi dạo nhé!\nNăng lượng {energy}%')
    panel.dialogue_test.click()
    assert list(pet.messages) == [f'Đi dạo nhé!\nNăng lượng {round(pet.life.energy)}%']
    pet.messages.clear()
    pet.dismiss_message()
    pet.last_action_message = 0
    pet.set_state('look')
    pet.messages.clear()
    pet.last_action_message = 0
    pet.set_state('walk')
    assert list(pet.messages) == [f'Đi dạo nhé!\nNăng lượng {round(pet.life.energy)}%']
    panel.dialogue_kind.setCurrentIndex(panel.dialogue_kind.findData('notice.water'))
    panel.dialogue_editor.setPlainText('Uống nước thôi {affection}!')
    pet.life.elapsed['water'] = pet.life.config['water_min']*60-1
    assert f'Uống nước thôi {round(pet.life.affection)}!' in pet.life.tick(2)
    panel.dialogue_enabled.setChecked(False)
    pet.messages.clear()
    panel.dialogue_test.click()
    assert not pet.messages
    pet.save()
    restored = Life(directory)
    assert restored.config['dialogue']['notice.water'] == 'Uống nước thôi {affection}!'
    assert not restored.config['dialogue_enabled']['notice.water']
    panel.dialogue_reset.click()
    assert 'notice.water' not in pet.life.config['dialogue']
    assert panel.dialogue_enabled.isChecked()
    pet.start_meditation(1)
    panel.sync()
    assert panel.end_meditation.isEnabled() and not panel.begin_meditation.isEnabled()
    panel.end_meditation.click()
    assert not pet.motion_locked
    assert panel.activity.findData('groom') >= 0
    # The app must execute a complete multi-hop route, not merely compute it.
    floor = bounds.bottom()+1
    left = bounds.left()
    pet.surfaces = [(('owner', 'a'), QRect(left+180, floor-65, 60, 12)),
                    (('owner', 'b'), QRect(left+280, floor-130, 60, 12)),
                    (('owner', 'c'), QRect(left+380, floor-195, 60, 12))]
    pet.surface_owners = {key: 'owner' for key, _ in pet.surfaces}
    pet.perch, pet.support_ref = None, None
    pet.fx, pet.fy = float(left+80-pet.width()/2), float(floor-pet.height())
    pet.life.config['auto_move'] = False
    pet.life.config['stay'] = False
    pet.set_state('idle')
    assert pet.request_route(('owner', 'c'))
    planned = pet.route_future.result(timeout=4)
    assert len(planned) >= 3, planned
    for _ in range(1200):
        pet.last_tick -= .033
        pet.advance()
        if pet.perch == ('owner', 'c'):
            break
    assert pet.perch == ('owner', 'c'), (pet.perch, pet.state, pet.navigation_status, list(pet.route))
    pet.life.config['stay'] = False
    pet.life.config['auto_move'] = False
    pet.life.config['window_perches'] = True
    pet.set_size('Small')
    floor = bounds.bottom() + 1
    pet.fx = float(bounds.left() + 150)
    pet.fy = float(floor - pet.height())
    pet.perch, pet.support_ref = None, None
    pet.surfaces = [(999, QRect(bounds.left() + 210, floor - 55, 140, 30))]
    pet.surface_owners = {}
    pet.set_state('idle')
    assert pet.explore()
    for _ in range(80):
        pet.last_tick -= .016
        pet.advance()
        if pet.perch == 999:
            break
    assert pet.perch == 999 and pet.y() + pet.height() == floor - 55
    assert jump_velocity(1000, -50) is None
    assert jump_velocity(10, -500) is None
    assert jump_velocity(10, -500, max_rise=None, max_duration=None) is not None
    assert jump_velocity(10, -1500, max_rise=None, max_duration=None) is not None
    # Calm walking stays on its ledge and lasts at most three seconds.
    pet.fx = float(pet.surfaces[0][1].right() - pet.width()/2 - 8)
    pet.facing = 1
    pet.set_state('walk')
    assert 1.5 <= pet.state_duration <= 3
    pet.last_tick -= .05
    pet.advance()
    assert pet.state == 'idle' and pet.perch == 999
    pet.set_state('hang')
    pet.last_tick -= .033
    pet.advance()
    assert pet.state == 'hang' and pet.perch == 999
    assert pet.y() + pet.height() > pet.surfaces[0][1].top()
    pet.state_start -= 1.1
    pet.last_tick -= .033
    pet.advance()
    pet.last_tick -= .033
    pet.advance()
    assert pet.state == 'idle' and pet.y() + pet.height() == pet.surfaces[0][1].top()
    for activity in ('sit', 'look', 'groom', 'stretch'):
        pet.set_state(activity)
        assert not pet.grab().isNull()
    assert pet.life.config['move_speed'] == 28
    # Touching tabs: walk across without teleporting or dropping off the edge.
    edge_y = bounds.top()+300
    tab_a = QRect(bounds.left()+100, edge_y, 150, 25)
    tab_b = QRect(bounds.left()+250, edge_y, 130, 25)
    pet.surfaces = [('tab_a', tab_a), ('tab_b', tab_b)]
    pet.surface_owners = {'tab_a': 111, 'tab_b': 111}
    pet.life.config['stay'] = False
    pet.perch, pet.support_ref = 'tab_a', None
    pet.fx = float(tab_a.right()-8-pet.width()/2)
    pet.fy = float(edge_y-pet.height())
    pet.facing = 1
    pet.set_state('walk')
    prior = pet.fx
    pet.last_tick -= .05
    pet.advance()
    assert pet.perch == 'tab_b' and pet.state == 'walk'
    assert 0 < pet.fx-prior <= 3
    for _ in range(20):
        pet.last_tick -= .033
        pet.advance()
        assert pet.perch == 'tab_b' and pet.state == 'walk'
    # Walking still uses a controlled hop across a nearby gap or height change.
    tab_c = QRect(bounds.left()+400, edge_y-25, 130, 25)
    pet.surfaces.append(('tab_c', tab_c))
    pet.surface_owners['tab_c'] = 111
    pet.fx = float(tab_b.right()-8-pet.width()/2)
    assert pet.cross_to_neighbor(tab_b)
    assert pet.state == 'jump' and pet.jump_target == 'tab_c'
    for _ in range(80):
        pet.last_tick -= .016
        pet.advance()
        if pet.perch == 'tab_c':
            break
    assert pet.perch == 'tab_c'
    with patch.object(pet, 'request_route') as request, patch.object(pet, 'explore') as explore:
        for _ in range(40):
            pet.choose_activity()
            assert pet.state != 'jump'
        request.assert_not_called()
        explore.assert_not_called()
    pet.set_state('idle')
    before_grab = pet.grab().toImage()
    QTest.mousePress(pet, Qt.LeftButton, pos=pet.rect().center())
    assert pet.drag_offset is None and pet.hold_timer.isActive()
    pet.life.affection = 50
    QTest.mouseRelease(pet, Qt.LeftButton, pos=pet.rect().center())
    assert pet.drag_offset is None
    assert pet.state == 'high_five' and pet.life.affection == 55
    # A quick click followed immediately by another hold cancels the old arm.
    QCursor.setPos(pet.mapToGlobal(pet.rect().center()))
    QTest.mouseDClick(pet, Qt.LeftButton, pos=pet.rect().center())
    assert pet.state == 'idle' and pet.high_five_target is None
    assert pet.hold_timer.isActive()
    QTest.qWait(500)
    assert pet.drag_offset is not None and pet.vx == pet.vy == 0
    assert pet.grab().toImage() != before_grab, 'Long hold shows gripping arms'
    QTest.mouseRelease(pet, Qt.LeftButton, pos=pet.rect().center())
    assert pet.drag_offset is None and pet.state == 'idle'
    assert pet.life.affection == 55, 'Long hold must not also high-five'
    # Release rescans real windows; reset the synthetic perch before checking
    # unrelated automatic activities below.
    pet.perch, pet.support_ref = None, None
    pet.fy = float(bounds.bottom()+1-pet.height())
    pet.move(round(pet.fx), round(pet.fy))
    assert render_pose('sleep') != render_pose('sit')
    panel.action_pause.setValue(2)
    assert pet.life.config['action_pause'] == 2
    pet.set_state('idle')
    assert pet.state_duration < 3
    pet.life.config['auto_move'] = True
    pet.set_state('groom')
    pet.state_start -= pet.state_duration + .1
    with patch.object(pet, 'choose_activity', side_effect=lambda: pet.set_state('look')) as choose:
        pet.last_tick -= .033
        pet.advance()
        choose.assert_called_once()
        assert pet.state == 'look', 'No extra idle wait after a completed activity'
    pet.life.start_focus()
    pet.set_state('sleep')
    pet.state_start -= 20
    pet.last_tick -= .033
    pet.advance()
    assert pet.state == 'sleep', 'Focus meditation must not end after the short automatic rest'
    pet.life.stop_focus()
    windows, full = scan({int(pet.winId()), int(pet.bubble.winId())})
    print('Windows scanned:', len(windows), 'Fullscreen:', full)
    assert not hasattr(pet, 'create_menu')
    pet.shutdown()
    pet.close()
print('PASS: QPainter, grounding, states, jump, mood, routines, persistence, surfaces, unified settings, right-click/tray entry, visibility, activity controls, live model/size changes, automatic movement')
