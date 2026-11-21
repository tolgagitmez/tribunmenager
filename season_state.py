"""Durable, fixture-scoped player rotation state; no transfer-wallet mutation.

The server snapshots readiness at kickoff. Only a completed authoritative
worker can write match minutes, conditioning and disciplinary state.
"""
import json

SCHEMA = """
CREATE TABLE IF NOT EXISTS season_player_state(
 league TEXT NOT NULL,slot INTEGER NOT NULL,player_key TEXT NOT NULL,
 fitness REAL NOT NULL,appearances INTEGER NOT NULL DEFAULT 0,
 minutes REAL NOT NULL DEFAULT 0,yellows INTEGER NOT NULL DEFAULT 0,
 reds INTEGER NOT NULL DEFAULT 0,yellow_carry INTEGER NOT NULL DEFAULT 0,
 suspension_until_round INTEGER NOT NULL DEFAULT 0,last_round INTEGER NOT NULL DEFAULT -1,
 PRIMARY KEY(league,slot,player_key));
CREATE TABLE IF NOT EXISTS season_fixture_appearances(
 league TEXT NOT NULL,round INTEGER NOT NULL,home INTEGER NOT NULL,away INTEGER NOT NULL,
 slot INTEGER NOT NULL,player_key TEXT NOT NULL,minutes REAL NOT NULL,
 yellows INTEGER NOT NULL,red INTEGER NOT NULL,
 fitness_before REAL NOT NULL,fitness_after REAL NOT NULL,
 PRIMARY KEY(league,round,home,away,slot,player_key));
"""

def player_key(player):
    uid=player.get("uid",player.get("rosterUid"))
    if isinstance(uid,str) and uid and len(uid)<200:
        return "uid:"+uid
    index=player.get("id",player.get("rosterId"))
    if type(index) is not int or index<0:
        raise ValueError("Season player requires a stable roster identity")
    return "id:"+str(index)

def clamp(v,lo,hi):
    return max(lo,min(hi,v))

def status(db,league,slot,player,round_number):
    key=player_key(player)
    row=db.execute("SELECT * FROM season_player_state WHERE league=? AND slot=? AND player_key=?",
                   (league,slot,key)).fetchone()
    original=clamp(float(player.get("fitness",95) or 95),0,100)
    if not row:
        return {**player,"fitness":original,"season":{
            "appearances":0,"minutes":0,"yellows":0,"reds":0,
            "yellowCarry":0,"suspended":False,"suspendedUntilRound":0}}
    # One fixed recovery increment per intervening fixture/day, never per read.
    available_fitness=clamp(row["fitness"]+8*max(0,round_number-row["last_round"]),30,100)
    return {**player,"fitness":round(available_fitness,2),"season":{
        "appearances":row["appearances"],"minutes":round(row["minutes"],2),
        "yellows":row["yellows"],"reds":row["reds"],
        "yellowCarry":row["yellow_carry"],
        "suspended":round_number<row["suspension_until_round"],
        "suspendedUntilRound":row["suspension_until_round"]}}

def check_lineup(players,starters):
    by_id={p["id"]:p for p in players if type(p.get("id")) is int}
    if len(by_id)!=len(players):raise ValueError("Kadrodaki futbolcu kimlikleri eşsiz olmalı.")
    if len(starters)!=11 or any(type(i) is not int or i not in by_id for i in starters) or len(set(starters))!=11:
        raise ValueError("İlk 11 seçimi geçersiz.")
    eligible=lambda p:not p.get("season",{}).get("suspended",False)
    order=[p for p in players if p["id"] not in starters and eligible(p)]
    used=set()
    fixed=[]
    replacements=[]
    for index in starters:
        old=by_id[index]
        if eligible(old):
            fixed.append(index)
            used.add(index)
            continue
        # Prefer the same specific role, then the same general sector.
        reserve=sorted((p for p in order if p["id"] not in used),
          key=lambda p:(p.get("subposition")!=old.get("subposition"),
                        p.get("pos")!=old.get("pos"),
                        -(p.get("rating",80) or 80),p["id"]))
        if not reserve:
            raise ValueError("Cezalı oyuncu "+str(old.get("name") or index)+
                             " yerine uygun yedek yok. Yeni kadro kurun.")
        replacement=reserve[0];fixed.append(replacement["id"]);used.add(replacement["id"])
        replacements.append({"out":index,"in":replacement["id"],"reason":"suspension"})
    return fixed,replacements

