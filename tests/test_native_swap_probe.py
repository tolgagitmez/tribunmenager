import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import os
import subprocess

HERE=Path(__file__).resolve().parents[1]/'integrations/league-soccer'
spec=importlib.util.spec_from_file_location('swap',HERE/'native_swap_probe.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SwapProbeTest(unittest.TestCase):
    def test_stats_and_missing_hook(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t)/'swaps'
            self.assertFalse(m.summarize(base,10,12)['observed'])
            p=Path(str(base)+'.sdl2')
            p.write_bytes(b''.join(struct.pack('=Q',int((10+i*.04)*1e9)) for i in range(51)))
            r=m.summarize(base,10,12)
            self.assertTrue(r['observed']);self.assertEqual(r['completedSwaps'],51)
            self.assertAlmostEqual(r['p95GapMs'],40,places=1)
            Path(str(base)+'.sdl1').write_bytes(b'')
            self.assertFalse(m.summarize(base,10,12)['observed'])
    def test_actual_dynamic_interposition(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);lib=p/'mock.so';exe=p/'driver';hook=p/'hook.so'
            (p/'mock.c').write_text('void SDL_GL_SwapWindow(void *p){}')
            (p/'driver.c').write_text('void SDL_GL_SwapWindow(void*); int main(){for(int i=0;i<3;i++)SDL_GL_SwapWindow(0);return 0;}')
            subprocess.run(['cc','-shared','-fPIC',str(p/'mock.c'),'-o',str(lib)],check=True)
            subprocess.run(['cc',str(p/'driver.c'),str(lib),'-o',str(exe)],check=True)
            m.compile_probe(HERE/'native_swap_hook.c',hook)
            subprocess.run([str(exe)],env=dict(os.environ,LD_PRELOAD=str(hook),TRIBUN_SWAP_LOG=str(p/'swaps')),check=True)
            self.assertEqual((p/'swaps.sdl2').stat().st_size,24)

if __name__=='__main__':unittest.main()
