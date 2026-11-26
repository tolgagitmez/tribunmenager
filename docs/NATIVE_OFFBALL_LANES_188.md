# Stage 188 — native off-ball lane requests

Private, default-off experiment using TRIBUN_AV_OFFBALL_LANES=1 with
idle recovery, fixed clock and a fixture. Reuse primary attacking runner
and secondary support assignment, native force-field attraction and
offside clamp. Exclude active combination/triangle runs. Compare candidate
lanes with up to 6 m forward and 5 m lateral target displacement.
Evaluate estimated arrival 0.35–1.5 s, moving defender positions along
both pass and run paths, and predicted teammate spacing. Preserve earlier
run-lane checks as an additional filter. Require at least 1.5 m onside
margin, 2.2 m endpoint clearance, 1.5 m pass corridor clearance, 3.5 m
teammate spacing and 1 m running corridor clearance. Opposite-side
preferences are not a guarantee of non-overlapping paths.

Arrival estimate is a bounded heuristic, not a physical guarantee.
The native runner remains free to follow other force-field influences.
No explicit decoy behavior or verified reception. Logs contain sparse
target selections, not actual completed runs. CI configured for private
baseline and experimental matches, not guaranteed matched seeds.

Standalone exact C++ policy functions compiled locally using g++ C++17
-Wall -Wextra -Werror and passed 16 assertions. Full patch application,
engine build, parser tests and real match remain unverified.
Main unchanged.
