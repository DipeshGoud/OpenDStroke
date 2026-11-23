import importlib.util
import json
from pathlib import Path
import queue
import sys
import tempfile
import unittest
from unittest import mock

FILE = Path(__file__).resolve().parents[1] / 'OpenDStroke.py'
spec = importlib.util.spec_from_file_location('keyhalo', FILE)
keyhalo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keyhalo)


class CoreTests(unittest.TestCase):
    def test_style_normalization(self):
        style = keyhalo.normalized_style({'fill':'#ABCDEF','text':'bad', 'radius': 999, 'font_size':-3})
        self.assertEqual(style['fill'], '#ABCDEF')
        self.assertEqual(style['text'], keyhalo.PRESETS['Graphite']['text'])
        self.assertEqual(style['radius'],22)
        self.assertEqual(style['font_size'],12)

    def test_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(keyhalo.os.environ,{'APPDATA':folder}):
            settings = keyhalo.read_settings()
            settings['theme']='Light'
            settings['style']='Custom'
            settings['mouse']=False
            keyhalo.write_settings(settings)
            updated = keyhalo.read_settings()
            self.assertEqual(updated['theme'],'Light')
            self.assertFalse(updated['mouse'])
            self.assertEqual(updated['style'],'Custom')

    def test_keyboard_shortcut_and_modifiers(self):
        events = queue.Queue()
        inp=keyhalo.WindowsInput(events)
        inp.on_key(0xA2,down=True) # ctrl
        inp.on_key(0xA0,down=True) # shift
        inp.on_key(0x53,down=True) # s
        self.assertEqual(events.get()[0],'keyboard')
        self.assertEqual(events.get()[1],['Ctrl','Shift'])
        self.assertEqual(events.get()[1],['Ctrl','Shift','S'])
        inp.on_key(0x53,down=True) # repeat must be ignored
        self.assertTrue(events.empty())
        inp.on_key(0x53,down=False)
        inp.on_key(0x4F,down=True)
        self.assertEqual(events.get(),('toggle',))

    def test_mouse_click_wheel(self):
        q=queue.Queue()
        inp=keyhalo.WindowsInput(q)
        inp.on_mouse(inp.WM_LBUTTONDOWN,0,101,301)
        inp.on_mouse(inp.WM_MOUSEWHEEL,120 << 16,101,301)
        inp.on_mouse(inp.WM_MOUSEWHEEL,(-120 & 0xFFFF)<<16,101,301)
        self.assertEqual(q.get(),('mouse','Left click',101,301,1))
        self.assertEqual(q.get()[1],'Scroll up')
        self.assertEqual(q.get()[1],'Scroll down')

    def test_rapid_clicks_increment_and_reset(self):
        q = queue.Queue()
        inp = keyhalo.WindowsInput(q)
        with mock.patch.object(keyhalo.time, 'monotonic', side_effect=[10, 10.1, 10.2, 11.2]):
            for x in (100, 100, 200, 200):
                inp.on_mouse(inp.WM_LBUTTONDOWN, x=x, y=100)
        self.assertEqual([q.get()[4] for _ in range(4)], [1, 2, 1, 1])

    def test_corrupted_settings_do_not_crash(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(keyhalo.os.environ,{'APPDATA':folder}):
            path=keyhalo.settings_file()
            path.parent.mkdir(parents=True)
            path.write_text('{bad json')
            self.assertEqual(keyhalo.read_settings()['style'],'Graphite')

if __name__=='__main__':
    unittest.main()
