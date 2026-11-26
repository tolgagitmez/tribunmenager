import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location("contrast",ROOT/"attribute-contrast.py")
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class ContrastTest(unittest.TestCase):
    def test_runtime_attribute_delivery(self):
        teams=[];players=[]
        for team in range(2):
            expected=[]
            for slot in range(11):
                id=team*11+slot+1
                stats={k:.7 for k in c.ATTRS}
                if slot:
                    for key in c.AXES["dribbling"]:stats[key]=.9 if team==0 else .55
                expected.append(dict(nativeId=id,stats=stats))
                players.append(dict(team=team,databaseId=id,goalkeeper=not slot,nativeAttributes={k:v*.8 for k,v in stats.items()},nativeRawAttributes=stats.copy(),nativeStatMultiplier=.8))
            teams.append(dict(team=team,players=expected))
        self.assertEqual(c.verify_attributes({"players":players},{"teams":teams},"dribbling",0),[10,10])
        players[2]["nativeAttributes"]["technical_dribble"]=.55
        with self.assertRaises(ValueError):c.verify_attributes({"players":players},{"teams":teams},"dribbling",0)
    def test_missing_mirrored_leg(self):
        with self.assertRaises(ValueError):c.compare("pace",{0:{}})
