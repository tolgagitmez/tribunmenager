import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
m=load("runtime-layout")
b=load("shared-assets-benchmark")
class SharedAssetsTest(unittest.TestCase):
    def test_layout_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/"source";source.mkdir()
            for name in ("data","databases","media","locale"):
                (source/name).mkdir();(source/name/"file").write_text(name)
            for name in ("gameplayfootball","native-match.config","tribun-runtime.json","run_menu_smoke.sh"):
                (source/name).write_text(name)
            snapshot=root/"snapshot";m.freeze(source,snapshot)
            self.assertTrue((source/"media/file").stat().st_mode&0o200)
            for name in ("a","b"):
                work=root/name;work.mkdir()
                row=m.materialize(snapshot,work,root/(name+".json"))
                self.assertTrue((work/"media").is_symlink())
                self.assertFalse((work/"databases").is_symlink())
                self.assertGreater(row["sharedLogicalBytes"],0)
            (root/"a/databases/file").write_text("changed")
            self.assertEqual((root/"b/databases/file").read_text(),"databases")
            self.assertEqual(m.identity(source),m.identity(snapshot))
            (snapshot/"media/file").chmod(0o644)
            with self.assertRaises(ValueError):
                list(m.inspect(snapshot/"media",readonly=True))
    def test_reject_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/"target").write_text("x");(p/"link").symlink_to(p/"target")
            with self.assertRaises(ValueError):list(m.inspect(p/"link"))
    def test_pss_delta(self):
        def row(shared,pss):
            return dict(sharedAssets=shared,nullRenderer=True,exactNativeDuration=True,nativeElapsedMs=300000,
                firstObservedMonotonic=10,finalObservedMonotonic=310,observedWallMs=300000,
                nativeMemory=dict(peakPssKiB=pss,peakPrivateDirtyKiB=70),
                resources=dict(userSeconds=10,systemSeconds=1))
        a=row(False,100);c=row(True,80)
        self.assertEqual(b.evaluate({"copy":[a,a],"shared":[c,c]})["sumIndividualPeakPssDeltaKiB"],-40)
        with self.assertRaises(ValueError):b.evaluate({"copy":[a,a],"shared":[a,a]})
