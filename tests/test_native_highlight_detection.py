import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integrations/league-soccer'))
from native_highlight_detection import analyze, classify, DURATION


def player(i, team, x, y, vx=0, owner=False, keeper=False):
    return dict(id=i, team=team, position=[x,y,0], velocity=[vx,0,0],
                uniquePossession=owner, goalkeeper=keeper)


def frame(t=0):
    return dict(fixedClock=dict(started=True, startMs=1000, elapsedMs=t,
                                half=t>=DURATION//2, finished=t==DURATION),
                matchMs=t*3, done=t==DURATION, score=[0,0], stats=dict(shots=[0,0]),
                ball=[0,0,0], ballVelocity=[0,0,0], attackDirection=[1,-1],
                inPlay=True, setPiece=False,
                players=[player(1,0,0,0,owner=True), player(2,0,5,6),
                         player(3,1,30,0)],
                participation=[dict(team=0,databaseId=1,cardCode=0)],
                nativeContacts=[],nativeKeeperEvents=[],nativeFouls=[])


class HighlightDetectionTest(unittest.TestCase):
    def test_midfield_and_box(self):
        row=frame()
        self.assertEqual(classify(row),(0,'routine-possession'))
        row['ball']=[45,8,0]
        self.assertEqual(classify(row),(2,'controlled-box'))

    def test_other_attacking_direction(self):
        row=frame()
        row['attackDirection']=[-1,1]
        row['ball']=[-45,8,0]
        self.assertEqual(classify(row),(2,'controlled-box'))

    def test_forward_run_and_covered_target(self):
        row=frame()
        row['ball']=[18,0,0]
        row['players'][1]=player(2,0,32,6,vx=5)
        self.assertEqual(classify(row),(2,'potential-forward-run'))
        row['players'][2]=player(3,1,37,6)
        self.assertEqual(classify(row),(1,'attacking-build-up'))

    def test_attacking_restart(self):
        row=frame()
        row.update(setPiece=True,inPlay=False,ball=[44,0,0])
        self.assertEqual(classify(row),(2,'attacking-set-piece'))

    def test_loose_ball_in_box(self):
        row=frame()
        row['players'][0]['uniquePossession']=False
        row['ball']=[-42,0,0]
        self.assertEqual(classify(row),(2,'loose-ball-in-box'))

    def test_reject_invalid_direction(self):
        row=frame()
        row['attackDirection']=[1,1]
        with self.assertRaises(ValueError):
            classify(row)

    def test_full_timeline_and_event_context(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'trace.ndjson'
            with path.open('w') as out:
                for t in range(0,DURATION+1,200):
                    # One unobserved interval should be protected, not fast-forwarded.
                    if 60000<t<61000:
                        continue
                    row=frame(t)
                    if t>=30000:
                        row['stats']['shots']=[1,0]
                    if t>=30200:
                        row['score']=[1,0]
                    if t==30000:
                        row['nativeContacts']=[dict(kind='shot',timeMs=t+1000)]
                    if t==40000:
                        row['nativeKeeperEvents']=[dict(kind='parry',timeMs=t+1000,team=1,playerId=3)]
                    if t>=50000:
                        row['participation'][0]['cardCode']=1
                    out.write(json.dumps(row)+'\n')
            result=analyze(path)
        self.assertEqual(sum(result['levelDurationsMs'].values()),DURATION)
        self.assertEqual(result['eventCounts']['goal'],1)
        self.assertEqual(result['eventCounts']['shot'],1)
        self.assertEqual(result['eventCounts']['keeper-parry'],1)
        self.assertEqual(result['eventCounts']['card-change'],1)
        segments=result['segments']
        self.assertEqual(segments[0]['startMs'],0)
        self.assertEqual(segments[-1]['endMs'],DURATION)
        self.assertTrue(all(a['endMs']==b['startMs'] for a,b in zip(segments,segments[1:])))
        for t,reason in [(24000,'goal'),(30000,'shot-contact'),(39000,'keeper-parry'),(50000,'card-change'),(60500,'unobserved-gap')]:
            segment=next(s for s in segments if s['startMs']<=t<s['endMs'])
            self.assertEqual(segment['level'],'critical')
            self.assertIn(reason,segment['reasons'])


if __name__=='__main__':
    unittest.main()
