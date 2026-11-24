import functools
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import start
import server

class PrivacyTests(unittest.TestCase):
    def test_both_server_modes_block_encoded_and_head_private_paths(self):
        for handler in (functools.partial(start.LocalHandler,directory=str(start.ROOT)),server.Handler):
            http=ThreadingHTTPServer(("127.0.0.1",0),handler)
            t=threading.Thread(target=http.serve_forever,daemon=True)
            t.start()
            try:
                base="http://127.0.0.1:"+str(http.server_port)
                for path in ("/work/api-football/team-33.json","/%77ork/api-football/team-33.json","/work/","/%2egit/config","/server%2epy","/tribun-dev.sqlite3"):
                    for method in ("GET","HEAD"):
                        with self.subTest(handler=str(handler),path=path,method=method),self.assertRaises(HTTPError) as err:
                            urlopen(Request(base+path,method=method))
                        self.assertEqual(err.exception.code,403)
                with urlopen(base+"/catalog-friendly.html") as response:
                    self.assertEqual(response.status,200)
            finally:
                http.shutdown()
                http.server_close()
                t.join()
