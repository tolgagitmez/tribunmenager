# Stage 147 — isolated native-only development league
Explicit operator creation only, no conversion of an existing league:
TRIBUN_NATIVE_ONLY_LEAGUE=1 python3 create_native_league.py /private/dev.sqlite
The response contains a private manager token; do not publish it.
Mode persists in SQLite, immutable. Scheduler freezes due fixtures once,
uses private native results for previous-round readiness and player state,
and excludes legacy registry restore and live/local legacy endpoints.
Database fences block legacy operation/frame/season inserts and official
score updates; old shadow queue is excluded. Native-only worker uses
league-gateway control, spectator browser and no automatic tactics.
Private verified results project into the existing league status without
writing official fixture scores. Tests use synthetic result records, not
real AV matches. Production scheduler, authenticated media access, capacity,
licensing and live five-minute performance remain unqualified. No main change.
