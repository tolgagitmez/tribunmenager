import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(ROOT))
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
i=load("instrument")
b=load("collision-pose-benchmark")
class CollisionPoseTest(unittest.TestCase):
    def test_cpp_cadence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"rng.hpp").write_text(i.VISUAL_RNG_HEADER)
            (p/"test.cpp").write_text(r'''
#include "rng.hpp"
#include <cassert>
int main(){
  assert(!tribun_visual::poseDue(0));
  for(unsigned long tick=1;tick<=30000;tick++)
    assert(tribun_visual::poseDue(tick)==(tick%10==0));
}
''')
            subprocess.run(["c++","-std=c++17",str(p/"test.cpp"),"-o",str(p/"test")],check=True)
            subprocess.run([str(p/"test")],check=True)
    def test_schedule_transform(self):
        src='''#include "framework/scheduler.hpp"
  gameSequence->AddUserTaskEntry(gameTask, e_TaskPhase_Process);
  GetScheduler()->RegisterTaskSequence(gameSequence);
  GetScheduler()->RegisterTaskSequence(graphicsSequence);'''
        out=i.ordered_pose_main(src)
        self.assertLess(out.index("e_TaskPhase_Process"),out.index("e_TaskPhase_Put"))
        self.assertIn("if (!orderedPose) GetScheduler()->RegisterTaskSequence(graphicsSequence);",out)
    def test_no_phase_overlap_guard(self):
        src='''#include "gametask.hpp"
void GameTask::Action() { matchLifetimeMutex.lock(); }
void GameTask::PutPhase() {
  matchLifetimeMutex.lock();
  match->Put();
  matchLifetimeMutex.unlock();
}'''
        out=i.ordered_pose_task(src)
        self.assertIn("void GameTask::Action() { matchLifetimeMutex.lock(); }",out)
        self.assertIn("!tribun_visual::poseDue(match->GetIterations())",out)
        self.assertLess(out.index("poseDue"),out.index("match->Put()"))
    def test_collision_task_preserves_prepare_and_fetch(self):
        src='''void GameTask::ProcessPhase() {
    match->PreparePutBuffers();
    matchPutBufferMutex.unlock();
}
void GameTask::PutPhase() {
  if (match) {
    matchPutBufferMutex.lock();
    match->Put();
  }
}'''
        out=i.collision_pose_task(src)
        self.assertLess(out.index("match->PreparePutBuffers()"),out.index("match->TribunUpdateCollisionPose()"))
        self.assertIn("if (match && !tribun_visual::collisionOnly())",out)
        match=i.collision_pose_match("void Match::Put() { }")
        for anchor in ("ball->Put();","teams[0]->Put();","teams[1]->Put();","officials->Put();","RecursiveUpdateSpatialData"):
            self.assertIn(anchor,match)
        self.assertNotIn("CaptureReplayFrame",match)
    def test_isolation(self):
        with self.assertRaises(ValueError):
            b.integrated.fixed.timing.run("x","x","x",("test","1.0","0"),collision_pose=True)
    def test_repeatability_gate(self):
        def row(name,index):
            candidate=True
            match=dict(nullRenderer=True,noDraw=True,noUpload=True,sharedAssets=False,configuredRenderIntervalMs=100,
                softwareRenderThreads=1,attackProfile="short-match",exactNativeDuration=True,nativeElapsedMs=300000,
                halfMs=150000,scale=1.0,retention=False,boxRuns=False,timedAttack=False,quickRestarts=False,
                leanScene=True,visualRng=True,skipPitchTexture=True,positionSkinning=True,requestedTaskWorkers=3,
                hardwareThreads=8,taskWorkerPool=3,determinismProbe=True,orderedPose=True,collisionPose=name=="collision",
                observedWallMs=300100,maxObservedGapMs=200,resources=dict(userSeconds=30,systemSeconds=2,maxRssKiB=500),
                nativeMemory=dict(peakPssKiB=300,peakNativeThreads=10,sampleCount=300),
                gameplay={k:[1,1] for k in b.integrated.METRICS})
            return dict(runId=name+str(index),match=match,digests={0:"a",100:"b"})
        runs={name:[row(name,j) for j in range(2)] for name in ("visual","collision")}
        self.assertTrue(b.evaluate(runs)["collisionObservedRepeatability"])
        runs["collision"][1]["digests"][100]="x"
        self.assertFalse(b.evaluate(runs)["collisionObservedRepeatability"])
