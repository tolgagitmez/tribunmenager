# Stage 177 — missed native touch recovery

Experimental descendant of stage 176. Observe failed native pass/shot touch
geometry only for active AI outfield unique possession with last touch.
Log measured full distance, native contact radius, height difference,
body angle (radians), player and ball speeds, and animation contact frame.
Support-foot positioning and separate temporal alignment are not yet measured.
The original contact condition and animation, physics, referee remain unchanged.

Two distinct missed touch frames of the same attacking function within
1500 native ms can trigger the existing stage 176 queue reprioritization,
only when the stationary-carrier eligibility still holds and the same
function is first in the queue. Prioritize a different native short pass
or native ball control with movement; no candidate deletion or fabricated
touch. If none is available, keep the original queue. Reset missed history
on observed possession loss, phase change, expiry, successful pass/shot/
controlled contact, or ResetSituation. Retry promotion consumes the streak
and applies a 500 ms cooldown. Logs are observations, not proof of a cure.

The standalone extracted MissedTouchWatch and assertion sequence compiled
with C++17 and passed locally. Full engine patch/build and private fixture
are not yet verified. Python parser tests added to CI, not yet run locally.
Inspect rounded geometry and correlate touch retry, subsequent actual
contact and measured player displacement in native trace. Retry promotions
are a subset of ordinary alternative promotions, not extra actions.
No main promotion, no Windows launcher change; new native build required.
