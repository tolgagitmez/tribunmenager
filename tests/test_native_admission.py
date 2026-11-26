import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('admission',Path(__file__).resolve().parents[1]/'integrations/league-soccer/native_admission.py')
a=importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

HOST={'bootHash':'same','runtimeManifestSha256':'same','logicalCpus':8}
GOOD={'cpuBusyPercent':50,'availableMemoryMiB':3000,'freeDiskMiB':5000}

def evidence():
    return {'hostIdentity':HOST,'profile':a.PROFILE,'requestedMatches':2,'passed':True,'filterThreads':0,
            'matches':[{'passed':True,'fixtureSha256':str(i)*64} for i in (1,2)],
            'overlapSeconds':290,'samples':[GOOD],
            'resourceSummary':{'cpuP95Percent':70,'minimumAvailableMemoryMiB':2000,'minimumFreeDiskMiB':4096}}

class AdmissionTest(unittest.TestCase):
    def test_verified_only_same_host_and_headroom(self):
        r=evidence()
        self.assertEqual(a.verified_slots(r,HOST),2)
        for change in ({'passed':False},{'profile':'gpu'},{'hostIdentity':{}},{'requestedMatches':4},
                       {'filterThreads':1},{'overlapSeconds':100},{'resourceSummary':{}},{'samples':[]}):
            self.assertEqual(a.verified_slots({**r,**change},HOST),0)
        self.assertEqual(a.verified_slots(r,dict(HOST,logicalCpus=4)),0)

    def test_queue_and_reservations(self):
        q=a.Queue(2)
        for x in ('m1','m2','m3'):q.enqueue(x)
        self.assertEqual(q.admit(dict(GOOD,cpuBusyPercent=90)),[])
        self.assertEqual(q.admit(GOOD),['m1','m2'])
        self.assertEqual(q.admit(GOOD),[])
        q.release('m1')
        self.assertEqual(q.admit(GOOD),['m3'])
        with self.assertRaises(ValueError):q.enqueue('m1')
        with self.assertRaises(ValueError):q.release('m1')

    def test_unknown_capacity_blocks_and_invalid_samples(self):
        q=a.Queue(0);q.enqueue('m1')
        self.assertEqual(q.admit(GOOD),[])
        self.assertFalse(a.pressure_ok(dict(GOOD,cpuBusyPercent=float('nan'))))
        self.assertFalse(a.pressure_ok(dict(GOOD,availableMemoryMiB=100)))

if __name__=='__main__':unittest.main()
