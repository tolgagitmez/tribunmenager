# Stage 178 — bounded native body preparation

Private CPU-only experiment descended from stage 177. After two same-type
missed contacts within the existing watch window, and only if ordinary
stage 176/177 alternative promotion did not occur, inspect the first
attacking command's desired touch direction. Use the predicted ball at
100 ms and aim-relative target 0.45 m behind it. A copy of an existing
native movement candidate requests 1.2 m/s and looks toward the original
aim. Original commands remain in queue. No teleport, forced body
rotation, foot placement, contact or physics change.

Eligibility requires stationary unique AI outfield possession, a nearby
slow low ball, 0.12–0.8 m target adjustment, at least 2.2 m sampled/predicted
opponent clearance, pitch margins and poor body alignment or significant
adjustment. These are experimental thresholds, not verified optimums.
Consumes missed-touch streak and applies existing cooldown. Native selector
can still reject the request or choose an animation that does not achieve
the target. It does not schedule a guaranteed subsequent pass or shot.

Ten assertions for the isolated SafeBodyPreparation predicate passed with
local C++17 compiler. Full patch application, engine build, Python report
tests and actual match are not verified here. CI added on experimental
branch. Report preparation request counts independently of movement/contact.
Next measure actual body orientation and displacement before/after requests,
then actual subsequent contact; support-foot and animation blending remain
unverified. Main and Windows launcher unchanged; a new build is required.
