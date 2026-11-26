import array,importlib.util,io,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
spec=importlib.util.spec_from_file_location("native_audio",HERE/"native_audio_capture.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class NativeAudioTest(unittest.TestCase):
    def test_config_overrides_existing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"game.config";p.write_text('"audio_renderer" "null"\n"audio_volume" "0.000000"\n"debug" "true"\n')
            s=m.audio_config(p).read_text()
            self.assertEqual(s.count('"audio_renderer"'),1);self.assertIn('"audio_renderer" "openal"',s)
            self.assertIn('"audio_volume" "0.500000"',s);self.assertIn('"debug" "true"',s)
            self.assertIn('"null"',p.read_text())
    def test_decoded_energy_detects_silence(self):
        samples=array.array("h",[0]*48000+[1000,-1000]*24000)
        metrics=m.pcm_metrics(io.BytesIO(samples.tobytes()))
        self.assertEqual(metrics["durationSeconds"],2)
        self.assertEqual(metrics["nonSilentWindows"],1)
        silent=m.pcm_metrics(io.BytesIO(bytes(96000)))
        self.assertEqual(silent["nonSilentWindows"],0)
        with self.assertRaises(ValueError):m.pcm_metrics(io.BytesIO(b""))
