import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_scheduler_policy import admitted_slots,pressure_ok
from test_native_admission import evidence,HOST,GOOD

class SchedulerPolicyTest(unittest.TestCase):
    def report(self):
        host={'host':HOST,'affinity':[0,1],'limitsSha256':'test','cgroup':'test'}
        r=evidence()
        r.update(admissionIdentity=host,completedAt=10000,allMatchesPassed=True,distinctFixtures=True,
            admissionGroupSummary=dict(GOOD,groupCpuBusyPercent=60,groupThrottleFraction=.01,groupMemoryHeadroomMiB=2000))
        for m in r['matches']:
            m.update(nativeExit=0,browserExit=0,nativeClockMs=300000,observedWallSeconds=300,coverage=.99,
                audioOwnershipVerified=True,acknowledgements=2,decodedFrames=7500,droppedFrames=5)
        return r,host
    def test_fresh_complete_same_host(self):
        r,h=self.report()
        self.assertEqual(admitted_slots(r,h,10001),2)
        self.assertEqual(admitted_slots(r,h,14000),0)
        self.assertEqual(admitted_slots(r,dict(h,affinity=[0]),10001),0)
        r['matches'][0]['observedWallSeconds']=666
        self.assertEqual(admitted_slots(r,h,10001),0)
    def test_resource_gate(self):
        r,h=self.report()
        for change in ({'groupCpuBusyPercent':99},{'groupThrottleFraction':.5},{'groupMemoryHeadroomMiB':500}):
            self.assertFalse(pressure_ok(dict(r['admissionGroupSummary'],**change)))
        del r['admissionGroupSummary']
        self.assertEqual(admitted_slots(r,h,10001),0)
