import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from tools.api_football_catalog import Catalog, normalize_squad, sync, ProbeError

NOW = datetime(2026, 11, 24, tzinfo=timezone.utc)
def payload(team, count=12):
    return [{"team":{"id":team,"name":f"Test {team}","logo":"not saved"},
             "players":[{"id":team*100+i,"name":f"Fictional {i}","age":22,"number":i+1,
                         "position":"Goalkeeper" if i==0 else "Defender" if i<5 else "Midfielder" if i<9 else "Attacker","photo":"not saved"} for i in range(count)]}]
def provider(remaining=100, bad_team=None):
    calls=[]
    def get(key, endpoint, params):
        calls.append((endpoint,params))
        if endpoint=="status":
            return {"subscription":{"active":True},"requests":{"current":100-remaining,"limit_day":100}}, remaining
        if params["team"]==bad_team:
            return [], remaining-len(calls)
        return payload(params["team"]), remaining-len(calls)
    return get,calls

class CatalogTest(unittest.TestCase):
    def test_identity_and_no_fabricated_skills_or_images(self):
        s=normalize_squad(33,payload(33),NOW.isoformat())
        self.assertEqual(s["players"][0]["uid"],"api-football:player:3300")
        self.assertIsNone(s["players"][0]["rating"])
        self.assertEqual(s["players"][0]["preferredFoot"],"unknown")
        self.assertNotIn("photo",str(s))
        self.assertNotIn("logo",str(s))
    def test_quota_and_dry_run(self):
        get,calls=provider()
        waits=[]
        r=sync("fake",[33,34],transport=get,wait=waits.append,now=NOW)
        self.assertEqual(r["players"],24)
        self.assertFalse(r["stored"])
        self.assertEqual(len(calls),3)
        self.assertEqual(waits,[7,7])
        get,calls=provider(remaining=6)
        with self.assertRaises(ProbeError):
            sync("fake",[33,34],transport=get,wait=lambda _:None,now=NOW)
        self.assertEqual(len(calls),1)
    def test_failed_batch_retains_prior_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            cat=Catalog(Path(d)/"catalog.sqlite3")
            get,_=provider()
            sync("fake",[33],catalog=cat,transport=get,wait=lambda _:None,now=NOW)
            before=cat.read(33)
            get,_=provider(bad_team=34)
            with self.assertRaises(ProbeError):
                sync("fake",[33,34],catalog=cat,transport=get,wait=lambda _:None,now=NOW+timedelta(days=1))
            self.assertEqual(cat.read(33),before)
            self.assertIsNone(cat.read(34))
            get,_=provider()
            sync("fake",[33,34],catalog=cat,transport=get,wait=lambda _:None,now=NOW+timedelta(days=1))
            self.assertNotEqual(cat.read(33),before)
            self.assertIsNotNone(cat.read(34))
            cat.export(33,Path(d)/"team.json")
            self.assertTrue((Path(d)/"team.json").exists())
            with self.assertRaises(ProbeError):
                sync("fake",[33],catalog=cat,transport=get,wait=lambda _:None,now=NOW)
    def test_invalid_players_rejected(self):
        p=payload(33)
        p[0]["players"][1]["id"]=p[0]["players"][0]["id"]
        with self.assertRaises(ProbeError): normalize_squad(33,p,NOW.isoformat())
        with self.assertRaises(ProbeError): normalize_squad(33,payload(34),NOW.isoformat())
        with self.assertRaises(ProbeError): normalize_squad(33,payload(33,10),NOW.isoformat())
