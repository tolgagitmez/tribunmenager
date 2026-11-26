import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]/'integrations/league-soccer'
def load(name):
    s=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
d=load('native_display_reservation')
f=load('native_capture_failure')

class IsolationTest(unittest.TestCase):
    def test_reservation_exclusive_and_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with d.reserve(root,[100,101],lambda n:False) as a:
                with d.reserve(root,[100,101],lambda n:False) as b:
                    self.assertNotEqual(a,b)
                    with self.assertRaises(RuntimeError):
                        with d.reserve(root,[100,101],lambda n:False):pass
            with d.reserve(root,[100],lambda n:False) as a:self.assertEqual(a,100)
    def test_skip_occupied(self):
        with tempfile.TemporaryDirectory() as tmp:
            with d.reserve(Path(tmp),[100,101],lambda n:n==100) as n:self.assertEqual(n,101)
    def test_report_only_allowlisted_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'runner.log').write_text('Private audio server exited\nhttp://127.0.0.1:1234/SECRET')
            (root/'native-match.capture.log').write_text('Resource temporarily unavailable')
            r=f.summarize(root)
            self.assertEqual(r['categories'],['encoder_resource','pulse_start'])
            self.assertNotIn('SECRET',str(r))

if __name__=='__main__':unittest.main()
