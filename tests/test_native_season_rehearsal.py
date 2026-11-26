import unittest
from test_native_season import fixture
import native_season
import native_season_rehearsal as R
class RehearsalTest(unittest.TestCase):
    def test_rollback_retry_idempotency(self):
        f,m=fixture();s=native_season.candidate(f,m);s["seasonPreview"]=native_season.preview(s)
        result=R.audit(f,m,s)
        self.assertTrue(result["rollbackPassed"]);self.assertTrue(result["idempotent"])
        self.assertEqual(result["appearanceCount"],22)
        self.assertEqual(result["standings"][0]["points"],3)
    def test_conflicting_result_and_out_of_order_rejected(self):
        db=R.create();self.addCleanup(db.close)
        f,m=fixture();s=native_season.candidate(f,m);s["seasonPreview"]=native_season.preview(s)
        key=("NATIVE-REHEARSAL",1,0,1)
        self.assertTrue(R.apply(db,key,f,m,s));old=R.snapshot(db)
        f["score"]=[0,0];s=native_season.candidate(f,m);s["seasonPreview"]=native_season.preview(s)
        with self.assertRaises(ValueError):R.apply(db,key,f,m,s)
        with self.assertRaises(ValueError):R.apply(db,("NATIVE-REHEARSAL",0,0,1),f,m,s)
        self.assertEqual(R.snapshot(db),old)
