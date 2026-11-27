import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import original_engine as engine
import start


class OriginalEngineTests(unittest.TestCase):
    def test_no_experiment_environment(self):
        env=engine.clean_env(dict(PATH='/bin',DISPLAY=':0',TRIBUN_NATIVE_FIXED_DURATION='1',
            GF_CAPTURE_TEST='1',GF_TEST='1',LD_PRELOAD='hook.so',SDL_AUDIODRIVER='dummy',
            LIBGL_ALWAYS_SOFTWARE='1',ALSOFT_DRIVERS='null'))
        self.assertEqual(env,dict(PATH='/bin',DISPLAY=':0'))

    def test_launcher_routes_original_without_web_server(self):
        with patch('original_engine.main',return_value=0) as launch, \
             patch('start.ThreadingHTTPServer') as server:
            self.assertEqual(start.main(['--mode','original']),0)
            launch.assert_called_once_with(build_only=False)
            server.assert_not_called()

    def test_build_only(self):
        with patch('original_engine.main',return_value=0) as launch:
            self.assertEqual(start.main(['--mode','original','--original-build-only']),0)
            launch.assert_called_once_with(build_only=True)

    def test_source_pin_and_clean_tree(self):
        with patch('original_engine.git_output',side_effect=[engine.REVISION,'']):
            engine.check_source(Path('source'),{})
        with patch('original_engine.git_output',return_value='wrong'):
            with self.assertRaises(RuntimeError):
                engine.check_source(Path('source'),{})
        with patch('original_engine.git_output',side_effect=[engine.REVISION,' M src/main.cpp']):
            with self.assertRaises(RuntimeError):
                engine.check_source(Path('source'),{})

    def test_config_is_byte_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            source,build=Path(tmp)/'source',Path(tmp)/'build'
            for p in (source/'data',build/'data'):
                p.mkdir(parents=True)
            for p in (source/'data/football.config',build/'football.config',build/'data/football.config'):
                p.write_bytes(b'original\n')
            engine.check_config(source,build)
            (build/'football.config').write_bytes(b'changed\n')
            with self.assertRaises(RuntimeError):
                engine.check_config(source,build)

    def test_runtime_manifest_detects_changed_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            build=Path(tmp)
            for name in engine.RUNTIME:
                p=build/name
                if name in ('gameplayfootball','football.config'):
                    p.write_text('original')
                else:
                    p.mkdir()
                    (p/'asset').write_text('original')
            original=engine.runtime_manifest(build)
            (build/'media/asset').write_text('changed')
            self.assertNotEqual(engine.runtime_manifest(build),original)

    def test_launch_no_arguments_and_private_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            build=Path(tmp)
            for name in engine.RUNTIME:
                p=build/name
                if name in ('gameplayfootball','football.config'):
                    p.write_text('original')
                else:
                    p.mkdir()
            def run(args,*,cwd,env):
                self.assertEqual(args,[str(cwd/'gameplayfootball')])
                self.assertNotEqual(cwd,build)
                self.assertEqual((cwd/'football.config').read_text(),'original')
                (cwd/'football.config').write_text('user setting')
                self.assertEqual(env,{'DISPLAY':':0'})
                return type('Result',(),{'returncode':0})()
            with patch('original_engine.subprocess.run',side_effect=run):
                self.assertEqual(engine.launch(build,{'DISPLAY':':0'}),0)
            self.assertEqual((build/'football.config').read_text(),'original')

    def test_launcher_restores_only_native_saves_and_keeps_last_clean_exit(self):
        from original_saves import current_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            build=base/'build'
            build.mkdir()
            store=base/'store'
            for name in engine.RUNTIME:
                p=build/name
                if name in ('gameplayfootball','football.config'):
                    p.write_text('original')
                else:
                    p.mkdir()
            calls=[]
            def run(args,*,cwd,env):
                self.assertEqual(args,[str(cwd/'gameplayfootball')])
                self.assertEqual((cwd/'football.config').read_text(),'original')
                self.assertEqual(env,{'DISPLAY':':0'})
                save=cwd/'saves/league/autosave.sqlite'
                if not calls:
                    save.parent.mkdir(parents=True)
                    save.write_bytes(b'first native save')
                else:
                    self.assertEqual(save.read_bytes(),b'first native save')
                    save.write_bytes(b'uncommitted changes')
                (cwd/'football.config').write_text('session-only settings')
                calls.append(cwd)
                return type('Result',(),{'returncode':0 if len(calls)==1 else 1})()
            with patch('original_engine.subprocess.run',side_effect=run):
                self.assertEqual(engine.launch(build,{'DISPLAY':':0'},save_root=store),0)
                previous=current_snapshot(store)
                self.assertEqual(engine.launch(build,{'DISPLAY':':0'},save_root=store),1)
                self.assertEqual(current_snapshot(store),previous)
            self.assertNotEqual(calls[0],calls[1])
            self.assertEqual((previous/'league/autosave.sqlite').read_bytes(),b'first native save')
            self.assertFalse((previous/'football.config').exists())
            self.assertEqual((build/'football.config').read_text(),'original')


if __name__=='__main__':
    unittest.main()
