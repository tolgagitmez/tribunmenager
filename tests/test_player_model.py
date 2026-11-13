"""Player identity survives catalogue, signing and persisted squad boundaries."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import economy


ROOT = Path(__file__).resolve().parents[1]


def catalog_player(**changes):
    player = {"providerId": "test", "externalId": "striker", "name": "Örnek Oyuncu",
              "club": "Örnek SK", "league": "Test Ligi", "updatedAt": "2026-11-13T00:00:00Z",
              "pos": "ATT", "subposition": "ST", "nationality": "TR", "age": 24,
              "rating": 80, "value": 1000000}
    player.update(changes)
    return player


class PlayerIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = economy.TransferService(Path(self.temp.name) / "test.sqlite3", rules={"maxSquad": 30})

    def test_catalogue_signing_and_storage_preserve_explicit_identity(self):
        attributes = {key: 42 + index for index, key in enumerate(economy.PLAYER_ATTRIBUTES)}
        raw = catalog_player(preferredFoot="left", archetype="targetForward", positions=["ST", "CF"], **attributes)
        self.service.import_catalog({"version": 1, "players": [raw]})
        with self.service.connect() as connection:
            stored = self.service._catalog(connection)[0]
            state = {"profileId": "identity", "players": [], "wallet": {"cash": 0, "tokens": 0},
                     "history": [], "market": []}
            self.service._sign(connection, state, stored, 0, 0, "free-fixture", 0, "test-sign")
            self.service._save(connection, state, auth=hashlib.sha256(b"token").hexdigest())
            loaded = self.service._load(connection, "token")["players"][0]
        for key, value in attributes.items():
            self.assertEqual(loaded[key], value, key)
        self.assertEqual(loaded["preferredFoot"], "left")
        self.assertEqual(loaded["archetype"], "targetForward")
        self.assertEqual(loaded["positions"], ["ST", "CF"])
        self.assertEqual(loaded["subposition"], "ST")
        self.assertEqual(loaded["id"], 0)

    def test_absent_identity_is_not_fabricated_from_overall_or_catalogue_id(self):
        a = economy.validate_catalog_player(catalog_player(rating=99, externalId="one"))
        b = economy.validate_catalog_player(catalog_player(rating=1, externalId="two"))
        self.assertEqual(a["preferredFoot"], "unknown")
        self.assertEqual(b["preferredFoot"], "unknown")
        for key in economy.PLAYER_ATTRIBUTES:
            self.assertNotIn(key, a)
            self.assertNotIn(key, b)
        self.assertNotIn("archetype", a)

    def test_all_explicit_foot_values_survive(self):
        for foot in economy.PLAYER_FEET:
            with self.subTest(foot=foot):
                self.assertEqual(economy.validate_catalog_player(catalog_player(preferredFoot=foot))["preferredFoot"], foot)

    def test_invalid_foot_values_rejected(self):
        for foot in [None, True, 0, 1, "Left", "ambidextrous", [], {}]:
            with self.subTest(foot=foot), self.assertRaises(economy.EconomyError):
                economy.validate_catalog_player(catalog_player(preferredFoot=foot))

    def test_every_supplied_attribute_is_a_bounded_integer(self):
        for key in economy.PLAYER_ATTRIBUTES:
            for value in [0, 100, -1, True, 80.0, "80", None]:
                with self.subTest(attribute=key, value=value), self.assertRaises(economy.EconomyError):
                    economy.validate_catalog_player(catalog_player(**{key: value}))
            for value in [1, 99]:
                with self.subTest(attribute=key, boundary=value):
                    self.assertEqual(economy.validate_catalog_player(catalog_player(**{key: value}))[key], value)

    def test_archetypes_are_explicit_recognized_profiles(self):
        for archetype in economy.PLAYER_ARCHETYPES:
            with self.subTest(archetype=archetype):
                self.assertEqual(economy.validate_catalog_player(catalog_player(archetype=archetype))["archetype"], archetype)
        for invalid in ["", "superstar", "target-forward", None, 3]:
            with self.subTest(invalid=invalid), self.assertRaises(economy.EconomyError):
                economy.validate_catalog_player(catalog_player(archetype=invalid))

    def test_secondary_positions_preserve_primary_and_reject_invalid_arrays(self):
        for invalid in [None, "ST", [], ["CF"], ["ST", "ST"], ["ST", "ATT"], ["ST", {}]]:
            with self.subTest(invalid=invalid), self.assertRaises(economy.EconomyError):
                economy.validate_catalog_player(catalog_player(positions=invalid))
        self.assertEqual(economy.validate_catalog_player(catalog_player(positions=["ST", "LW"]))["positions"], ["ST", "LW"])
        with self.assertRaises(economy.EconomyError):
            economy.validate_catalog_player(catalog_player(pos="DEF", subposition="ST"))

    def test_loading_legacy_persisted_record_does_not_invent_new_identity(self):
        state = {"profileId": "legacy", "players": [{"id": 14, "pos": "MID", "rating": 83}]}
        with self.service.connect() as connection:
            self.service._save(connection, state, auth=hashlib.sha256(b"legacy-token").hexdigest())
            loaded = self.service._load(connection, "legacy-token")
        self.assertEqual(loaded, state)
        self.assertNotIn("preferredFoot", loaded["players"][0])
        self.assertNotIn("strength", loaded["players"][0])

    def test_one_time_progression_migration_keeps_seed_identity(self):
        root = Path(self.temp.name) / "seed-root"
        (root / "data").mkdir(parents=True)
        players = [{"id": i, "pos": "MID", "rating": 80, "fitness": 95, "form": 80,
                    "preferredFoot": "left", "strength": 72, "archetype": "playmaker"} for i in range(11)]
        (root / "data/club-seed.json").write_text(json.dumps(players))
        old = copy.deepcopy(players)
        old[0].update(rating=83, fitness=0, form=0, preferredFoot="right", strength=99, archetype="stopper")
        self.service.rules.update(startingCash=0, startingTokens=0)
        with patch.object(economy, "ROOT", root), patch.object(self.service, "_advance"), \
             patch.object(self.service, "_view", side_effect=lambda c, s, now: {"players": copy.deepcopy(s["players"])}):
            result = self.service.create_profile({"players": old})
        self.assertEqual(result["players"][0]["rating"], 83)
        self.assertEqual(result["players"][0]["fitness"], 0)
        self.assertEqual(result["players"][0]["form"], 0)
        self.assertEqual(result["players"][0]["preferredFoot"], "left")
        self.assertEqual(result["players"][0]["strength"], 72)
        self.assertEqual(result["players"][0]["archetype"], "playmaker")

    def test_league_quality_matches_browser_contract_for_all_role_pairs(self):
        cases = []
        for pos in economy.POSITIONS:
            for slot in economy.POSITIONS:
                for rating in [1, 50, 75, 99]:
                    for fitness, form in [(0, 0), (50, 50), (95, 80), (100, 100)]:
                        cases.append({"player": {"pos": pos, "rating": rating, "fitness": fitness, "form": form}, "slot": slot})
        code = "const M=require('./player-model.js');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(JSON.parse(s).map(c=>M.forSlot(c.player,c.slot).skill))));"
        result = subprocess.run(["node", "-e", code], cwd=ROOT, input=json.dumps(cases), text=True,
                                capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), [economy.player_match_quality(c["player"], c["slot"]) for c in cases])

    def test_default_attributes_match_browser_profiles_without_rating_or_id_dependence(self):
        cases = [{"pos": pos, "subposition": sub, "rating": rating, "id": id_}
                 for pos, subs in economy.POSITIONS.items() for sub in sorted(subs)
                 for rating, id_ in [(1, 2), (99, 921)]]
        cases.extend({"pos": "MID", "archetype": archetype} for archetype in economy.PLAYER_ARCHETYPES)
        cases.extend([{"subposition": "CB"}, {"pos": "GK", "passing": 99}, {"preferredFoot": "both", "weakFoot": 30}])
        keys = list(economy.PLAYER_ATTRIBUTES)
        code = "const M=require('./player-model.js');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>{const c=JSON.parse(s);process.stdout.write(JSON.stringify(c.players.map(p=>{const n=M.normalize(p);return c.keys.map(k=>n[k])}))) });"
        result = subprocess.run(["node", "-e", code], cwd=ROOT, input=json.dumps({"players": cases, "keys": keys}),
                                text=True, capture_output=True, check=True)
        expected = [[economy.player_attribute_value(p, key) for key in keys] for p in cases]
        self.assertEqual(json.loads(result.stdout), expected)

    def test_training_missing_attribute_starts_from_shared_role_default(self):
        player = economy.validate_catalog_player(catalog_player(archetype="targetForward"))
        player.update(id=0, owned=True)
        state = {"players": [player], "trainingDate": "", "trainingUsed": 0}
        base = economy.player_attribute_value(player, "passing")
        self.service._command(None, state, "train", {"playerId": 0, "focus": "passing"}, 0)
        self.assertEqual(player["passing"], min(99, base + 3))
        self.assertEqual(state["trainingUsed"], 1)
        self.assertEqual(player["preferredFoot"], "unknown")
        self.assertNotIn("shooting", player)
        self.assertNotIn("strength", player)


if __name__ == "__main__":
    unittest.main()
