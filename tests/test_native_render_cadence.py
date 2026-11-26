import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m
profile=load("render-profile")
bench=load("render-benchmark")
class RenderCadenceTest(unittest.TestCase):
    def test_only_graphics_property_changed(self):
        source='"match_duration_minutes" "5.0"\n"menu_smoke_match_time_scale" "1.0"\n'
        self.assertEqual(profile.configure(source,100),source+'"graphics3d_frametime_ms" "100"\n')
        existing=source+'"graphics3d_frametime_ms" "0"\n"quick_start" "false"\n'
        self.assertEqual(profile.configure(existing,100),existing.replace('"graphics3d_frametime_ms" "0"','"graphics3d_frametime_ms" "100"'))
        with self.assertRaises(ValueError):profile.configure(existing+'"graphics3d_frametime_ms" "0"\n',100)
        with self.assertRaises(ValueError):profile.configure(source,0)
        last=source+'\n"graphics3d_frametime_ms" "0"\n\n'
        self.assertEqual(profile.configure(last,100),last.replace('"graphics3d_frametime_ms" "0"','"graphics3d_frametime_ms" "100"'))

    def test_reports_never_activate_production(self):
        def row(interval,cpu):
            return dict(configuredRenderIntervalMs=interval,softwareRenderThreads=2,
                        exactNativeDuration=True,nativeElapsedMs=300000,
                        resources=dict(userSeconds=cpu,systemSeconds=2,maxRssKiB=1000),
                        observedWallMs=300100,maxObservedGapMs=150)
        r=bench.evaluate(dict(control=row(0,100),capped=row(100,50)))
        self.assertEqual(r["cpuSecondsDelta"],-50)
        self.assertFalse(r["productionEnabled"])
        with self.assertRaises(ValueError):bench.evaluate(dict(control=row(0,100),capped=row(0,50)))
