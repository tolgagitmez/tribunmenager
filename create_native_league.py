"""Operator-only create a new native-only development league; no web API toggle."""
import argparse
import json
import os
from pathlib import Path
import server
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('database',type=Path);p.add_argument('--manager',default='Deneme Menajeri')
    a=p.parse_args()
    if os.environ.get('TRIBUN_NATIVE_ONLY_LEAGUE')!='1':p.error('Explicit opt-in required')
    target=a.database.resolve()
    if target.is_relative_to(server.ROOT):p.error('Database must be outside static web root')
    server.DATA=target
    server.init_db()
    print(json.dumps(server.new_league(a.manager,native=True),ensure_ascii=False))
if __name__=='__main__':main()
