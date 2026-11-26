import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
instrument=load("instrument")
bench=load("null-renderer-benchmark")
class NullRendererTest(unittest.TestCase):
    def test_backend_is_opt_in(self):
        source = '''#include "graphics_system.hpp"
  if (config.Get("graphics3d_renderer", "opengl") == "opengl")
    renderer3DTask = new OpenGLRenderer3D();'''
        patched=instrument.select_null_renderer(source)
        self.assertIn("new OpenGLRenderer3D()",patched)
        self.assertIn("new TribunNullRenderer3D()",patched)
        self.assertIn("TRIBUN_NATIVE_NO_UPLOAD",patched)
        self.assertIn("static_assert",instrument.NULL_RENDERER_HEADER)
        self.assertNotIn("SDL_GL_CreateContext",instrument.NULL_RENDERER_HEADER)
        self.assertNotIn("SDL_CreateWindow",instrument.NULL_RENDERER_HEADER)
    def test_requires_isolated_mode(self):
        with self.assertRaises(ValueError):
            bench.fixed.timing.run("unused","unused","unused",("test","1.0","0"),null_renderer=True)
    def test_comparison(self):
        def row(mode,cpu):
            return dict(noDraw=True,noUpload=True,nullRenderer=mode,configuredRenderIntervalMs=100,softwareRenderThreads=2,
                        exactNativeDuration=True,nativeElapsedMs=300000,attackProfile="short-match",
                        resources=dict(userSeconds=cpu,systemSeconds=2,maxRssKiB=1000),
                        observedWallMs=300100,maxObservedGapMs=150,score=[0,0],shots=[1,1],
                        onTarget=[0,0],controlledBoxCrossings=[2,2])
        a,b=row(False,100),row(True,60)
        result=bench.evaluate({"opengl":a,"null":b})
        self.assertEqual(result["cpuSecondsDelta"],-40)
        self.assertFalse(result["productionEnabled"])
        b["nullRenderer"]=False
        with self.assertRaises(ValueError):bench.evaluate({"opengl":a,"null":b})
