import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_gpu_display import wsl_environment,parse_glx
class WslGpuTest(unittest.TestCase):
    def test_reject_non_wsl(self):
        with patch('native_gpu_display.Path.read_text',return_value='linux'):
            with self.assertRaises(ValueError):wsl_environment({'DISPLAY':':0'})
    def test_env(self):
        with patch('native_gpu_display.Path.read_text',return_value='microsoft-standard-WSL2'),patch('native_gpu_display.Path.exists',return_value=True),patch('native_gpu_display.Path.is_dir',return_value=True):
            env=wsl_environment({'DISPLAY':':0','LIBGL_ALWAYS_SOFTWARE':'1','LP_NUM_THREADS':'2'})
            self.assertEqual(env['GALLIUM_DRIVER'],'d3d12')
            self.assertNotIn('LIBGL_ALWAYS_SOFTWARE',env)
            with self.assertRaises(ValueError):wsl_environment({'DISPLAY':':1'})
    def test_renderer(self):
        self.assertTrue(parse_glx('direct rendering: Yes\nAccelerated: yes\nOpenGL renderer string: D3D12 (Intel(R) UHD Graphics)\n')['eligible'])
        self.assertFalse(parse_glx('direct rendering: Yes\nAccelerated: no\nOpenGL renderer string: llvmpipe\n')['eligible'])
