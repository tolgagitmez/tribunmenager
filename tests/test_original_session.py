import functools
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import original_session as session
import start


class BridgeTests(unittest.TestCase):
    def test_origin_and_public_binding(self):
        self.assertTrue(session.allowed('127.0.0.1',('127.0.0.1',8000),
            'localhost:8000','http://localhost:8000'))
        for client,bind,host,origin in [
            ('10.0.0.2','127.0.0.1','localhost:8000',None),
            ('127.0.0.1','0.0.0.0','localhost:8000',None),
            ('127.0.0.1','127.0.0.1','attacker.example:8000',None),
            ('127.0.0.1','127.0.0.1','localhost:8000','https://attacker.example')]:
            self.assertFalse(session.allowed(client,(bind,8000),host,origin))

    def test_no_uninstalled_launch_and_no_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch('original_engine.cache_root',return_value=Path(tmp)), \
             patch('original_session.sys.platform','linux'), \
             patch('original_session.subprocess.Popen') as popen:
            bridge=session.OriginalSession()
            self.assertEqual(bridge.launch()[0],409)
            popen.assert_not_called()
            work=Path(tmp)/session.original_engine.REVISION
            work.mkdir()
            (work/'pristine-manifest.json').write_text('{}')
            popen.return_value.poll.return_value=None
            self.assertEqual(bridge.launch()[0],202)
            self.assertEqual(bridge.launch()[0],409)
            popen.assert_called_once()
            self.assertEqual(popen.call_args.args[0][-3:],
                             ['--mode','original','--original-installed-only'])
            self.assertFalse(bridge.status()['managerBridge'])

    def test_http_same_origin_launch_and_cross_origin_rejection(self):
        with ThreadingHTTPServer(('127.0.0.1',0),
                functools.partial(start.LocalHandler,directory=str(start.ROOT))) as http:
            http.original_session=session.OriginalSession()
            thread=threading.Thread(target=http.serve_forever,daemon=True)
            thread.start()
            base=f'http://127.0.0.1:{http.server_port}'
            try:
                with patch.object(http.original_session,'launch',return_value=(202,{'running':True})) as run:
                    for headers in ({},{'Origin':'https://example.org','X-Tribun-Original':'launch'},
                                    {'Origin':base,'X-Tribun-Original':'launch','Host':'attacker.example'}):
                        with self.assertRaises(HTTPError) as exc:
                            urlopen(Request(base+'/api/original/launch',headers=headers,method='POST'))
                        self.assertEqual(exc.exception.code,403)
                    run.assert_not_called()
                    req=Request(base+'/api/original/launch',headers={'Origin':base,
                        'X-Tribun-Original':'launch'},method='POST')
                    with urlopen(req) as res:
                        self.assertEqual(res.status,202)
                        self.assertTrue(json.load(res)['running'])
                    run.assert_called_once()
                with urlopen(base+'/api/original/status') as res:
                    self.assertFalse(json.load(res)['managerBridge'])
            finally:
                http.shutdown()
                thread.join()

    def test_installed_only_routes_without_build(self):
        with patch('original_engine.main',return_value=0) as launch:
            self.assertEqual(start.main(['--mode','original','--original-installed-only']),0)
            launch.assert_called_once_with(installed_only=True)

    def test_report_freshness_matches_snapshot_and_legacy_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            cache=base/'cache'
            cache.mkdir()
            root=base/'store'
            root.mkdir()
            old='snapshot-'+'a'*32
            new='snapshot-'+'b'*32
            for name in (old,new):
                (root/name).mkdir()
            (root/'current').write_text(old)
            report=cache/'last-native-results.json'
            data=dict(schema=1,revision=session.original_engine.REVISION,
                      exitCode=0,saves=[],snapshotId=old,createdAtUtc='2026-11-27T12:00:00+00:00')
            report.write_text(json.dumps(data))
            with patch('original_engine.cache_root',return_value=cache), \
                 patch('original_engine.save_root_path',return_value=root), \
                 patch('original_session.sys.platform','linux'):
                bridge=session.OriginalSession()
                response=bridge.results()
                self.assertEqual(response['snapshotConsistency'],'matches-saved-snapshot')
                self.assertNotIn('snapshotId',response)
                self.assertEqual(json.loads(report.read_text()),data)
                (root/'current').write_text(new)
                self.assertEqual(bridge.results()['snapshotConsistency'],'different-saved-snapshot')
                (root/'current').write_text('../invalid')
                self.assertEqual(bridge.results()['snapshotConsistency'],'unknown')
                data.pop('snapshotId')
                report.write_text(json.dumps(data))
                self.assertEqual(bridge.results()['snapshotConsistency'],'unknown')


if __name__=='__main__':
    unittest.main()
