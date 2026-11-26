import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("smoke",Path(__file__).resolve().parents[1]/"integrations/league-soccer/manager-control-smoke.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def records():
    start=5000
    def ack(rev,nominal):
        return dict(revision=rev,appliedMatchMs=nominal,appliedElapsedMs=start+nominal//18)
    a,b,c=ack(1,720000),ack(1,900000),ack(2,3780000)
    return [dict(fixedClock=dict(started=True,startMs=start),elapsedMs=start+50000,managerTactics=[a,b]),
            dict(fixedClock=dict(started=True,startMs=start),elapsedMs=start+220000,managerTactics=[c,b])]
class FixedControlsTest(unittest.TestCase):
    def test_both_halves(self):self.assertEqual(len(m.verify_fixed_controls(records())),3)
    def test_second_half_command_too_early(self):
        r=records();r[1]["managerTactics"][0]["appliedMatchMs"]=1800000
        r[1]["managerTactics"][0]["appliedElapsedMs"]=105000
        with self.assertRaises(ValueError):m.verify_fixed_controls(r)
    def test_wrong_clock(self):
        r=records();r[0]["managerTactics"][0]["appliedElapsedMs"]+=10
        with self.assertRaises(ValueError):m.verify_fixed_controls(r)
    def test_missing_command(self):
        with self.assertRaises(ValueError):m.verify_fixed_controls(records()[:1])
