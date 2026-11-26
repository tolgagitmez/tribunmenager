# Stage 179 — paired native foot metadata and contact timing

Private CPU-only experiment descended from stage 178. For accepted native
pass/shot animation while a unique AI outfield ball carrier is observed,
store selection time, phase, animation ID, function and contact frame.
Clear on subsequent accepted selection, observed audit scope exit, native
ResetSituation, mismatched animation/phase, or expiry (2000 ms).
Only a matching actual contact frame emits a paired sample. Record elapsed
native time, original spatial foot state, animation current/outgoing foot
labels, authored touch body-part side and original geometry check result.
The original contact distance/height conditions remain unchanged.

Foot labels are engine metadata, not world-space sole or support-foot
coordinates. In particular spatialState.foot can represent outgoing foot
from a previous animation; no claim of planted-foot detection or IK.
No extra animation selection, forced contact, changes to foot preference,
or animation speed. Unpaired/canceled selections are not in the paired
sample denominator. Geometry pass is not pass completion. Compare paired
timings and foot labels by action and geometry result before adjusting
the engine. Next capture before/after preparation pose and synchronized
world-space foot motion, verifying render/simulation frame alignment.

A manually reproduced standalone C++17 watchdog test passed 12 assertions
locally. Full patch application, build, parser tests and real private
match are not verified here. CI configured. Main and Windows launcher
unchanged; new native build required.
