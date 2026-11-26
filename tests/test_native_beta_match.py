import importlib.util
from pathlib import Path
import sys,unittest
HERE=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location("beta",HERE/"beta-match.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BetaMatchTest(unittest.TestCase):
    def test_defaults_and_mapping(self):
        a=m.arguments(["runtime","out"])
        self.assertEqual(a.profile,"reference")
        self.assertEqual(m.options(a)["homeFormation"],"4-3-3")
        a=m.arguments(["runtime","out","--profile","combined","--home-press","80","--away-style","possession"])
        self.assertEqual(m.options(a)["homePress"],80)
        self.assertEqual(m.options(a)["awayStyle"],"possession")
    def test_invalid_values(self):
        for flags in (["--seed","-1"],["--home-press","101"],["--profile","production"],["--away-formation","invalid"]):
            with self.assertRaises(SystemExit):m.arguments(["runtime","out",*flags])
