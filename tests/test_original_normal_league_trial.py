import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from original_normal_league_trial import ORDER,trace_records,summarize,trial_config,regulation_timing

from original_native_reload_probe import (controller_event, pause_focus, press_until,
    controller_sides, tap_menu_arrow, pause_navigation_key, reload_navigation_key)

class NormalLeagueTrialTests(unittest.TestCase):
    def test_release_timing_includes_halftime_and_checks_final_score(self):
        from original_capture_probe import ACTIVE,HALF,FULL,DONE
        from original_normal_league_trial import release_timing_report
        events=[(1,ACTIVE,ACTIVE),(155,HALF,HALF),(158,ACTIVE,ACTIVE),
                (320,FULL,FULL+' Ajax 2 - 1 PSV'),(321,DONE,DONE)]
        history=dict(homeTeam='Ajax',homeGoals=2,awayGoals=1,awayTeam='PSV',nativeMatchClockMs=5400000)
        report=release_timing_report(events,history)
        self.assertEqual(report['activeToFulltimeMarkerSeconds'],319)
        self.assertEqual(report['observedHalvesSeconds'],[154,162])
        for mismatch in (dict(awayGoals=2),dict(nativeMatchClockMs=2700000)):
            with self.assertRaises(ValueError):
                release_timing_report(events,dict(history,**mismatch))

    def test_reload_never_activates_quick_match_or_another_save(self):
        for focus,key in [('page_2','Return'),('frame_intro_bg_frame','Return'),
                          ('button_main_start','Down'),
                          ('button_main_career','Up'),('button_main_league','Return'),
                          ('button_league_start_load','Return'),
                          ('filebrowser_league_start_load_Ajax','Return'),
                          ('dialog_league_load_save_frame_positive','Return')]:
            self.assertEqual(reload_navigation_key(focus,'Ajax'),key)
        for focus in ('dialog_league_load_save_frame_negative','filebrowser_league_start_load_PSV',None):
            with self.assertRaises(RuntimeError):
                reload_navigation_key(focus,'Ajax')

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

    def test_native_pause_navigation_uses_settled_focus(self):
        self.assertEqual(pause_navigation_key('button_resume'),'Up')
        self.assertEqual(pause_navigation_key('button_gameplan'),'Down')
        self.assertIsNone(pause_navigation_key('button_controllerselect'))
        with self.assertRaises(RuntimeError):
            pause_navigation_key('unverified')

    def test_native_controller_side_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace=Path(tmp)/'phases.jsonl'
            inputs=Path(str(trace)+'.inputs')
            self.assertIsNone(controller_sides(trace))
            inputs.write_text(''.join(json.dumps(x)+'\n' for x in [
                dict(kind='controller-sides',sides=[-1]),
                dict(kind='sdl-key',key=1073741903,pressed=True),
                dict(kind='controller-sides',sides=[0])])+'{"kind":')
            self.assertEqual(controller_sides(trace),[0])

    def test_menu_arrow_waits_for_its_own_release_even_if_neutral_is_seen(self):
        key=1073741903
        down=dict(kind='sdl-key',key=key,pressed=True)
        up=dict(kind='sdl-key',key=key,pressed=False)
        stale=[down,up]
        neutral=stale+[down,dict(kind='controller-sides',sides=[0])]
        wrong_key=neutral+[dict(kind='sdl-key',key=1073741904,pressed=False)]
        reads=[stale,stale,neutral,wrong_key,wrong_key+[up]]
        game=Mock()
        game.poll.return_value=None
        with patch('original_native_reload_probe.native_input_records',side_effect=reads) as read, \
             patch('original_native_reload_probe.subprocess.run') as run, \
             patch('original_native_reload_probe.time.sleep'):
            tap_menu_arrow('Right',Path('trace'),{},game)
            run.assert_called_once_with(['xdotool','keydown','Right','sleep','0.10','keyup','Right'],
                                        env={},check=True,timeout=5)
            self.assertEqual(read.call_count,len(reads))

    def test_failed_menu_pulse_releases_key(self):
        game=Mock()
        game.poll.return_value=None
        with patch('original_native_reload_probe.native_input_records',return_value=[]), \
             patch('original_native_reload_probe.subprocess.run',
                   side_effect=[subprocess.TimeoutExpired('xdotool',5),None]) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                tap_menu_arrow('Left',Path('trace'),{},game)
            self.assertEqual(run.call_args.args[0],['xdotool','keyup','Left'])

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
        raw=b'"match_duration_minutes" "25"\n"match_difficulty" "0.5"\n"context_x" "1280"\n'
        result=trial_config(raw)
        self.assertEqual(result.count(b'"match_duration_minutes"'),1)
        self.assertIn(b'"match_duration_minutes" "5.000000"',result)
        self.assertIn(b'"menu_smoke_match_time_scale" "1.0"',result)
        self.assertIn(b'"match_difficulty" "0.5"',result)
        self.assertEqual(result.count(b'"context_x"'),1)
        self.assertIn(b'"context_x" "640"',result)
        self.assertIn(b'"context_y" "360"',result)
        self.assertNotIn(b'"25"',result)

    def test_native_clock_decomposition_rejects_invalid_ticks(self):
        first=dict(durationMinutes=5,timeScale=1,actualTimeMs=1000,monotonic=10)
        half=dict(clockMs=2700000,actualTimeMs=161000,monotonic=180)
        end=dict(clockMs=5400000,actualTimeMs=321000,monotonic=350)
        report=regulation_timing(first,half,end)
        self.assertEqual(report['total']['clockAdvancingSimulationSeconds'],300)
        self.assertEqual(report['total']['nonAdvancingSimulationSeconds'],20)
        self.assertEqual(report['total']['wallMinusSimulationSeconds'],20)
        for bad in (None,160999,160000.0,1000,310000):
            with self.subTest(actualTimeMs=bad):
                with self.assertRaises(ValueError):
                    regulation_timing(first,dict(half,actualTimeMs=bad),end)
        # A signed residual is evidence, not automatically a performance failure.
        self.assertEqual(regulation_timing(first,half,dict(end,monotonic=325))
                         ['total']['wallMinusSimulationSeconds'],-5)

    def test_phase_and_result_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace.jsonl'
            rows=[dict(kind=k,monotonic=t) for k,t in zip(ORDER,(0,10,175,178,180,345,348))]
            rows[1].update(teamIds=[1,7],durationMinutes=5,timeScale=1,actualTimeMs=0)
            rows[2].update(clockMs=2880000,actualTimeMs=165000)
            rows[5].update(clockMs=5640000,actualTimeMs=330000)
            rows[6].update(teamIds=[1,7],clockMs=5400000,score=[1,0])
            def write():
                path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            write()
            fixture=dict(homeTeamId=1,awayTeamId=7)
            history=dict(nativeMatchClockMs=5400000,homeGoals=1,awayGoals=0)
            report=summarize(path,fixture,history)
            self.assertEqual(report['observedRegulationPhaseSpanSeconds'],335)
            resumed=dict(kind='resumed',humanCounts=[0,0],monotonic=35)
            observed=summarize(path,fixture,history,resumed)['regulationTiming']
            self.assertEqual(observed['firstHalfStartToCpuResumeSeconds'],25)
            self.assertEqual(observed['cpuResumeToRegulationEndSeconds'],310)
            self.assertEqual(observed['cpuResumeToFulltimeScreenSeconds'],313)
            for bad in (None,True,float('nan'),9,176):
                with self.assertRaises(ValueError):
                    summarize(path,fixture,history,dict(resumed,monotonic=bad))
            timing=report['regulationTiming']['total']
            self.assertEqual(timing['wallSeconds'],335)
            self.assertEqual(timing['unpausedSimulationSeconds'],330)
            self.assertEqual(timing['clockAdvancingSimulationSeconds'],323.333)
            self.assertEqual(timing['nonAdvancingSimulationSeconds'],6.667)
            self.assertEqual(timing['wallMinusSimulationSeconds'],5)
            self.assertEqual(timing['addedTimeSimulationSeconds'],23.333)
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
