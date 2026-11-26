import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from instrument import optimize_skinning_channels
from short_match_patch import optimize_joint_cache
from native_av_attack_comparison import diagnostic_summary

class CompositionTest(unittest.TestCase):
    def test_old_channels_then_joint_cache(self):
        # Minimal exact upstream anchors; actual complete tree is separately
        # exercised by the pinned patch-only preflight.
        raw='''#include <cmath>
#include "humanoid.hpp"
void HumanoidBase::UpdateFullbodyModel(bool updateSrc) {
  int uploadVertices = true;
  int uploadNormals = true;
  int uploadTangents = true;
  int uploadBitangents = true;
  resultVertex -= joints[weightedVertices[v].bones[0].jointID].origPos * zMultiplier;
  resultVertex += joints[weightedVertices[v].bones[0].jointID].position * zMultiplier;
  adaptedVertex -= joints[weightedVertices[v].bones[b].jointID].origPos * zMultiplier;
  adaptedVertex += joints[weightedVertices[v].bones[b].jointID].position * zMultiplier;
  fullbodyGeometryData->resourceMutex.unlock();
}'''
        result=optimize_joint_cache(optimize_skinning_channels(raw))
        self.assertIn('const bool uploadBitangents = channels.bitangents;',result)
        self.assertIn('bindOffset(weightedVertices[v].bones[b].jointID)',result)
        self.assertIn('[tribun-skin-cache]',result)
        self.assertLess(result.index('const bool uploadBitangents'),result.index('const char* skinCacheMode'))
    def test_diagnostics_do_not_copy_sensitive_messages(self):
        n={'status':'failed','failureType':'RuntimeError','failureMessage':'private secret','runnerExit':1,'checks':{'wallWithinOneSecond':False,'other':'secret'}}
        b={'passed':True,'error':'secret','diagnostic':{'url':'secret'}}
        d=diagnostic_summary(n,b,[SimpleNamespace(returncode=1),SimpleNamespace(returncode=0)],{'process':'native','code':1})
        self.assertEqual(d['firstFailedChild']['process'],'native')
        self.assertEqual(d['nativeExit'],1)
        self.assertEqual(d['browserChecks'],{'passed':True})
        self.assertNotIn('secret',str(d))
