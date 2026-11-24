"""Local operator-only import into the existing transfer catalogue."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from economy import TransferService, EconomyError
from tools.api_football_catalog import Catalog, LOCAL

ROOT = Path(__file__).resolve().parents[1]

def import_market(service, snapshots, rating_mode="neutral"):
    result = subprocess.run(["node", str(ROOT/"tools/api-football-market-export.cjs")],
                            input=json.dumps({"snapshots":snapshots,"ratingMode":rating_mode}),
                            text=True, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise EconomyError("Market adapter rejected snapshots")
    payload = json.loads(result.stdout)
    return {"imported":service.import_catalog(payload), "skippedUnknownAge":payload["skippedUnknownAge"]}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--team", type=int, required=True, action="append")
    parser.add_argument("--rating-mode", choices=["neutral","synthetic-varied"], default="neutral")
    parser.add_argument("--rights-confirmed", action="store_true", required=True)
    args=parser.parse_args()
    if not args.database.resolve().is_relative_to(ROOT) or not args.database.is_file():
        parser.error("use an existing local game SQLite database inside the project")
    if not 1 <= len(args.team) <= 20 or len(set(args.team)) != len(args.team) or any(i <= 0 for i in args.team):
        parser.error("provide 1-20 distinct positive verified team IDs")
    try:
        catalog=Catalog(LOCAL/"catalog.sqlite3")
        snapshots=[catalog.read(team) for team in args.team]
        if any(s is None for s in snapshots):
            raise EconomyError("Missing local squad snapshot")
        print(json.dumps(import_market(TransferService(args.database),snapshots,args.rating_mode)))
        return 0
    except Exception:
        print("Market import failed; existing catalog and owned players preserved.",file=sys.stderr)
        return 1

if __name__=="__main__":
    sys.exit(main())
