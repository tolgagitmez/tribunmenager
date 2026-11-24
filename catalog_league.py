"""Local-operator catalog league pilot. Snapshots never depend on later provider refreshes."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FORMATIONS = {
    "4-3-3": ["ATT"]*3+["MID"]*3+["DEF"]*4+["GK"],
    "4-2-3-1": ["ATT"]+["MID"]*5+["DEF"]*4+["GK"],
    "4-4-2": ["ATT"]*2+["MID"]*4+["DEF"]*4+["GK"],
    "3-5-2": ["ATT"]*2+["MID"]*5+["DEF"]*3+["GK"],
    "5-3-2": ["ATT"]*2+["MID"]*3+["DEF"]*5+["GK"],
    "4-5-1": ["ATT"]+["MID"]*5+["DEF"]*4+["GK"],
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_league_rosters(
 league TEXT NOT NULL,slot INTEGER NOT NULL,team_uid TEXT NOT NULL,
 source_at TEXT NOT NULL,players TEXT NOT NULL,starters TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1,
 PRIMARY KEY(league,slot), UNIQUE(league,team_uid));
"""

def convert(snapshots, mode):
    if not isinstance(snapshots,list) or len(snapshots)!=6:
        raise ValueError("Tam altı farklı takım gerekli.")
    if mode not in ("neutral","synthetic-varied"):
        raise ValueError("Geçersiz yetenek modeli.")
    try:
        result=subprocess.run(["node",str(ROOT/"tools/catalog-league-convert.cjs")],
            input=json.dumps({"snapshots":snapshots,"mode":mode}),text=True,capture_output=True,timeout=30)
        if result.returncode:
            raise ValueError("Kadro doğrulaması başarısız. Altı farklı, yeterli ve çakışmasız kadro gerekli.")
        return json.loads(result.stdout)
    except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:
        raise ValueError("Kadro dönüştürücüsü çalıştırılamadı.") from exc

def row(c,league,slot):
    return c.execute("SELECT * FROM catalog_league_rosters WHERE league=? AND slot=?",(league,slot)).fetchone()

def is_catalog(c,league):
    return c.execute("SELECT 1 FROM catalog_league_rosters WHERE league=? LIMIT 1",(league,)).fetchone() is not None

def validate_lineup(players,formation,ids):
    roles=FORMATIONS.get(formation)
    if not roles or not isinstance(ids,list) or len(ids)!=11 or any(type(i) is not int for i in ids) or len(set(ids))!=11:
        raise ValueError("İlk 11 veya diziliş geçersiz.")
    by_id={p["id"]:p for p in players}
    if any(i not in by_id or by_id[i]["pos"]!=role for i,role in zip(ids,roles)):
        raise ValueError("İlk 11 mevki uyumsuz.")
    if any(by_id[i].get("season",{}).get("suspended") for i in ids):
        raise ValueError("Cezalı futbolcu ilk 11'e seçilemez.")
    return ids[:]

def repair(players,formation,ids):
    # Preserve legal, available choices. Reserve distinct same-role players.
    roles=FORMATIONS[formation]
    by_id={p["id"]:p for p in players}
    selected=[]
    for i,role in enumerate(roles):
        old=ids[i] if i<len(ids) else None
        eligible=[p for p in players if p["pos"]==role and p["id"] not in selected and not p.get("season",{}).get("suspended")]
        if not eligible:
            raise ValueError("Bu diziliş için yeterli cezadan muaf futbolcu yok.")
        preferred=next((p for p in eligible if p["id"]==old),None)
        selected.append((preferred or max(eligible,key=lambda p:(p["rating"],-p["id"])))["id"])
    return validate_lineup(players,formation,selected)
