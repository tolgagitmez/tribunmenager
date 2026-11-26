import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('gpu',Path(__file__).resolve().parents[1]/'integrations/league-soccer/native_gpu_display.py')
g=importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

class GpuTest(unittest.TestCase):
    def test_renderer(self):
        self.assertFalse(g.parse_glx('direct rendering: Yes\nOpenGL renderer string: llvmpipe (LLVM)\nAccelerated: no')['eligible'])
        self.assertTrue(g.parse_glx('direct rendering: Yes\nOpenGL renderer string: AMD Radeon\nAccelerated: yes')['eligible'])
        self.assertTrue(g.parse_glx('direct rendering: Yes\nOpenGL renderer string: NVIDIA GeForce')['eligible'])
        self.assertFalse(g.parse_glx('direct rendering: No\nOpenGL renderer string: NVIDIA GeForce')['eligible'])
        self.assertFalse(g.parse_glx('direct rendering: Yes\nOpenGL renderer string: unknown')['eligible'])
    def test_display_and_env(self):
        self.assertEqual(g.local_display(':90.0'),':90')
        for d in ('localhost:90','host:0',':90.1',''):
            with self.assertRaises(ValueError): g.local_display(d)
        env=g.hardware_env({'LIBGL_ALWAYS_SOFTWARE':'1','LP_NUM_THREADS':'2','XAUTHORITY':'/private/auth'},':90')
        self.assertNotIn('LIBGL_ALWAYS_SOFTWARE',env)
        self.assertNotIn('LP_NUM_THREADS',env)
        self.assertEqual(env['DISPLAY'],':90')
        self.assertEqual(env['XAUTHORITY'],'/private/auth')

if __name__=='__main__': unittest.main()
