import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('profile', Path(__file__).resolve().parents[1] / 'integrations/league-soccer/native_process_profile.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class ProcessProfileTest(unittest.TestCase):
    def test_roles(self):
        self.assertEqual(p.role('gameplayfootball', []), 'engine_with_software_gl')
        self.assertEqual(p.role('ffmpeg', ['x11grab']), 'video_encoder')
        self.assertEqual(p.role('ffmpeg', ['-f', 's16le']), 'media_audit')
        self.assertEqual(p.role('chrome', []), 'browser')

    def test_stat_with_parentheses(self):
        fields = ['S'] + ['0'] * 21
        for i,v in [(1,7),(11,12),(12,13),(19,123),(21,5)]: fields[i]=str(v)
        self.assertEqual(p.parse_stat('42 (a (b)) ' + ' '.join(fields)), (42,7,123,25,5))

    def test_isolation_and_pid_reuse(self):
        meter = p.ProcessProfile(hz=100,page_size=1048576)
        rows={1:(0,1,100,1,'supervisor_other'),2:(1,2,200,2,'video_encoder'),
              3:(2,3,300,3,'browser'),4:(0,4,900,9,'browser')}
        meter.observe(rows,[1])
        rows[2]=(1,2,250,4,'video_encoder')
        rows[3]=(2,33,999,3,'browser')
        s=meter.observe(rows,[1])
        self.assertEqual(s['video_encoder']['observedCpuSeconds'],.5)
        self.assertEqual(s['browser']['observedCpuSeconds'],0)
        self.assertEqual(s['browser']['processCount'],1)
        self.assertEqual(meter.report()['roles']['video_encoder']['peakSummedRssMiB'],4)

if __name__ == '__main__': unittest.main()
