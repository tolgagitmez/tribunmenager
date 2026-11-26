import argparse
import functools
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request,build_opener,HTTPRedirectHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import start
sys.path.insert(0,str(start.ROOT/'integrations/league-soccer'))
from native_private_beta import AlphaHandler
from native_alpha import find_runtime,expected_manifest

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*a,**kw):return None

class EntrypointTest(unittest.TestCase):
    def args(self):
        return argparse.Namespace(host='127.0.0.1',port=8765,native_delay=120,native_install_deps=False,
            native_runtime=None,native_session_root=None,native_prepare_only=False,native_update=False)
    def test_native_linux_and_windows(self):
        a=self.args()
        c=start.native_command(a,'linux')
        self.assertIn('native_alpha.py',c[1]);self.assertIn('--private-diagnostic',c)
        with patch('start.shutil.which',return_value='wsl.exe'):
            c=start.native_command(a,'win32')
            self.assertEqual(c[:7],['wsl.exe','--distribution','Ubuntu','--cd','~','--exec','python3'])
            self.assertIn('stage170',c[7])
            self.assertNotIn(start.WSL_BOOTSTRAP,c)
        with patch('start.subprocess.run') as run:
            run.return_value.returncode=0
            self.assertEqual(start.wsl_prepare(a),0)
            self.assertEqual(run.call_args.args[0][-4:],['bash','-s','--','keep'])
            self.assertIn(start.NATIVE_BRANCH.encode(),run.call_args.kwargs['input'])
            self.assertIn(b'git clone',run.call_args.kwargs['input'])
        with patch('start.shutil.which',return_value=None):
            with self.assertRaises(ValueError):start.native_command(a,'win32')
        a.host='0.0.0.0'
        with self.assertRaises(ValueError):start.native_command(a,'linux')
    def test_default_never_falls_back(self):
        with patch('start.native_command',side_effect=ValueError('not ready')),patch('start.ThreadingHTTPServer') as old:
            self.assertEqual(start.main([]),2);old.assert_not_called()
    def test_matching_runtime_reuse(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);session=base/'alpha-a';session.mkdir(mode=0o700)
            runtime=session/'runtime';runtime.mkdir()
            (runtime/'gameplayfootball').write_text('fixture')
            (runtime/'gameplayfootball').chmod(0o700)
            (runtime/'native-match.config').write_text('fixture')
            (runtime/'tribun-runtime.json').write_text(json.dumps(expected_manifest()))
            self.assertEqual(find_runtime(base),runtime.resolve())
            (runtime/'tribun-runtime.json').write_text('{}')
            self.assertIsNone(find_runtime(base))
    def test_old_match_routes_redirect(self):
        with ThreadingHTTPServer(('127.0.0.1',0),AlphaHandler) as http:
            thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            try:
                base='http://127.0.0.1:'+str(http.server_port);opener=build_opener(NoRedirect)
                for route,target in [('/','/native-beta-login.html'),('/match.html?live=0','/league.html'),('/native-match.html','/league.html'),('/%6datch.html','/league.html')]:
                    with self.assertRaises(HTTPError) as e:opener.open(base+route)
                    self.assertEqual(e.exception.code,303);self.assertEqual(e.exception.headers['Location'],target)
                with self.assertRaises(HTTPError) as e:opener.open(Request(base+'/api/league/create',data=b'{}'))
                self.assertEqual(e.exception.code,403)
            finally:http.shutdown();thread.join(timeout=5)
