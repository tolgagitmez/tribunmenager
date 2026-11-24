import copy
import json
import tempfile
import unittest
from pathlib import Path
from economy import TransferService, EconomyError, game_market_value, validate_catalog_player
from tools.import_api_football_market import import_market

def snapshot(team=33):
    return {"schema":1,"source":"api-football","teamId":team,"teamUid":f"api-football:team:{team}",
            "name":"Fictional club","fetchedAt":"2026-11-24T00:00:00Z",
            "players":[{"providerId":team*100+i,"uid":f"api-football:player:{team*100+i}","name":f"Fictional {i}",
                        "age":19+i%10,"pos":"GK" if i==0 else "DEF" if i<5 else "MID" if i<9 else "ATT"} for i in range(12)]}

class MarketTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service=TransferService(Path(self.tmp.name)/"game.sqlite3",clock=lambda:1000000)

    def test_actual_buy_and_refresh_preserves_owned_identity_and_wallet(self):
        s=snapshot()
        self.assertEqual(import_market(self.service,[s]),{"imported":12,"skippedUnknownAge":0})
        initial=self.service.create_profile()
        self.assertEqual(len(initial["players"]),18)
        self.assertEqual(initial["wallet"],{"cash":25000000,"tokens":120})
        offer=next(l for l in initial["market"] if l["price"]<=initial["wallet"]["cash"])
        bought=self.service.command(initial["token"],"buy-1","buy",{"listingId":offer["id"],"expectedCash":offer["price"]})
        p=bought["players"][-1]
        self.assertEqual(p["uid"],offer["player"]["uid"])
        self.assertEqual(p["preferredFoot"],"unknown")
        self.assertIsNone(p["subposition"])
        self.assertIsNone(p["nationality"])
        self.assertIsNone(p["realForm"])
        self.assertEqual(p["valueSource"],"game-credit-v1")
        self.assertEqual(bought["wallet"]["cash"],25000000-offer["price"])
        duplicate=self.service.command(initial["token"],"buy-1","buy",{"listingId":offer["id"],"expectedCash":offer["price"]})
        self.assertEqual(duplicate["wallet"],bought["wallet"])
        self.assertEqual(len(duplicate["players"]),19)
        refresh=copy.deepcopy(s)
        refresh["fetchedAt"]="2026-11-25T00:00:00Z"
        refresh["name"]="New fictional club"
        refresh["players"][0]["name"]="Renamed"
        import_market(self.service,[refresh],"synthetic-varied")
        after=self.service.status(initial["token"])
        self.assertEqual(after["players"][-1],p)
        self.assertEqual(after["wallet"],bought["wallet"])
        trained=self.service.command(initial["token"],"train-1","train",{"playerId":p["id"],"focus":"passing"})
        trained=self.service.command(initial["token"],"train-2","train",{"playerId":p["id"],"focus":"passing"})
        q=trained["players"][-1]
        self.assertEqual(q["rating"],min(p["rating"]+1,p["potential"]))
        self.assertEqual(q["value"],game_market_value(q["rating"],q["age"],q["potential"]))
    def test_batch_rejects_conflicting_uid_and_stale_refresh(self):
        s=snapshot()
        import_market(self.service,[s],"synthetic-varied")
        with self.service.connect() as c: before=self.service._catalog(c)
        with self.assertRaises(EconomyError): import_market(self.service,[s,s])
        s["fetchedAt"]="2026-11-23T00:00:00Z"
        with self.assertRaises(EconomyError): import_market(self.service,[s])
        with self.service.connect() as c: self.assertEqual(self.service._catalog(c),before)
    def test_unknown_age_skipped_and_value_recomputed_not_trusted(self):
        s=snapshot()
        s["players"][0]["age"]=None
        self.assertEqual(import_market(self.service,[s]),{"imported":11,"skippedUnknownAge":1})
        with self.service.connect() as c: p=self.service._catalog(c)[0]
        p["value"]=2000000000
        p["potential"]=99
        fresh=validate_catalog_player(p)
        self.assertLess(fresh["value"],2000000000)
        self.assertLess(fresh["potential"],99)
        self.assertEqual(fresh["ratingProvenance"]["observed"],False)
    def test_age_and_rating_change_simulated_value(self):
        self.assertGreater(game_market_value(85,20,95),game_market_value(85,33,85))
        self.assertGreater(game_market_value(90,25,94),game_market_value(80,25,84))
