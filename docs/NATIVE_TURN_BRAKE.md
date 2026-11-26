# Stage 182 — turning and braking motion experiment

Opt-in private rendered descendant of stage 181. Apply a partial blend
toward the existing longitudinal/lateral traction limiter in the native
root-motion planner, after native acceleration and air resistance logic.
Straight acceleration has weight 0.35; stronger lateral or backward
requests up to 0.70. Agility, acceleration and balance are inputs.
Only AI outfield movement clips without touch or special states, away
from the ball (>2 m), in open play. Keep original end-of-clip velocity
quantization. No direct animation playback, foot pin, ball touch or
goalkeeper changes. Root-motion planning does change, so football
outcomes may change. Braking limits can also increase stopping distance.

TRIBUN_AV_TURN_BRAKE=1 is private opt-in, default off; cannot be combined
with stage 181 leg blend or the existing active motion-smooth planner.
Report actual sampled velocity changes (not speculative candidate plans)
away from ball for CPU players; exclude phase changes, gaps >250 ms,
duplicate timestamps and stoppages. Thresholds 3 m/s² and 45 degrees.
CI configured to run baseline and experimental matches; independent
fixtures are not necessarily identical seeded A/B samples. Compare
rates with interval denominators and football results; review turns,
stopping distances and video subjectively before promotion.

The two standalone functions copied from the patch and 10 assertions
compiled with C++17, -Wall -Wextra -Werror and ran successfully locally.
Full engine patch/build, report tests and actual matches not verified.
Main and Windows launcher unchanged; new native build required.
