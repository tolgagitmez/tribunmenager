import sys
from pathlib import Path
import tempfile
import subprocess
import os
import unittest
HERE=Path(__file__).resolve().parents[1]/'integrations/league-soccer'
sys.path.insert(0,str(HERE))
from native_gl_context import compile_hook,verify
class ContextTest(unittest.TestCase):
    def test_context_interposition_with_mock(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);mock=p/'mock.so';exe=p/'driver';hook=p/'hook.so';log=p/'context.log'
            (p/'mock.c').write_text('const unsigned char *glGetString(unsigned int n){return (const unsigned char *)(n==0x1F00?"Mock Vendor":n==0x1F01?"Mock GPU":"4.6");} void SDL_GL_SwapWindow(void *p){}')
            (p/'driver.c').write_text('void SDL_GL_SwapWindow(void*); int main(){SDL_GL_SwapWindow(0);return 0;}')
            subprocess.run(['cc','-shared','-fPIC',str(p/'mock.c'),'-o',str(mock)],check=True)
            subprocess.run(['cc',str(p/'driver.c'),str(mock),'-o',str(exe)],check=True)
            compile_hook(HERE/'native_gl_context_hook.c',hook)
            subprocess.run([str(exe)],env=dict(os.environ,LD_PRELOAD=str(hook),TRIBUN_NATIVE_GL_CONTEXT_LOG=str(log)),check=True)
            pre=dict(eligible=True,vendor='Mock Vendor',renderer='Mock GPU')
            self.assertTrue(verify(log,pre)['hardwareContextVerified'])
            with self.assertRaises(ValueError):verify(log,dict(pre,renderer='different'))
            log.write_text('vendor=Mock Vendor\nrenderer=llvmpipe\nversion=4.6\n')
            with self.assertRaises(ValueError):verify(log,dict(pre,renderer='llvmpipe'))
