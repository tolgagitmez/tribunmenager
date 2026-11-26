import importlib.util
from pathlib import Path
import sys,unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location("release_quality",HERE/"release-quality.py")
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
class ReleaseQualityTest(unittest.TestCase):
    def test_missing_is_blocked(self):
        with patch.object(q,"stamp",return_value={"evidence":{"candidateSha256":"a"}}),patch.object(q.I.capacity,"fingerprint",return_value={"runtime":"x"}):
            result=q.evaluate({},Path("."),Path("."))
        self.assertEqual(result["status"],"blocked")
        self.assertFalse(result["productionEnabled"])
        self.assertFalse(result["combinedQualified"])
        self.assertFalse(result["checks"]["fullMatrix"])
        self.assertFalse(result["checks"]["headContactCoverage"])
        self.assertFalse(result["checks"]["webglActualTrace"])
    def test_uncovered_contacts_and_foreign_runtime_cannot_pass(self):
        report={"evidence":{"candidateSha256":"old"},"identity":{"runtime":"old"},
                "visual":{"contact-precision":{"metrics":{"foot":{"samples":1,"baselineMeanCm":5,"candidateMeanCm":4},"head":{"samples":0,"baselineMeanCm":None,"candidateMeanCm":None},"palm":{"samples":1,"baselineMeanCm":2,"candidateMeanCm":3}}}},
                "visualTraceSha256":"a","webgl":{"passed":True,"traceSha256":"b"}}
        with patch.object(q,"stamp",return_value={"evidence":{"candidateSha256":"new"}}),patch.object(q.I.capacity,"fingerprint",return_value={"runtime":"new"}):
            c=q.evaluate(report,Path("."),Path("."))["checks"]
        self.assertTrue(c["footContactCoverage"])
        for k in ("versionBound","sameFrozenInputs","headContactCoverage","palmContactCoverage","webglActualTrace"):
            self.assertFalse(c[k])
    def test_matrix_unique_mode_scenario_pairs(self):
        self.assertEqual(len({(s,m) for s in q.SCENARIOS for m in q.MODES}),12)
        self.assertEqual(set(q.POLICIES),{"keeper","collective","pace"})
