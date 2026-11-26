import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_alpha import clean_env,expected_manifest,private_base,validate_runtime,ROOT
class AlphaLauncherTest(unittest.TestCase):
    def test_no_diagnostic_environment(self):
        env={'PATH':'/bin','HOME':'/tmp','TRIBUN_AV_DUEL':'1','TRIBUN_NATIVE_NO_DRAW':'1','GF_CAPTURE_PATH':'bad','TRIBUN_NATIVE_ONLY_LEAGUE':'1'}
        self.assertEqual(clean_env(env),{'PATH':'/bin','HOME':'/tmp'})
    def test_matching_runtime(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);binary=p/'gameplayfootball';binary.write_text('fixture');binary.chmod(0o700)
            (p/'native-match.config').write_text('fixture')
            (p/'tribun-runtime.json').write_text(json.dumps(expected_manifest()))
            self.assertEqual(validate_runtime(p),p.resolve())
            (p/'tribun-runtime.json').write_text('{}')
            with self.assertRaises(ValueError):validate_runtime(p)
    def test_private_base(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'new';self.assertEqual(private_base(p),p.resolve())
            self.assertEqual(p.stat().st_mode&0o777,0o700)
            p.chmod(0o755)
            with self.assertRaises(ValueError):private_base(p)
        with self.assertRaises(ValueError):private_base(ROOT/'alpha-private-not-created')
