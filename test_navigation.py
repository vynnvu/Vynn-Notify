"""Pure routing/physics and Windows integration checks (no registry writes)."""
import sys
import tempfile
import unittest
import uuid
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from pet.navigation import Ledge, plan_route, plan_climb_route, integrate, clear_arc
from pet.behavior import jump_velocity
from pet.life import Life
from pet.platform_services import SingleInstance, startup_command, set_autostart
from pet.dialogue import DEFAULT_ENABLED, LEGACY_TEXT


class NavigationTests(unittest.TestCase):
    def test_vietnamese_defaults_upgrade_once_and_keep_custom_content(self):
        with tempfile.TemporaryDirectory() as path:
            target = Path(path)/'config.json'
            target.write_text(json.dumps({'messages_enabled': False,
                'dialogue_enabled': {'action.walk': True, 'notice.water': False},
                'dialogue': {'notice.water': LEGACY_TEXT['notice.water'], 'notice.call': 'Câu riêng của tôi'}}), encoding='utf-8')
            life = Life(path)
            self.assertTrue(life.config['messages_enabled'])
            self.assertEqual(life.config['dialogue_enabled'], DEFAULT_ENABLED)
            self.assertIn('uống nước', life.dialogue('notice.water'))
            self.assertEqual(life.dialogue('notice.call'), 'Câu riêng của tôi')
            self.assertEqual(life.dialogue('action.walk'), '')
            life.config['dialogue_enabled']['notice.water'] = False
            life.save()
            restored = Life(path)
            self.assertFalse(restored.config['dialogue_enabled']['notice.water'])

    def test_three_stage_route(self):
        ledges = [Ledge('a', 130, 330, 190, 340), Ledge('b', 230, 260, 290, 270),
                  Ledge('c', 330, 190, 390, 200)]
        route = plan_route(70, 400, None, 'c', ledges, 20, 30, 400, 0, 600, 0)
        self.assertEqual([s.key for s in route], ['a', 'b', 'c'])
        self.assertTrue(all(s.kind == 'jump' for s in route))

    def test_blocked_route_and_missing_target(self):
        target = Ledge('target', 130, 330, 190, 340)
        wall = Ledge('wall', 100, 0, 120, 400)
        self.assertEqual(plan_route(50, 400, None, 'target', [wall, target], 20, 30, 400, 0, 300, 0), [])
        self.assertEqual(plan_route(50, 400, None, 'missing', [target], 20, 30, 400, 0, 300, 0), [])

    def test_auto_climb_searches_across_intermediate_surfaces(self):
        ledges = [Ledge('a', 130, 330, 190, 340), Ledge('b', 230, 260, 290, 270),
                  Ledge('c', 330, 190, 390, 200)]
        route = plan_climb_route(70, 400, None, ledges, 20, 30, 400, 0, 600, 0)
        self.assertEqual([step.key for step in route], ['a', 'b', 'c'])
        self.assertEqual(plan_climb_route(70, 400, None, [], 20, 30, 400, 0, 600, 0), [])

    def test_tall_adjacent_wall_uses_climb(self):
        wall = Ledge('wall', 100, 180, 200, 320)
        route = plan_route(90, 300, None, 'wall', [wall], 20, 30, 300, 0, 400, 0)
        self.assertTrue(route)
        self.assertEqual(route[-1].kind, 'climb')

    def test_head_and_side_collisions_cannot_tunnel(self):
        x, y, vx, vy, _, hit = integrate(0, 100, 1000, 0, .1, 20, 30, [Ledge('wall', 60, 50, 70, 160)])
        self.assertTrue(hit)
        self.assertLessEqual(x+20, 60)
        self.assertLess(vx, 0)
        x, y, vx, vy, _, hit = integrate(20, 150, 0, -400, .1, 20, 30, [Ledge('roof', 0, 100, 100, 120)])
        self.assertTrue(hit)
        self.assertGreaterEqual(y, 120)
        self.assertGreaterEqual(vy, 0)

    def test_landing_and_obstacle_arc(self):
        r = Ledge('ledge', 0, 200, 100, 220)
        _, y, _, vy, landed, _ = integrate(20, 160, 0, 300, .1, 20, 30, [r])
        self.assertEqual((y, vy, landed), (170, 0, 'ledge'))
        velocity = jump_velocity(100, -50)
        self.assertFalse(clear_arc(50, 300, 150, 250, velocity,
            [Ledge('wall', 95, 0, 105, 300)], 20, 30, 0))

    def test_favourite_memory_and_meditation_survive_restart(self):
        with tempfile.TemporaryDirectory() as path:
            life = Life(path)
            life.remember('Chrome_WidgetWin_1:2:3:4', 5)
            life.meditation = 60
            life.save()
            restored = Life(path)
            self.assertEqual(restored.favourites, life.favourites)
            self.assertEqual(restored.meditation, 60)
            restored.tick(61, True)
            self.assertEqual(restored.meditation, 0)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows only')
    def test_named_mutex_excludes_second_instance(self):
        name = 'Local\\VynnNotifyTest.'+uuid.uuid4().hex
        first = SingleInstance(name)
        second = SingleInstance(name)
        try:
            self.assertTrue(first.acquired)
            self.assertFalse(second.acquired)
        finally:
            first.close()
            second.close()
        third = SingleInstance(name)
        self.assertTrue(third.acquired)
        third.close()

    @unittest.skipUnless(sys.platform == 'win32', 'Windows only')
    def test_startup_uses_current_path_and_is_reversible(self):
        import winreg
        self.assertIn('--background', startup_command())
        with patch.object(winreg, 'CreateKeyEx') as create, patch.object(winreg, 'SetValueEx') as write, patch.object(winreg, 'DeleteValue') as delete:
            set_autostart(True)
            write.assert_called_once()
            self.assertEqual(write.call_args.args[-1], startup_command())
            set_autostart(False)
            self.assertEqual([call.args[1] for call in delete.call_args_list],
                             ['Vynn Notify'])

    def test_default_data_directory_restores_saved_settings(self):
        with tempfile.TemporaryDirectory() as path:
            directory = Path(path)/'Vynn Notify'
            life = Life(directory)
            life.config['move_speed'] = 42
            life.save()
            with patch.dict('os.environ', {'APPDATA': path}):
                restored = Life()
                self.assertEqual(restored.directory, directory)
                self.assertEqual(restored.config['move_speed'], 42)


if __name__ == '__main__':
    unittest.main()
