import json
from pathlib import Path
import tempfile
import unittest
from original_normal_league_trial import ORDER,trace_records,summarize,trial_config

from original_native_reload_probe import controller_event

class NormalLeagueTrialTests(unittest.TestCase):
    def test_native_controller_observation_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace=Path(tmp)/'phases.jsonl'
            controls=Path(str(trace)+'.controls')
            self.assertIsNone(controller_event(trace,'controller-menu'))
            menu=dict(kind='controller-menu',humanCounts=[1,0])
            cpu=dict(kind='cpu-control',humanCounts=[0,0])
            controls.write_text(json.dumps(menu)+'\n'+json.dumps(cpu))
            self.assertEqual(controller_event(trace,'controller-menu'),menu)
            self.assertIsNone(controller_event(trace,'cpu-control'))
            controls.write_text(json.dumps(menu)+'\n'+json.dumps(cpu)+'\n')
            self.assertEqual(controller_event(trace,'cpu-control'),cpu)
            controls.write_text(json.dumps(cpu)+'\n')
            with self.assertRaises(ValueError):
                controller_event(trace,'cpu-control')
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
