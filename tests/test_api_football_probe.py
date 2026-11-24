import contextlib
import io
import unittest
from tools.api_football_probe import probe, ProbeError

class TestApiFootballProbe(unittest.TestCase):
    def run_probe(self, quota=100, fail_season=False):
        calls = []
        def transport(key, endpoint, params):
            calls.append(endpoint)
            self.assertEqual(key, "fake-key")
            if endpoint == "status":
                return {"subscription":{"active":True},"requests":{"current":0,"limit_day":quota},"account":{"email":"private@example.test"}}, quota
            if endpoint == "players/squads":
                return [{"team":{"id":33},"players":[{"id":1,"name":"private player"}]}], quota-1
            if fail_season:
                raise ProbeError("plan/season restriction")
            return [{"team":{"id":33}}], quota-2
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            probe("fake-key", transport)
        return calls, out.getvalue()

    def test_three_calls_and_no_raw_data(self):
        calls, out = self.run_probe()
        self.assertEqual(calls, ["status","players/squads","teams"])
        self.assertIn("1 player records", out)
        self.assertNotIn("private", out)
        self.assertNotIn("fake-key", out)

    def test_season_limit_is_separate(self):
        calls, out = self.run_probe(fail_season=True)
        self.assertEqual(len(calls), 3)
        self.assertIn("Current squad access remains confirmed", out)

    def test_daily_budget(self):
        calls, out = self.run_probe(quota=1)
        self.assertEqual(calls, ["status","players/squads"])
        self.assertIn("request budget exhausted", out)

    def test_missing_key_and_invalid_status(self):
        with self.assertRaises(ProbeError):
            probe("", lambda *_: self.fail("network call"))
        with self.assertRaises(ProbeError):
            probe("fake-key", lambda *_: ({}, None))

if __name__ == "__main__":
    unittest.main()
