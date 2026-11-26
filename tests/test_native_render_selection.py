import copy
import importlib.util
from pathlib import Path
import unittest
import uuid
p=Path(__file__).resolve().parents[1]/'integrations/league-soccer/native_render_selection.py'
spec=importlib.util.spec_from_file_location('selection',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def report(workers,cpu):
    return dict(trialId=uuid.uuid4().hex,passed=True,renderEvidenceComplete=True,renderProbeRequested=True,glWorkers=workers,
        hostIdentity={'bootHash':'a'},profile='software',filterThreads=1,cpuPartition=False,cpuGroups=[[],[]],
        requestedMatches=2,overlapSeconds=290,processProfile={'roles':{'engine_with_software_gl':{'observedCpuSecondsLowerBound':cpu},
            'video_encoder':{'observedCpuSecondsLowerBound':50}}},
        matches=[dict(passed=True,softwareGLWorkers=workers,coverage=.99,nativeClockMs=300000,observedWallSeconds=300,
            fixtureSha256=str(i),decodedFrames=7500,droppedFrames=10,encodedVideoMaxGapSeconds=.04,browserLongestProgressIntervalMs=1000,
            renderProbe={'observed':True,'averageSwapsPerSecond':30,'p95GapMs':40,'maxGapMs':100}) for i in range(2)])

class SelectionTest(unittest.TestCase):
    def test_repeated_saving_required(self):
        a,b=report(2,100),report(1,85)
        self.assertIsNone(m.compare([(a,b)])['recommendedGLWorkers'])
        self.assertIsNone(m.compare([(a,b),(a,b)])['recommendedGLWorkers'])
        r=m.compare([(a,b),(dict(a,trialId=uuid.uuid4().hex),dict(b,trialId=uuid.uuid4().hex))])
        self.assertEqual(r['recommendedGLWorkers'],1)
        self.assertFalse(r['productionQualified'])
    def test_reject_mismatch_and_stall(self):
        a,b=report(2,100),report(1,85)
        b['matches'][0]['renderProbe']['maxGapMs']=600
        self.assertEqual(m.compare([(a,b),(dict(a,trialId=uuid.uuid4().hex),dict(b,trialId=uuid.uuid4().hex))])['recommendedGLWorkers'],2)
        b['hostIdentity']={'bootHash':'b'}
        self.assertIsNone(m.compare([(a,b),(a,b)])['recommendedGLWorkers'])
    def test_baseline_failure_and_missing_evidence(self):
        a,b=report(2,100),report(1,85)
        a['passed']=False
        self.assertIsNone(m.compare([(a,b),(a,b)])['recommendedGLWorkers'])
        a=report(2,100);del b['matches'][0]['droppedFrames']
        self.assertIsNone(m.compare([(a,b),(a,b)])['recommendedGLWorkers'])