def demo_roster(formation):
    from_positions={
      "4-3-3":["LW","ST","RW","CM","DM","CM","LB","CB","CB","RB","GK"],
      "4-2-3-1":["ST","LM","AM","RM","DM","DM","LB","CB","CB","RB","GK"],
      "4-4-2":["ST","ST","LM","CM","CM","RM","LB","CB","CB","RB","GK"],
      "3-5-2":["ST","ST","LM","CM","AM","CM","RM","CB","CB","CB","GK"],
      "5-3-2":["ST","ST","CM","DM","CM","LWB","CB","CB","CB","RWB","GK"],
      "4-5-1":["ST","LM","CM","AM","CM","RM","LB","CB","CB","RB","GK"]}
    role=lambda p:"GK" if p=="GK" else "DEF" if p in ("CB","LB","RB","LWB","RWB") else "ATT" if p in ("ST","CF","LW","RW") else "MID"
    positions=from_positions.get(formation,from_positions["4-3-3"])+["CB","LB","RB","CM","ST","AM","DM"]
    return [{"id":i,"name":"Lig Oyuncusu "+str(i+1),"pos":role(p),"subposition":p,
             "positions":[p],"rating":80,"fitness":95,"form":80,
             "preferredFoot":"left" if p in ("LB","LWB","LW","LM") else "right",
             "dataKind":"league-demo"} for i,p in enumerate(positions)]

def apply_fixture(db,key,appearances):
    league,round_number,home,away=key
    for entry in appearances:
        if entry.get("team") not in (0,1):continue
        slot=(home,away)[entry["team"]]
        source={"uid":entry.get("rosterUid"),"id":entry["rosterId"]}
        identity=player_key(source)
        minutes=clamp(float(entry.get("minutes",0)),0,90)
        if minutes<=0:continue
        yellow=max(0,min(2,int(entry.get("yellow",0))))
        red=1 if entry.get("red") else 0
        before=clamp(float(entry.get("startFitness",95)),0,100)
        exertion=clamp(float(entry.get("sprintSeconds",0))/max(.01,float(entry.get("seconds",1))),0,1)
        after=round(clamp(before-13*minutes/90-5*exertion,30,100),2)
        cursor=db.execute("""INSERT OR IGNORE INTO season_fixture_appearances
           (league,round,home,away,slot,player_key,minutes,yellows,red,fitness_before,fitness_after)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
           (league,round_number,home,away,slot,identity,round(minutes,2),yellow,red,before,after))
        if not cursor.rowcount:continue  # idempotent even on worker replay
        previous=db.execute("""SELECT * FROM season_player_state
            WHERE league=? AND slot=? AND player_key=?""",(league,slot,identity)).fetchone()
        carry=(previous["yellow_carry"] if previous else 0)+yellow
        suspension=round_number+2 if red or carry>=5 else (previous["suspension_until_round"] if previous else 0)
        db.execute("""INSERT INTO season_player_state
            (league,slot,player_key,fitness,appearances,minutes,yellows,reds,yellow_carry,suspension_until_round,last_round)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(league,slot,player_key) DO UPDATE SET
            fitness=excluded.fitness,appearances=excluded.appearances,minutes=excluded.minutes,
            yellows=excluded.yellows,reds=excluded.reds,yellow_carry=excluded.yellow_carry,
            suspension_until_round=excluded.suspension_until_round,last_round=excluded.last_round""",
            (league,slot,identity,after,(previous["appearances"] if previous else 0)+1,
             round((previous["minutes"] if previous else 0)+minutes,2),
             (previous["yellows"] if previous else 0)+yellow,
             (previous["reds"] if previous else 0)+red,carry%5,suspension,round_number))

def summary(db,league,slot,round_number):
    rows=db.execute("""SELECT * FROM season_player_state WHERE league=? AND slot=?
                 ORDER BY player_key""",(league,slot)).fetchall()
    return [{"playerKey":r["player_key"],"fitness":round(clamp(r["fitness"]+8*max(0,round_number-r["last_round"]),30,100),2),
             "minutes":r["minutes"],"appearances":r["appearances"],
             "yellows":r["yellows"],"reds":r["reds"],
             "suspended":round_number<r["suspension_until_round"],
             "suspendedUntilRound":r["suspension_until_round"]} for r in rows]
