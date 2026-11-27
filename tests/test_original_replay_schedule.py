import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from original_replay_schedule import fixture_identity,schedule_replay,schedule_status,open_scheduled_replay

class ReplayScheduleTests(unittest.TestCase):
    def test_schedule_advances_without_viewers_and_survives_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            fixture=dict(league='TEST',round=1,home=0,away=1,kickoff=1000)
            key,_,_=fixture_identity(fixture)
            review=dict(operatorReviewed=True,fixtureKey=key,kickoff=1000,replaySha256='a'*64)
            self.assertTrue(schedule_replay(root,fixture,review)['created'])
            self.assertFalse(schedule_replay(root,fixture,review)['created'])
            for now,phase,pos in ((999,'waiting',0),(1000,'playing',0),(1125,'playing',125),
                                  (1300,'finished',300),(1600,'finished',300)):
                state=schedule_status(root,key,now)
                self.assertEqual((state['phase'],state['positionSeconds']),(phase,pos))
                self.assertFalse(state['scoreWritten'])
                self.assertFalse(state['nativeKickoffVerified'])
            with patch('original_replay_schedule.ReplayServer') as server:
                open_scheduled_replay(root,key,'match.mp4',8766)
                server.assert_called_once_with('match.mp4','a'*64,port=8766,scheduled_epoch=1000,fixture_key=key)

    def test_schedule_cannot_reset_clock_or_swap_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture=dict(league='TEST',round=1,home=0,away=1,kickoff=1000)
            key,_,_=fixture_identity(fixture)
            review=dict(operatorReviewed=True,fixtureKey=key,kickoff=1000,replaySha256='a'*64)
            with self.assertRaises(ValueError):
                schedule_replay(tmp,fixture,{**review,'operatorReviewed':False})
            schedule_replay(tmp,fixture,review)
            with self.assertRaises(ValueError):
                schedule_replay(tmp,{**fixture,'kickoff':2000},{**review,'kickoff':2000})
            with self.assertRaises(ValueError):
                schedule_replay(tmp,fixture,{**review,'replaySha256':'b'*64})
            alternate={**fixture,'round':2}
            other,_,_=fixture_identity(alternate)
            with self.assertRaises(ValueError):
                schedule_replay(tmp,alternate,{**review,'fixtureKey':other})
            self.assertEqual(schedule_status(tmp,key,1100)['positionSeconds'],100)

if __name__=='__main__':
    unittest.main()
