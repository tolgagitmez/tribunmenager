import tempfile
from pathlib import Path
import unittest
import native_av_gateway as g
class LeagueKeyTest(unittest.TestCase):
    def test_key_only_from_private_attempt(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/('a'*32)/'run';p.mkdir(parents=True)
            with self.assertRaises(g.GatewayError):g.gateway_secret(t,'a'*32)
            f=p/'league-gateway.key';f.write_text('x'*43);f.chmod(0o600)
            self.assertEqual(g.gateway_secret(t,'a'*32),'x'*43)
            f.chmod(0o644)
            with self.assertRaises(g.GatewayError):g.gateway_secret(t,'a'*32)
            f.chmod(0o600);f.write_text('invalid')
            with self.assertRaises(g.GatewayError):g.gateway_secret(t,'a'*32)
