import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('encoder',Path(__file__).resolve().parents[1]/'integrations/league-soccer/native_hw_encoder.py')
e=importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)

class EncoderTest(unittest.TestCase):
    def test_default_unchanged(self):
        init,enc,gop=e.plan('x264')
        self.assertEqual(init,[])
        self.assertIn('libx264',enc)
        self.assertIn('zerolatency',gop)

    def test_hardware_explicit_no_fallback(self):
        for backend,device,codec in [('nvenc','','h264_nvenc'),('vaapi','/dev/dri/renderD128','h264_vaapi'),('qsv','/dev/dri/renderD129','h264_qsv')]:
            init,enc,gop=e.plan(backend,device)
            self.assertIn(codec,enc)
            self.assertNotIn('libx264',enc)
            self.assertEqual(gop[gop.index('-bf')+1],'0')
            self.assertIn('baseline',gop)
        for args in [('unknown',),('qsv',),('vaapi','/tmp/device'),('nvenc','','abc'),('x264','/dev/dri/renderD128')]:
            with self.assertRaises(ValueError): e.plan(*args)

    def test_output_contract(self):
        stream=dict(codec_name='h264',width=1280,height=720,pix_fmt='yuv420p',has_b_frames=0,profile='Constrained Baseline')
        self.assertTrue(e.verify_stream(stream))
        self.assertFalse(e.verify_stream(dict(stream,has_b_frames=2)))
        self.assertFalse(e.verify_stream(dict(stream,profile='High')))

if __name__=='__main__': unittest.main()
