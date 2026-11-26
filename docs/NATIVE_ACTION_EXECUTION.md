# Stage 175 — native action execution evidence

The experiment inherits stage 174 and uses the private CPU idle-recovery flag.
Observe the real native Humanoid selector: actual attempted candidate type and
accepted/rejected result for unique AI outfield possession. Record pass, shot
and controlled-dribble ball contact and missed touch geometry in open play.
Every record has phase, actual engine time, nominal match time, team and player.
Movement acceptance is not proof that the player moved. The trace is still
required to measure displacement. Candidate acceptance is not ball contact:
rejected candidates may simply be normal fallback behavior, and contacts may
occur after possession changes. Do not divide these counts to claim a
completion rate or attribute a particular contact to a particular candidate.
No event is not proof of a healthy engine; the selector may not have run.

The private match quality report provides bounded event details and full counts
from the game log. Missing logs are unknown; malformed action lines are counted.
CI runs the parser tests, applies pinned upstream patches, builds and runs a
private fixture, and retains the report and game log. Compare event times with
stage 173 carrier inactivity and stage 174 restart events. Specifically inspect
periods where the clock advances but the carrier is stationary: repeated
rejections, accepted animation followed by missed touch, and absence of
candidate events are distinct hypotheses, not proven causes. No forced
animation, physics, ball contact, queue priority, or production changes.
New native build required; Windows launcher remains at previous version.
