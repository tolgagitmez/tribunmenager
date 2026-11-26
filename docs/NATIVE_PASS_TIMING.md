# Stage 186 — native lead pass timing
Private opt-in descendant of stage 185. Uses native forced-target long-pass
lead delay and forward offset for a decision-time target estimate. Compare
receiver projected position at estimated travel time and nearby defenders
at four interior fractions of the pass path. Require progress 3–23 m,
distance 7–26 m, forward receiver speed >=1.6 m/s, onside margin >=1.5 m,
endpoint clearance >=2 m, corridor clearance >=1.4 m, native heuristic
odds >=0.76 and projected reach error <=1.8 m. Prefer only competitive
native long-pass candidates; original pass ranking, aim, power, actual
contact and physics remain native. Estimates are not guaranteed arrival,
offside clearance or calibrated probabilities.

TRIBUN_AV_PASS_TIMING=1 is isolated private opt-in, default off. Reports
selected command requests and all native long-pass contacts separately;
these are not paired or actual completed passes. CI configured for baseline
and experimental private matches, not guaranteed seed-matched. New wall
pass and one-touch mechanics are not implemented in this stage.

The three standalone C++ functions and 14 assertions compiled and ran
locally with C++17 -Wall -Wextra -Werror. Full engine patch/build, parser
tests and actual matches not verified. Local upstream clone failed due
to DNS resolution; GitHub connector writes succeeded. Main unchanged.
