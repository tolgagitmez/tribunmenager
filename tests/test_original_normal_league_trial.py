import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from original_normal_league_trial import ORDER,trace_records,summarize,trial_config

from original_native_reload_probe import controller_event, pause_focus, press_until

class NormalLeagueTrialTests(unittest.TestCase):
    def test_verified_native_input_releases_key_on_success_and_failure(self):
        game=Mock()
        game.poll.return_value=None
        env={}
        evidence={'kind':'pause-menu'}
        with patch('original_native_reload_probe.subprocess.run') as run, patch('original_native_reload_probe.time.sleep'):
            self.assertEqual(press_until('Escape',Mock(side_effect=[None,evidence]),env,game),evidence)
            self.assertEqual([call.args[0][1] for call in run.call_args_list],['keydown','keyup'])
            run.reset_mock()
            with self.assertRaisesRegex(ValueError,'bad evidence'):
                press_until('Escape',Mock(side_effect=[None,ValueError('bad evidence')]),env,game)
            self.assertEqual([call.args[0][1] for call in run.call_args_list],['keydown','keyup'])
            run.reset_mock()
            self.assertEqual(press_until('Escape',lambda:evidence,env,game),evidence)
            run.assert_not_called()

    def test_pause_focus_uses_latest_complete_native_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace=Path(tmp)/'phases.jsonl'
            inputs=Path(str(trace)+'.inputs')
            self.assertIsNone(pause_focus(trace))
            inputs.write_text(''.join(json.dumps(x)+'\n' for x in [
                dict(kind='pause-focus',name='button_resume'),
                dict(kind='sdl-escape',pressed=True),
                dict(kind='pause-focus',name='button_controllerselect')])+'{"kind":')
            self.assertEqual(pause_focus(trace),'button_controllerselect')

    def test_native_controller_observation_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace=Path(tmp)/'phases.jsonl'
            controls=Path(str(trace)+'.controls')
            self.assertIsNone(controller_event(trace,'controller-menu'))
            ready=dict(kind='game-ready',humanCounts=[1,0],actualTimeMs=1000)
            pause=dict(kind='pause-menu',humanCounts=[1,0])
            menu=dict(kind='controller-menu',humanCounts=[1,0])
            cpu=dict(kind='cpu-control',humanCounts=[0,0])
            resumed=dict(kind='resumed',humanCounts=[0,0],clockMs=0)
            rows=[ready,pause,menu,cpu,resumed]
            prefix=''.join(json.dumps(row)+'\n' for row in rows[:3])
            controls.write_text(prefix+json.dumps(cpu))
            self.assertEqual(controller_event(trace,'controller-menu'),menu)
            self.assertIsNone(controller_event(trace,'cpu-control'))
            controls.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            self.assertEqual(controller_event(trace,'game-ready'),ready)
            self.assertEqual(controller_event(trace,'pause-menu'),pause)
            self.assertEqual(controller_event(trace,'cpu-control'),cpu)
            self.assertEqual(controller_event(trace,'resumed'),resumed)
            controls.write_text(json.dumps(cpu)+'\n')
            with self.assertRaises(ValueError):
                controller_event(trace,'cpu-control')
            controls.write_text(json.dumps(ready)+'\n'+json.dumps(menu)+'\n')
            with self.assertRaises(ValueError):
                controller_event(trace,'controller-menu')
            controls.write_text(json.dumps(dict(kind='error',message='debugger failure'))+'\n')
            with self.assertRaises(RuntimeError):
                controller_event(trace,'cpu-control')

    def test_supported_clock_configuration(self):
        raw=b'"match_duration_minutes" "25"\n"match_difficulty" "0.5"\n'
        result=trial_config(raw)
        self.assertEqual(result.count(b'"match_duration_minutes"'),1)
        self.assertIn(b'"match_duration_minutes" "5.000000"',result)
        self.assertIn(b'"menu_smoke_match_time_scale" "1.0"',result)
        self.assertIn(b'"match_difficulty" "0.5"',result)
        self.assertNotIn(b'"25"',result)

    def test_phase_and_result_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace.jsonl'
            rows=[dict(kind=k,monotonic=t) for k,t in zip(ORDER,(0,10,175,178,180,345,348))]
            rows[1].update(teamIds=[1,7],durationMinutes=5,timeScale=1)
            rows[2]['clockMs']=2880000
            rows[5]['clockMs']=5640000
            rows[6].update(teamIds=[1,7],clockMs=5400000,score=[1,0])
            def write():
                path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            write()
            fixture=dict(homeTeamId=1,awayTeamId=7)
            history=dict(nativeMatchClockMs=5400000,homeGoals=1,awayGoals=0)
            report=summarize(path,fixture,history)
            self.assertEqual(report['observedRegulationPhaseSpanSeconds'],335)
            self.assertFalse(report['realTime300SecondMatchVerified'])
            self.assertFalse(report['productionImportAllowed'])
            with self.assertRaises(ValueError):
                summarize(path,fixture,dict(history,awayGoals=2))
            rows[1]['timeScale']=6
            write()
            with self.assertRaises(ValueError):
                summarize(path,fixture,history)
            rows[1]['timeScale']=1
            rows[4]['kind']='fulltime'
            write()
            with self.assertRaises(ValueError):
                trace_records(path)
