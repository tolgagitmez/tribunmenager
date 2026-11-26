# Stage 185 — pressure hold and safe outlet

Experimental descendant of stage 184. Reuse native hold-up trial and short
pass selection. Compare current movement decision with seven candidate
directions around facing; forecast reachable positions at 150, 300, 450
ms using stage 184 reach-time heuristic. Rate predicted clearance from
nearby opponents, facing alignment, movement away from the nearest threat,
forward progress and clearance gain. Reject clearance below 0.95 m,
backward progress beyond 0.65 m, or unsafe pitch margins. Require score
improvement >0.30 and native quantized speed at least 1 m/s and at most
48% of sprint speed. Retain original hold eligibility and native movement
and touch selection. No forced body rotation, collision changes or new
shield animation.

Private mode permits an eligible support pass during trial stage 1 as
well as stage 2, without requiring the 400 ms held milestone. Use existing
native pass odds, receiver space, offside margin and original ranking,
including private fallback offside calculation when running-pass policy
is disabled. Log start, held, released, received, lost and cancelled
events. Unlogged resets or shots can leave unresolved observations.
Early release is not a failed hold; reception needs native possession
confirmation. No guaranteed physical body shielding.

TRIBUN_AV_PRESSURE_HOLD=1 private opt-in; default off; exclusive of
stages 181–184 private flags. CI configured for separate baseline and
experimental private matches; no matched seed guarantee. Compare
possession, retention, progression, successful native passes and video
before promoting.

PressureShieldScore copied verbatim into standalone C++17 test, compiled
with -Wall -Wextra -Werror and executed successfully (12 assertions).
Full native patch/build, parser tests and actual matches are unverified.
Main and Windows launcher unchanged. New native build required.
