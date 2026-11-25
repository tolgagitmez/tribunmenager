import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location("control",Path(__file__).resolve().parents[1]/"integrations/league-soccer/manager-control.py")
control=importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)

class NativeControlTests(unittest.TestCase):
    def test_monotonic_atomic_mailbox_and_team_isolation(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(control.publish(d,0,1,0,90,80,60,40)["state"],"submitted-not-applied")
            control.publish(d,1,1,0,20,30,40,50)
            with self.assertRaises(ValueError):
                control.publish(d,0,1,0,20,30,40,50)
            control.publish(d,0,2,60000,10,20,30,40)
            self.assertEqual((Path(d)/"team-0.txt").read_text(),"TRIBUNTACTIC1 2 60000 10 20 30 40\n")
            self.assertEqual((Path(d)/"team-1.txt").read_text(),"TRIBUNTACTIC1 1 0 20 30 40 50\n")
    def test_reject_bad_values_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as d:
            for args in ((2,1,0,10,20,30,40),(0,0,0,10,20,30,40),(0,1,5400000,10,20,30,40),(0,1,0,101,20,30,40),(0,1,0,True,20,30,40)):
                with self.assertRaises(ValueError):control.publish(d,*args)
            (Path(d)/"team-0.txt").write_text("corrupt")
            with self.assertRaises(ValueError):control.publish(d,0,1,0,10,20,30,40)
if __name__=="__main__":unittest.main()
