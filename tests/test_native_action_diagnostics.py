from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_action_diagnostics import inspect_actions

def line(event,action,actual=100):
    return f'[tribun-action] phase=1 actual_ms={actual} match_ms=1800 team=0 player=7 event={event} action={action}\n'

class ActionDiagnosticsTest(unittest.TestCase):
    def read(self,data):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'game.log'
            p.write_text(data)
            return inspect_actions(p)

    def test_candidates_and_contacts_separate(self):
        r=self.read(line('rejected','short-pass')+line('accepted','short-pass')+
                    line('contact','short-pass',300)+line('accepted','movement'))
        self.assertEqual(r['counts']['short-pass'],dict(rejected=1,accepted=1,contact=1))
        self.assertEqual(r['counts']['movement'],dict(accepted=1))
        self.assertEqual(r['events'][2]['actualMs'],300)

    def test_missed_and_invalid(self):
        r=self.read(line('missed-touch','shot')+line('contact','movement')+
                    '[tribun-action] bad\nunrelated\n')
        self.assertEqual(r['counts']['shot'],{'missed-touch':1})
        self.assertEqual(r['invalidLines'],2)

    def test_missing_and_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(inspect_actions(Path(d)/'missing'))
        self.assertFalse(self.read('ordinary log\n')['evidenceAvailable'])

    def test_bounded_events(self):
        with patch('native_action_diagnostics.MAX_EVENTS',2):
            r=self.read(line('accepted','ball-control')*3)
        self.assertEqual(r['observedEvents'],3)
        self.assertEqual(len(r['events']),2)
        self.assertTrue(r['truncated'])

    def test_size_limit(self):
        with patch('native_action_diagnostics.LIMIT',1):
            with self.assertRaises(ValueError):
                self.read('too big')


    def test_alternative_promotion_is_not_contact(self):
        p='[tribun-action-alternative] phase=1 match_ms=1800 team=0 player=7 from=shot to=short-pass\n'
        r=self.read(p+line('rejected','short-pass')+p)
        self.assertEqual(r['alternativePromotions'],2)
        self.assertEqual(r['alternativeCounts'],{'shot->short-pass':2})
        self.assertEqual(r['observedEvents'],1)
        self.assertNotIn('contact',r['counts']['short-pass'])
        self.assertEqual(r['alternativeEvents'][0]['playerId'],7)


    def test_touch_geometry_and_retry(self):
        g='[tribun-touch-geometry] phase=1 match_ms=1800 team=0 player=7 action=shot distance=0.5000 limit=0.4000 height_error=0.1000 body_angle=-0.2 player_speed=0.5 ball_speed=0.2 frame=10 touch_frame=10\n'
        p='[tribun-touch-retry] phase=1 match_ms=1800 team=0 player=7 from=shot to=short-pass\n'
        r=self.read(g+g.replace('0.5000','0.3000').replace('0.1000','1.1000')+p)
        self.assertEqual(r['touchGeometryCounts'],{'distance':1,'height':1})
        self.assertEqual(r['touchRetryPromotions'],1)
        self.assertEqual(r['observedEvents'],0)
        self.assertTrue(r['evidenceAvailable'])
        self.assertEqual(r['touchGeometryEvents'][0]['frame'],10)
        self.assertEqual(self.read(g.replace('0.5000','nan'))['invalidLines'],1)


    def test_body_preparation_requests(self):
        p='[tribun-body-preparation] phase=1 match_ms=1800 team=0 player=7 action=shot body_dot=0.1000 adjustment=0.3000 clearance=3.0000\n'
        r=self.read(p+p.replace('0.3000','0.9000'))
        self.assertEqual(r['bodyPreparationRequests'],1)
        self.assertEqual(r['bodyPreparationCounts'],{'shot':1})
        self.assertEqual(r['bodyPreparationEvents'][0]['adjustment'],.3)
        self.assertEqual(r['invalidLines'],1)
        self.assertEqual(r['observedEvents'],0)
        self.assertTrue(r['evidenceAvailable'])


    def test_paired_foot_timing(self):
        p='[tribun-foot-timing] phase=1 match_ms=1800 team=0 player=7 action=shot anim=22 frame=12 elapsed_ms=120 state_foot=0 anim_foot=1 outgoing_foot=0 contact_side=right geometry=pass\n'
        r=self.read(p+p.replace('120 state','140 state')+p.replace('geometry=pass','geometry=miss')+p.replace('120 state','2001 state'))
        self.assertEqual(r['pairedFootTimingCount'],3)
        self.assertEqual(r['pairedFootTimingCounts'],{'shot:pass':2,'shot:miss':1})
        self.assertEqual(r['meanPairedTimingMs'],{'shot:pass':130.0,'shot:miss':120.0})
        self.assertEqual(r['pairedFootTimingEvents'][0]['contactSide'],'right')
        self.assertEqual(r['invalidLines'],1)
        self.assertEqual(r['observedEvents'],0)
        self.assertTrue(r['evidenceAvailable'])
