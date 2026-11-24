"""Provision an authorized six-club catalog league in the local game DB."""
import argparse
import json
from pathlib import Path
import sys
import server
from tools.api_football_catalog import Catalog, LOCAL

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--team",type=int,action="append",required=True)
    p.add_argument("--rating-mode",choices=["neutral","synthetic-varied"],default="neutral")
    p.add_argument("--rights-confirmed",action="store_true",required=True)
    a=p.parse_args()
    if len(a.team)!=6 or len(set(a.team))!=6 or any(i<=0 for i in a.team):
        p.error("exactly six different positive provider team IDs required")
    try:
        catalog=Catalog(LOCAL/"catalog.sqlite3")
        snapshots=[catalog.read(i) for i in a.team]
        if any(s is None for s in snapshots):raise ValueError("Missing squad")
        server.init_db()
        print(json.dumps(server.new_catalog_league(snapshots,a.rating_mode)))
        return 0
    except Exception:
        print("League creation failed; check local squads and rights.",file=sys.stderr)
        return 1
if __name__=="__main__":
    sys.exit(main())
