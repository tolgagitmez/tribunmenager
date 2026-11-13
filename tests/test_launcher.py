import functools
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen, Request

import start


class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(start.LocalHandler, directory=str(start.ROOT)))
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.http.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()

    def test_local_health_and_real_game_modules(self):
        self.assertEqual(json.load(urlopen(self.base + '/api/health'))['mode'], 'local')
        for file in ['index.html', 'tactics.html', 'match.html', 'football-sim.js', 'match-rules.js', 'referee-laws.js', 'pitch-laws.js', 'KURULUM.md']:
            with self.subTest(file=file):
                self.assertEqual(urlopen(self.base + '/' + file).status, 200)

    def test_local_api_explains_unavailable_full_features(self):
        for request in [self.base + '/api/transfers/state', Request(self.base + '/api/transfers/profile', data=b'{}', method='POST')]:
            with self.assertRaises(HTTPError) as caught:
                urlopen(request)
            self.assertEqual(caught.exception.code, 503)
            self.assertIn('error', json.load(caught.exception))

    def test_private_files_are_not_served(self):
        for path in ['/server.py', '/work/stage12/laws-unit.log', '/.git/config', '/tribun-dev.sqlite3']:
            with self.subTest(path=path), self.assertRaises(HTTPError) as caught:
                urlopen(self.base + path)
            self.assertEqual(caught.exception.code, 403)

    def test_full_mode_missing_data_has_an_actionable_error(self):
        if all((start.ROOT / p).exists() for p in ['data/transfer-rules.json', 'data/player-catalog.json', 'data/club-seed.json']):
            self.skipTest('Real full-mode data is installed in this checkout')
        result = subprocess.run([sys.executable, str(start.ROOT / 'start.py'), '--mode', 'full'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('--mode local', result.stderr)
        self.assertIn('KURULUM.md', result.stderr)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
