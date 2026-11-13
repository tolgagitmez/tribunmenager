"""Server-owned transfer economy. No client-supplied balances, prices or receipts.

Each development profile has a separate bot market. The catalogue is shared;
player ownership, market supply, scouting, offers and books are profile-scoped.
All commands, background sales and verified commerce use SQLite transactions.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import random
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
POSITIONS = {"GK": {"GK"}, "DEF": {"CB", "LB", "RB", "LWB", "RWB"},
             "MID": {"DM", "CM", "AM", "LM", "RM"}, "ATT": {"ST", "LW", "RW", "CF"}}
PLAYER_ATTRIBUTES = ("passing", "shooting", "tackling", "dribbling", "pace", "agility", "heading", "crossing",
                     "weakFoot", "strength", "balance", "acceleration", "endurance", "vision", "composure",
                     "goalkeeping", "reactions", "handling")
PLAYER_FEET = ("left", "right", "both", "unknown")
PLAYER_ARCHETYPES = ("goalkeeper", "stopper", "fullback", "playmaker", "ballWinner", "winger", "poacher", "targetForward")
BOT_CLUBS = ("Altınşehir SK", "Kuzey 1907", "Fırtına FK", "Anadolu Yıldızları", "Estrela Amadora", "Güneyspor")


class EconomyError(ValueError):
    pass


def integer(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise EconomyError(f"{label}: {low}–{high} arasında tam sayı gerekli.")
    return value


def text(value, limit, label):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise EconomyError(f"{label} geçersiz.")
    return value.strip()


def value_of(player):
    # Currency is integer club credit, never real money. Imported catalogue values
    # are an explicit game-economy mapping, independent of real-market currencies.
    if "value" in player:
        return integer(player["value"], 100000, 2000000000, "Oyuncu değeri")
    age = player.get("age", 25)
    return max(100000, round((player["rating"] / 75) ** 4 * 8000000 *
                            max(.55, 1 + (25 - age) * .025) / 10000) * 10000)


def price_bounds(player, rules):
    val = value_of(player)
    return math.ceil(val * rules["minPriceMultiplier"]), math.floor(val * rules["maxPriceMultiplier"])


def sale_probability(player, price, rules):
    # One conditional trial per irregular persisted market visit. A higher asking
    # multiplier always lowers probability; waiting never promises a sale time.
    ratio = price / value_of(player)
    form = player.get("realForm") or {}
    demand = .85 + .30 * form.get("score", 50) / 100
    return min(.9, max(.015, rules["baseSaleProbability"] * demand *
                         math.exp(-rules["priceSensitivity"] * (ratio - 1))))


def eligible_to_sell(state, player, rules):
    owned = [p for p in state["players"] if p.get("owned", True)]
    if not player.get("owned", True):
        raise EconomyError("Bu oyuncu artık kadroda değil.")
    if len(owned) <= rules["minSquad"]:
        raise EconomyError(f"Kadro en az {rules['minSquad']} oyuncudan oluşmalı.")
    if sum(p["pos"] == player["pos"] for p in owned) <= rules["minByPosition"][player["pos"]]:
        raise EconomyError("Bu mevkide korunması gereken asgari oyuncu sayısına ulaştın.")


def player_match_quality(player, slot):
    """The roster/match display contract; rounded per player before team mean.

    The browser applies this formula in player-model.js. Cross-runtime parity
    tests cover it explicitly; Python's ties-to-even round would disagree with
    JavaScript Math.round at the half boundaries.
    """
    a, b = player["pos"], slot
    fit = (1 if a == b else .45 if "GK" in (a, b) else .87 if {a, b} == {"MID", "ATT"}
           else .82 if {a, b} == {"DEF", "MID"} else .66)
    return math.floor(player["rating"] * fit * (.83+.17*player["fitness"]/100) *
                      (.91+.09*player["form"]/100) + .5)


def player_attribute_value(player, key):
    """Read a raw attribute or the same labelled profile default as the browser.

    The shared JSON is game tuning, not provider data. Looking up a training
    starting value does not fill every absent attribute on a stored player.
    """
    if key not in PLAYER_ATTRIBUTES:
        raise EconomyError("Oyuncu özelliği geçersiz.")
    if key == "weakFoot" and player.get("preferredFoot") == "both":
        return 99
    value = player.get(key)
    if type(value) in (int, float) and math.isfinite(value):
        return max(1, min(99, value))
    profiles = json.loads((ROOT / "player-model-profiles.json").read_text())
    archetype = player.get("archetype")
    if archetype not in PLAYER_ARCHETYPES:
        pos, sub = player.get("pos"), player.get("subposition")
        if pos not in POSITIONS:
            pos = next((group for group, positions in POSITIONS.items() if sub in positions), "MID")
        archetype = ("goalkeeper" if pos == "GK" else
                     ("fullback" if sub in ("LB", "RB", "LWB", "RWB") else "stopper") if pos == "DEF" else
                     ("winger" if sub in ("LW", "RW") else "poacher") if pos == "ATT" else
                     "ballWinner" if sub == "DM" else "playmaker")
    return profiles[archetype][key]


def repair_starters(state):
    # Retain numeric array IDs for the existing match/tactics APIs. Sold records
    # remain as tombstones; new signings append and never inherit a sold ID.
    owned = [p for p in state["players"] if p.get("owned", True)]
    valid, used = [], set()
    for i, old in enumerate(state.get("starters", [])):
        p = state["players"][old] if isinstance(old, int) and 0 <= old < len(state["players"]) else None
        if p and p.get("owned", True) and old not in used:
            valid.append(old)
            used.add(old)
        else:
            role = p["pos"] if p else ("GK" if i == 10 else "MID")
            pool = [q for q in owned if q["id"] not in used and q["id"] not in state.get("starters", [])]
            pool = pool or [q for q in owned if q["id"] not in used]
            q = max(pool, key=lambda q: (q["pos"] == role, q["rating"]))
            valid.append(q["id"])
            used.add(q["id"])
    while len(valid) < 11:
        q = max((q for q in owned if q["id"] not in used), key=lambda q: q["rating"])
        valid.append(q["id"])
        used.add(q["id"])
    state["starters"] = valid[:11]


def validate_catalog_player(raw):
    if not isinstance(raw, dict):
        raise EconomyError("Futbolcu kaydı nesne olmalı.")
    p = {k: text(raw.get(k), n, k) for k, n in (("providerId", 50), ("externalId", 100),
         ("name", 80), ("club", 80), ("league", 80), ("updatedAt", 40))}
    for k in ("providerId", "externalId"):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", p[k]):
            raise EconomyError("Veri sağlayıcı ve futbolcu kimliği yalnız harf/rakam/._- içerebilir.")
    p["uid"] = p["providerId"] + ":" + p["externalId"]
    try:
        stamp = datetime.fromisoformat(p["updatedAt"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError()
    except (ValueError, TypeError):
        raise EconomyError("updatedAt saat dilimi içeren ISO tarih olmalı.")
    p["pos"] = raw.get("pos")
    if p["pos"] not in POSITIONS or raw.get("subposition") not in POSITIONS[p["pos"]]:
        raise EconomyError("Mevki / özel mevki eşleşmesi geçersiz.")
    p["subposition"] = raw["subposition"]
    p["nationality"] = text(raw.get("nationality"), 2, "Uyruk").upper()
    if not re.fullmatch("[A-Z]{2}", p["nationality"]):
        raise EconomyError("Uyruk iki harfli kod olmalı.")
    for key, low, high in (("age", 16, 50), ("rating", 1, 99), ("value", 100000, 2000000000)):
        p[key] = integer(raw.get(key), low, high, key)
    for key in PLAYER_ATTRIBUTES:
        if key in raw:
            p[key] = integer(raw[key], 1, 99, key)
    # Unknown foot and absent attributes are data gaps, not measurements derived
    # from an array ID or the overall rating. The shared match model supplies
    # explicitly labelled simulation defaults when those values are needed.
    foot = raw.get("preferredFoot", "unknown")
    if foot not in PLAYER_FEET:
        raise EconomyError("Tercih edilen ayak left/right/both/unknown olmalı.")
    p["preferredFoot"] = foot
    if "positions" in raw:
        positions = raw["positions"]
        allowed = set().union(*POSITIONS.values())
        if (not isinstance(positions, list) or not positions or len(positions) > len(allowed) or
                any(not isinstance(pos, str) or pos not in allowed for pos in positions) or
                len(set(positions)) != len(positions) or p["subposition"] not in positions):
            raise EconomyError("Uyumlu mevkiler benzersiz ve asıl özel mevkiyi içeren bir dizi olmalı.")
        p["positions"] = positions[:]
    if "archetype" in raw:
        archetype = text(raw["archetype"], 40, "Oyuncu profili")
        if archetype not in PLAYER_ARCHETYPES:
            raise EconomyError("Oyuncu profili tanımlı futbol rollerinden biri olmalı.")
        p["archetype"] = archetype
    rf = raw.get("realForm")
    p["realForm"] = None
    if rf is not None:
        if not isinstance(rf, dict):
            raise EconomyError("Gerçek form kaydı geçersiz.")
        score = integer(rf.get("score"), 0, 100, "Gerçek form")
        sample = integer(rf.get("sampleMatches"), 1, 100, "Form maç sayısı")
        as_of = text(rf.get("asOf"), 10, "Form tarihi")
        try:
            datetime.strptime(as_of, "%Y-%m-%d")
        except ValueError:
            raise EconomyError("Form tarihi YYYY-MM-DD olmalı.")
        p["realForm"] = {"score": score, "sampleMatches": sample, "asOf": as_of, "provider": p["providerId"]}
    p.update(fitness=95, form=(rf or {}).get("score", 80), xp=0, face=0, dataKind="catalog")
    return p


def criteria(raw):
    if not isinstance(raw, dict):
        raise EconomyError("Keşif filtreleri geçersiz.")
    c = {}
    if raw.get("pos"):
        if raw["pos"] not in POSITIONS:
            raise EconomyError("Mevki geçersiz.")
        c["pos"] = raw["pos"]
    if raw.get("subposition"):
        sub = raw["subposition"]
        if sub not in set().union(*POSITIONS.values()) or c.get("pos") and sub not in POSITIONS[c["pos"]]:
            raise EconomyError("Özel mevki seçilen mevkiyle uyumlu değil.")
        c["subposition"] = sub
    for key, low, high, default in (("minAge", 16, 50, 16), ("maxAge", 16, 50, 50),
                                  ("minRating", 1, 99, 1), ("maxRating", 1, 99, 99), ("minForm", 0, 100, 0)):
        c[key] = integer(raw.get(key, default), low, high, key)
    if c["minAge"] > c["maxAge"] or c["minRating"] > c["maxRating"]:
        raise EconomyError("Alt sınır üst sınırdan büyük olamaz.")
    for key in ("nationality", "league"):
        if raw.get(key):
            c[key] = text(raw[key], 80, key)
    return c


def matches(p, c):
    if any(c.get(k) and p.get(k) != c[k] for k in ("pos", "subposition", "nationality")):
        return False
    if c.get("league") and c["league"].casefold() not in p["league"].casefold():
        return False
    return (c["minAge"] <= p["age"] <= c["maxAge"] and c["minRating"] <= p["rating"] <= c["maxRating"] and
            (not c["minForm"] or (p.get("realForm") or {}).get("score", -1) >= c["minForm"]))


class TransferService:
    def __init__(self, database, clock=time.time, rules=None):
        self.path = Path(database)
        self.clock = clock
        self.rules = rules or json.loads((ROOT / "data/transfer-rules.json").read_text())
        self.init_db()

    def connect(self):
        c = sqlite3.connect(self.path, timeout=20)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def init_db(self):
        with self.connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS transfer_profiles(id TEXT PRIMARY KEY, auth TEXT UNIQUE NOT NULL, state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS transfer_catalog(uid TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS transfer_commands(profile TEXT, request_id TEXT, payload TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(profile,request_id));
            CREATE TABLE IF NOT EXISTS transfer_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT, profile TEXT NOT NULL,
                at REAL NOT NULL, kind TEXT NOT NULL, currency TEXT NOT NULL, delta INTEGER NOT NULL, balance INTEGER NOT NULL, reference TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS transfer_receipts(provider TEXT, event_id TEXT, fingerprint TEXT NOT NULL,
                profile TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(provider,event_id));
            CREATE TABLE IF NOT EXISTS transfer_league_links(profile TEXT PRIMARY KEY, league TEXT NOT NULL, slot INT NOT NULL,
                UNIQUE(league,slot));
            """)

    def import_catalog(self, payload):
        if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("players"), list):
            raise EconomyError("Katalog version=1 ve players dizisi içermeli.")
        players = [validate_catalog_player(p) for p in payload["players"]]
        if len({p["uid"] for p in players}) != len(players):
            raise EconomyError("Tekrarlanan futbolcu kimliği var.")
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            for p in players:
                previous = c.execute("SELECT data FROM transfer_catalog WHERE uid=?", (p["uid"],)).fetchone()
                if previous:
                    old = json.loads(previous[0])
                    parse = lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))
                    if parse(p["updatedAt"]) < parse(old["updatedAt"]):
                        raise EconomyError("Eski tarihli veri güncel futbolcu kaydını değiştiremez.")
                c.execute("INSERT INTO transfer_catalog VALUES(?,?) ON CONFLICT(uid) DO UPDATE SET data=excluded.data", (p["uid"], json.dumps(p)))
        return len(players)

    def _catalog(self, c):
        return [json.loads(row[0]) for row in c.execute("SELECT data FROM transfer_catalog ORDER BY uid")]

    def _record(self, c, s, kind, currency, delta, ref, at):
        if delta < 0 and s["wallet"][currency] < -delta:
            raise EconomyError("Token bakiyesi yetersiz." if currency == "tokens" else "Kulüp bütçesi yetersiz.")
        s["wallet"][currency] += delta
        c.execute("INSERT INTO transfer_ledger(profile,at,kind,currency,delta,balance,reference) VALUES(?,?,?,?,?,?,?)",
                  (s["profileId"], at, kind, currency, delta, s["wallet"][currency], ref))

    def create_profile(self, legacy=None):
        now = self.clock()
        token = secrets.token_urlsafe(32)
        s = {"profileId": secrets.token_hex(16), "revision": 1, "wallet": {"cash": 0, "tokens": 0},
             "players": json.loads((ROOT / "data/club-seed.json").read_text()),
             "starters": [8, 9, 10, 7, 5, 6, 4, 2, 3, 1, 0], "listings": [], "history": [],
             "market": [], "scout": None, "offer": None, "nextOfferAt": 0, "sequence": 0,
             "rng": secrets.randbits(32) or 1, "lastTime": now, "trainingDate": "", "trainingUsed": 0, "adClaims": []}
        # One-time development save migration: only existing sample-player
        # progression, never currencies, ownership, external IDs or receipts.
        if isinstance(legacy, dict) and isinstance(legacy.get("players"), list):
            for i, p in enumerate(s["players"]):
                old = legacy["players"][i] if i < len(legacy["players"]) else None
                if not isinstance(old, dict) or old.get("id") != i:
                    continue
                for key in ("rating", "fitness", "form", "passing", "shooting", "tackling", "dribbling", "pace", "agility", "heading", "crossing"):
                    v = old.get(key)
                    low, high = (0, 100) if key in ("fitness", "form") else (1, 99)
                    if type(v) is int and low <= v <= high:
                        p[key] = v
                p["xp"] = old.get("xp", 0) if type(old.get("xp", 0)) is int and 0 <= old.get("xp", 0) < 6 else 0
            ids = legacy.get("starters")
            if isinstance(ids, list) and len(ids) == 11 and all(type(i) is int and 0 <= i < len(s["players"]) for i in ids) and len(set(ids)) == 11:
                s["starters"] = ids
            if legacy.get("trainingDate") == datetime.fromtimestamp(now, timezone.utc).date().isoformat():
                s["trainingDate"] = legacy["trainingDate"]
                s["trainingUsed"] = max(0, min(2, legacy.get("trainingUsed", 0))) if type(legacy.get("trainingUsed", 0)) is int else 0
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            self._record(c, s, "welcome", "cash", self.rules["startingCash"], "welcome", now)
            self._record(c, s, "welcome", "tokens", self.rules["startingTokens"], "welcome", now)
            self._advance(c, s, now)
            self._save(c, s, auth=hashlib.sha256(token.encode()).hexdigest())
            view = self._view(c, s, now)
        return {"token": token, **view}

    def _load(self, c, token):
        if not isinstance(token, str) or len(token) > 150:
            raise EconomyError("Transfer oturumu geçersiz.")
        row = c.execute("SELECT state FROM transfer_profiles WHERE auth=?", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row:
            raise EconomyError("Transfer oturumu bulunamadı.")
        return json.loads(row[0])

    def _save(self, c, s, auth=None):
        if auth:
            c.execute("INSERT INTO transfer_profiles VALUES(?,?,?)", (s["profileId"], auth, json.dumps(s)))
        else:
            c.execute("UPDATE transfer_profiles SET state=? WHERE id=?", (json.dumps(s), s["profileId"]))

    def _random(self, s):
        x = s["rng"]
        x ^= (x << 13) & 0xffffffff
        x ^= x >> 17
        x ^= (x << 5) & 0xffffffff
        s["rng"] = x & 0xffffffff or 1
        return s["rng"] / 4294967296

    def _interval(self, s):
        return self.rules["checkMinSeconds"] + self._random(s) * (self.rules["checkMaxSeconds"] - self.rules["checkMinSeconds"])

    def _next_id(self, s, prefix):
        s["sequence"] += 1
        return f"{prefix}-{s['sequence']}"

    def _player(self, s, id_):
        integer(id_, 0, len(s["players"]) - 1, "Oyuncu")
        p = s["players"][id_]
        if not p.get("owned", True):
            raise EconomyError("Oyuncu kadroda değil.")
        return p

    def _history(self, s, item):
        s["history"].insert(0, item)
        del s["history"][200:]

    def _sell(self, c, s, p, price, ref, now, kind="market-sale"):
        eligible_to_sell(s, p, self.rules)
        if kind == "quick-sale":
            self._record(c, s, kind, "tokens", -self.rules["quickSaleTokens"], ref, now)
        self._record(c, s, kind, "cash", price, ref, now)
        p["owned"] = False
        buyer = BOT_CLUBS[int(self._random(s) * len(BOT_CLUBS))]
        for listing in s["listings"]:
            if listing["playerId"] == p["id"] and listing["status"] == "active":
                listing.update(status="sold", soldAt=now, buyer=buyer)
        repair_starters(s)
        self._history(s, {"id": ref, "type": kind, "player": p["name"], "buyer": buyer, "price": price, "at": now})

    def _league_lock_until(self, c, s, at):
        link = c.execute("SELECT league,slot FROM transfer_league_links WHERE profile=?", (s["profileId"],)).fetchone()
        if not link:
            return None
        match = c.execute("SELECT kickoff+300 FROM fixtures WHERE league=? AND (home=? OR away=?) AND kickoff<=? AND kickoff+300>? LIMIT 1",
                          (link["league"], link["slot"], link["slot"], at, at)).fetchone()
        return match[0] if match else None

    def _update_league_strength(self, c, s, now):
        link = c.execute("SELECT league,slot FROM transfer_league_links WHERE profile=?", (s["profileId"],)).fetchone()
        if not link or self._league_lock_until(c, s, now):
            return
        team = c.execute("SELECT formation FROM teams WHERE league=? AND slot=?", (link["league"], link["slot"])).fetchone()
        if not team:
            return
        roles = {"4-3-3": ["ATT"]*3+["MID"]*3+["DEF"]*4+["GK"],
                 "4-2-3-1": ["ATT"]+["MID"]*5+["DEF"]*4+["GK"],
                 "4-4-2": ["ATT"]*2+["MID"]*4+["DEF"]*4+["GK"],
                 "3-5-2": ["ATT"]*2+["MID"]*5+["DEF"]*3+["GK"],
                 "5-3-2": ["ATT"]*2+["MID"]*3+["DEF"]*5+["GK"],
                 "4-5-1": ["ATT"]+["MID"]*5+["DEF"]*4+["GK"]}[team["formation"]]
        quality = 0
        for id_, role in zip(s["starters"], roles):
            p = s["players"][id_]
            quality += player_match_quality(p, role)
        c.execute("UPDATE teams SET quality=? WHERE league=? AND slot=?", (quality/11, link["league"], link["slot"]))

    def _advance(self, c, s, now):
        now = max(now, s["lastTime"])
        changed = False
        # Chronological market visits, including while the tab is closed. The
        # persisted RNG and next-check time prevent rerolls on refresh/repricing.
        for _ in range(4096):
            active = [l for l in s["listings"] if l["status"] == "active" and l["nextCheckAt"] <= now]
            if not active:
                break
            l = min(active, key=lambda x: (x["nextCheckAt"], x["id"]))
            at = l["nextCheckAt"]
            lock_until = self._league_lock_until(c, s, at)
            if lock_until:
                l["nextCheckAt"] = lock_until + self._interval(s)
                changed = True
                continue
            p = s["players"][l["playerId"]]
            try:
                eligible_to_sell(s, p, self.rules)
            except EconomyError:
                l.update(status="cancelled", reason="Kadro güvenliği sınırı", closedAt=at)
            else:
                # Revalue on every visit, not only when listing was created.
                lo, hi = price_bounds(p, self.rules)
                l["price"] = max(lo, min(hi, l["price"]))
                if self._random(s) < sale_probability(p, l["price"], self.rules):
                    self._sell(c, s, p, l["price"], l["id"], at)
                else:
                    l["checks"] += 1
                    l["nextCheckAt"] = at + self._interval(s)
            changed = True
        if s["scout"] and s["scout"]["status"] == "searching" and s["scout"]["readyAt"] <= now:
            s["scout"]["status"] = "ready"
            changed = True
        catalog = self._catalog(c)
        owned = {p["uid"] for p in s["players"] if p.get("owned", True)}
        known = {x["player"]["uid"] for x in s["market"]}
        available = sum(l["available"] and l["player"]["uid"] not in owned for l in s["market"])
        for p in catalog:
            if available >= self.rules["marketSize"]:
                break
            if p["uid"] not in owned and p["uid"] not in known:
                s["market"].append({"id": self._next_id(s, "market"), "player": p,
                                    "price": round(value_of(p) * (1.1 + .6 * self._random(s))), "available": True})
                changed = True
                available += 1
        by_uid = {p["uid"]: p for p in catalog}
        for listing in s["market"]:
            p = by_uid.get(listing["player"]["uid"])
            if p and listing["player"] != p:
                ratio = listing["price"] / value_of(listing["player"])
                listing.update(player=p, price=round(value_of(p) * max(1, min(2.5, ratio))))
                changed = True
        if (not s["offer"] or s["offer"]["expiresAt"] <= now or s["offer"].get("claimed")) and now >= s["nextOfferAt"]:
            roster = [p for p in s["players"] if p.get("owned", True)]
            weakest = min(POSITIONS, key=lambda pos: sum(p["rating"] for p in roster if p["pos"] == pos) / max(1, sum(p["pos"] == pos for p in roster)))
            base = min(p["rating"] for p in roster if p["pos"] == weakest)
            candidates = [p for p in catalog if p["uid"] not in owned and p["pos"] == weakest and p["rating"] >= base + 2]
            if candidates:
                p = min(candidates, key=lambda p: (abs(p["rating"] - base - 8), p["uid"]))
                standard = max(20, math.ceil(value_of(p) / 500000))
                s["offer"] = {"id": self._next_id(s, "offer"), "player": p, "position": weakest,
                              "standardTokens": standard, "tokens": max(1, math.floor(standard * (100 - self.rules["offerDiscountPercent"]) / 100)),
                              "createdAt": now, "expiresAt": now + self.rules["offerSeconds"], "claimed": False}
                s["nextOfferAt"] = now + self.rules["offerCooldownSeconds"]
                changed = True
        s["lastTime"] = now
        self._update_league_strength(c, s, now)
        if changed:
            s["revision"] += 1

    def _view(self, c, s, now):
        view = {k: copy.deepcopy(s[k]) for k in ("profileId", "revision", "wallet", "players", "starters", "history", "scout", "offer", "trainingDate", "trainingUsed")}
        view["listings"] = [{k: v for k, v in l.items() if k != "nextCheckAt"} for l in s["listings"] if l["status"] == "active"]
        owned = {p["uid"] for p in s["players"] if p.get("owned", True)}
        view["market"] = [copy.deepcopy(l) for l in s["market"] if l["available"] and l["player"]["uid"] not in owned]
        if view["scout"] and view["scout"]["status"] == "searching":
            view["scout"]["results"] = []  # no early result leak
        view["rules"] = self.rules
        view["serverTime"] = max(now, s["lastTime"])
        view["catalogCount"] = c.execute("SELECT count(*) FROM transfer_catalog").fetchone()[0]
        link = c.execute("SELECT league,slot FROM transfer_league_links WHERE profile=?", (s["profileId"],)).fetchone()
        view["linkedLeague"] = dict(link) if link else None
        view["rosterLockedUntil"] = self._league_lock_until(c, s, now)
        view["ledger"] = [dict(l) for l in c.execute("SELECT at,kind,currency,delta,balance,reference FROM transfer_ledger WHERE profile=? ORDER BY id DESC LIMIT 100", (s["profileId"],))]
        view["capabilities"] = {"payments": False, "rewardedAds": False, "verifiedCommerceBridge": bool(os.environ.get("TRIBUN_COMMERCE_SECRET"))}
        return view

    def status(self, token):
        now = self.clock()
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            s = self._load(c, token)
            self._advance(c, s, now)
            self._save(c, s)
            return self._view(c, s, now)

    def command(self, token, request_id, action, payload):
        text(request_id, 100, "İşlem kimliği")
        if not isinstance(payload, dict):
            raise EconomyError("İşlem parametreleri geçersiz.")
        fingerprint = json.dumps([action, payload], sort_keys=True, separators=(",", ":"))
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            s = self._load(c, token)
            now = max(self.clock(), s["lastTime"])
            self._advance(c, s, now)
            duplicate = c.execute("SELECT payload,result FROM transfer_commands WHERE profile=? AND request_id=?", (s["profileId"], request_id)).fetchone()
            if duplicate:
                if duplicate["payload"] != fingerprint:
                    raise EconomyError("İşlem kimliği başka bir istek için kullanılmış.")
                result = json.loads(duplicate["result"])
            else:
                if action in ("buy", "quick-sell", "scout-buy", "offer-buy", "lineup", "train") and self._league_lock_until(c, s, now):
                    raise EconomyError("Günlük maç oynanırken kadro değişiklikleri kilitlidir. Maç bitince yeniden dene.")
                result = self._command(c, s, action, payload, now)
                s["revision"] += 1
                self._update_league_strength(c, s, now)
                c.execute("INSERT INTO transfer_commands VALUES(?,?,?,?)", (s["profileId"], request_id, fingerprint, json.dumps(result)))
            self._save(c, s)
            return {"result": result, **self._view(c, s, now)}

    def _sign(self, c, s, p, cash, tokens, ref, now, kind):
        if sum(q.get("owned", True) for q in s["players"]) >= self.rules["maxSquad"]:
            raise EconomyError("Kadro kapasitesi dolu.")
        if any(q["uid"] == p["uid"] and q.get("owned", True) for q in s["players"]):
            raise EconomyError("Bu futbolcu zaten kadroda.")
        # Check both before writing either currency. Transaction also rolls back
        # any later failure, including duplicate callback or roster exceptions.
        if s["wallet"]["cash"] < cash or s["wallet"]["tokens"] < tokens:
            raise EconomyError("Transfer için bütçe veya token yetersiz.")
        if cash:
            self._record(c, s, kind, "cash", -cash, ref, now)
        if tokens:
            self._record(c, s, kind, "tokens", -tokens, ref, now)
        player = copy.deepcopy(p)
        taken = {q["number"] for q in s["players"] if q.get("owned", True)}
        number = next(n for n in range(1, 100) if n not in taken)
        player.update(id=len(s["players"]), number=number, owned=True, fitness=95, xp=0)
        s["players"].append(player)
        for l in s["market"]:
            if l["player"]["uid"] == p["uid"]:
                l["available"] = False
        self._history(s, {"id": ref, "type": kind, "player": p["name"], "seller": p["club"], "price": cash, "tokens": tokens, "at": now})
        return {"message": p["name"] + " kadroya katıldı.", "playerId": player["id"]}

    def _command(self, c, s, action, d, now):
        r = self.rules
        def quote(key, actual):
            if key in d and (type(d[key]) is not int or d[key] != actual):
                raise EconomyError("Bedel değişti. Güncel tutarı inceleyip işlemi yeniden aç.")
        if action == "link-league":
            if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='teams'").fetchone():
                raise EconomyError("Günlük lig henüz başlatılmadı.")
            person = c.execute("SELECT league,slot FROM teams WHERE token=?", (text(d.get("leagueToken"), 100, "Lig oturumu"),)).fetchone()
            if not person:
                raise EconomyError("Lig oturumu geçersiz.")
            target = c.execute("SELECT profile FROM transfer_league_links WHERE league=? AND slot=?", (person["league"], person["slot"])).fetchone()
            if target and target["profile"] != s["profileId"]:
                raise EconomyError("Bu lig kulübü başka transfer profiline bağlı.")
            old = c.execute("SELECT league FROM transfer_league_links WHERE profile=?", (s["profileId"],)).fetchone()
            if old and old["league"] != person["league"]:
                unfinished = c.execute("SELECT 1 FROM fixtures WHERE league=? AND home_score IS NULL LIMIT 1", (old["league"],)).fetchone()
                if unfinished:
                    raise EconomyError("Transfer profili devam eden başka bir lige bağlı.")
            active = c.execute("SELECT 1 FROM fixtures WHERE league=? AND kickoff<=? AND kickoff+300>? LIMIT 1", (person["league"], now, now)).fetchone()
            if active and not target:
                raise EconomyError("Transfer profili maç sırasında lige bağlanamaz.")
            c.execute("INSERT INTO transfer_league_links VALUES(?,?,?) ON CONFLICT(profile) DO UPDATE SET league=excluded.league,slot=excluded.slot", (s["profileId"], person["league"], person["slot"]))
            return {"message": "Transfer kadron günlük lige bağlandı."}
        if action in ("list", "reprice", "unlist", "quick-sell"):
            p = self._player(s, d.get("playerId"))
            active = [l for l in s["listings"] if l["status"] == "active"]
            current = next((l for l in active if l["playerId"] == p["id"]), None)
            if action == "unlist":
                if not current:
                    raise EconomyError("Oyuncunun aktif ilanı yok.")
                current.update(status="withdrawn", closedAt=now)
                return {"message": "Oyuncu transfer listesinden çıkarıldı."}
            eligible_to_sell(s, p, r)
            if action == "quick-sell":
                quote("expectedValue", value_of(p))
                quote("expectedTokens", r["quickSaleTokens"])
                ref = self._next_id(s, "quick")
                self._sell(c, s, p, value_of(p), ref, now, "quick-sale")
                return {"message": "Oyuncu mevcut değerinden satıldı."}
            price = integer(d.get("price"), *price_bounds(p, r), "İlan fiyatı")
            if action == "reprice":
                if not current:
                    raise EconomyError("Oyuncunun aktif ilanı yok.")
                current["price"] = price  # preserve random market-visit schedule
                return {"message": "İlan fiyatı güncellendi."}
            if current:
                raise EconomyError("Oyuncu zaten transfer listesinde.")
            if len(active) >= r["maxListings"]:
                raise EconomyError("Aynı anda en fazla dört oyuncu listelenebilir.")
            s["listings"].append({"id": self._next_id(s, "listing"), "playerId": p["id"], "price": price,
                                  "listedAt": now, "nextCheckAt": now + self._interval(s), "checks": 0, "status": "active"})
            return {"message": "Oyuncu transfer listesine eklendi."}
        if action == "buy":
            listing = next((l for l in s["market"] if l["id"] == d.get("listingId") and l["available"]), None)
            if not listing:
                raise EconomyError("Transfer ilanı artık mevcut değil.")
            quote("expectedCash", listing["price"])
            return self._sign(c, s, listing["player"], listing["price"], 0, listing["id"], now, "market-buy")
        if action == "scout-start":
            quote("expectedCash", r["scoutCash"])
            if s["scout"] and s["scout"]["status"] == "searching":
                raise EconomyError("Keşif görevi devam ediyor.")
            crit = criteria(d.get("criteria", {}))
            owned = {p["uid"] for p in s["players"] if p.get("owned", True)}
            pool = [p for p in self._catalog(c) if p["uid"] not in owned and matches(p, crit)]
            if not pool:
                raise EconomyError("Bu filtrelerle keşfedilecek futbolcu yok. Bütçe harcanmadı.")
            # Selection stays hidden and stable until readyAt, including restarts.
            pool.sort(key=lambda p: (-(p.get("realForm") or {}).get("score", 50), -p["rating"], p["uid"]))
            ref = self._next_id(s, "scout")
            results = [{"id": f"{ref}-{i}", "player": p, "price": round(value_of(p) * 1.1), "available": True}
                       for i, p in enumerate(pool[:r["scoutResults"]])]
            self._record(c, s, "scout", "cash", -r["scoutCash"], ref, now)
            s["scout"] = {"id": ref, "criteria": crit, "startedAt": now, "readyAt": now + r["scoutSeconds"],
                          "expiresAt": now + r["scoutSeconds"] + r["scoutResultSeconds"], "status": "searching", "results": results}
            return {"message": "Keşif görevi başladı."}
        if action == "scout-buy":
            job = s["scout"]
            if not job or job["status"] != "ready" or now >= job["expiresAt"]:
                raise EconomyError("Keşif sonuçları hazır değil veya süresi doldu.")
            result = next((p for p in job["results"] if p["id"] == d.get("resultId") and p["available"]), None)
            if not result:
                raise EconomyError("Keşif oyuncusu artık mevcut değil.")
            quote("expectedCash", result["price"])
            answer = self._sign(c, s, result["player"], result["price"], 0, result["id"], now, "scout-buy")
            result["available"] = False
            return answer
        if action == "offer-buy":
            offer = s["offer"]
            if not offer or offer["id"] != d.get("offerId") or offer["claimed"] or now >= offer["expiresAt"]:
                raise EconomyError("Özel teklif sona erdi veya kullanıldı.")
            quote("expectedTokens", offer["tokens"])
            answer = self._sign(c, s, offer["player"], 0, offer["tokens"], offer["id"], now, "offer-buy")
            offer["claimed"] = True
            return answer
        if action == "lineup":
            ids = d.get("starters")
            if not isinstance(ids, list) or len(ids) != 11 or any(not isinstance(i, int) or isinstance(i, bool) for i in ids) or len(set(ids)) != 11:
                raise EconomyError("İlk 11 geçersiz.")
            for id_ in ids:
                self._player(s, id_)
            s["starters"] = ids
            return {"message": "İlk 11 eşitlendi."}
        if action == "train":
            p = self._player(s, d.get("playerId"))
            day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
            if day != s["trainingDate"]:
                s.update(trainingDate=day, trainingUsed=0)
            if s["trainingUsed"] >= 2:
                raise EconomyError("Günlük antrenman hakkın bitti.")
            focus = d.get("focus")
            if focus not in ("passing", "shooting", "tackling", "fitness", "dribbling", "pace", "heading", "crossing"):
                raise EconomyError("Antrenman alanı geçersiz.")
            if focus == "fitness":
                p[focus] = min(100, p[focus] + 5)
            else:
                p[focus] = min(99, player_attribute_value(p, focus) + 3)
                p["xp"] += 3
                if p["xp"] >= 6:
                    p["rating"] = min(99, p["rating"] + 1)
                    p["xp"] -= 6
                p["fitness"] = max(50, p["fitness"] - 2)
            s["trainingUsed"] += 1
            return {"message": p["name"] + " · Antrenman tamamlandı."}
        raise EconomyError("Transfer işlemi tanınmıyor.")

    def settle_all(self):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            now = self.clock()
            for row in c.execute("SELECT state FROM transfer_profiles").fetchall():
                s = json.loads(row[0])
                self._advance(c, s, now)
                self._save(c, s)

    def verified_commerce(self, raw_body, signature):
        """Trusted payment/ad adapter callback, not a browser credit endpoint.

        An external adapter must validate the actual provider's receipt/SSV,
        then sign this bridge envelope. Provider SDK/checkout is not installed.
        """
        secret = os.environ.get("TRIBUN_COMMERCE_SECRET", "")
        if len(secret) < 32:
            raise EconomyError("Ödeme/reklam doğrulama bağlantısı etkin değil.")
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(expected, signature):
            raise EconomyError("Doğrulama imzası geçersiz.")
        try:
            e = json.loads(raw_body)
        except (ValueError, UnicodeError):
            raise EconomyError("Doğrulama kaydı geçersiz.")
        if not isinstance(e, dict):
            raise EconomyError("Doğrulama kaydı nesne olmalı.")
        provider = text(e.get("provider"), 50, "Sağlayıcı")
        event_id = text(e.get("eventId"), 100, "Olay kimliği")
        profile = text(e.get("profileId"), 50, "Kulüp kimliği")
        sent = e.get("timestamp")
        if isinstance(sent, bool) or not isinstance(sent, (int, float)) or not math.isfinite(sent) or abs(self.clock() - sent) > 300:
            raise EconomyError("Doğrulama zaman aşımına uğradı.")
        # Timestamp may change during a retry; economic identity must not.
        fingerprint = json.dumps({k: v for k, v in e.items() if k != "timestamp"}, sort_keys=True)
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            old = c.execute("SELECT fingerprint,result FROM transfer_receipts WHERE provider=? AND event_id=?", (provider, event_id)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise EconomyError("Doğrulama kimliği farklı bir işlemle çakışıyor.")
                return json.loads(old["result"])
            row = c.execute("SELECT state FROM transfer_profiles WHERE id=?", (profile,)).fetchone()
            if not row:
                raise EconomyError("Kulüp bulunamadı.")
            s = json.loads(row[0])
            now = max(self.clock(), s["lastTime"])
            if e.get("type") == "token_purchase":
                pack = next((p for p in self.rules["tokenPacks"] if p["sku"] == e.get("sku")), None)
                if not pack:
                    raise EconomyError("Token paketi geçersiz.")
                amount, kind = pack["tokens"], "token-purchase"
            elif e.get("type") == "rewarded_ad":
                if e.get("placement") != "transfer-reward":
                    raise EconomyError("Reklam ödül alanı geçersiz.")
                day = datetime.fromtimestamp(now, timezone.utc).date()
                claims = s["adClaims"]
                if claims and now - claims[-1] < self.rules["rewardCooldownSeconds"]:
                    raise EconomyError("Reklam ödülü bekleme süresi dolmadı.")
                if sum(datetime.fromtimestamp(t, timezone.utc).date() == day for t in claims) >= self.rules["rewardDailyLimit"]:
                    raise EconomyError("Günlük reklam ödülü sınırına ulaşıldı.")
                s["adClaims"] = [t for t in claims if now - t < 172800] + [now]
                amount, kind = self.rules["rewardTokens"], "ad-reward"
            else:
                raise EconomyError("Doğrulama olayı tanınmıyor.")
            self._record(c, s, kind, "tokens", amount, provider + ":" + event_id, now)
            s["revision"] += 1
            self._save(c, s)
            result = {"ok": True, "tokensGranted": amount}
            c.execute("INSERT INTO transfer_receipts VALUES(?,?,?,?,?)", (provider, event_id, fingerprint, profile, json.dumps(result)))
            return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Validate and import the future football data catalogue; no network access.")
    ap.add_argument("--database", required=True)
    ap.add_argument("--import-catalog", type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps({"imported": TransferService(args.database).import_catalog(json.loads(args.import_catalog.read_text()))}, ensure_ascii=False))
