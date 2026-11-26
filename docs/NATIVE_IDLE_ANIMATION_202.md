# Stage 202 — native recovery command priority

The original ElizaController requests a native ball-control command
after previously generated on-ball commands. The animation selector
tries commands in queue order. A safe recovery input therefore does
not guarantee that the native moving ball-control candidate is tried
first. This is a source-level observation, not a demonstrated cause
of each stationary-carrier episode.

In the stage 201 safe-move path only, detect exactly one newly
appended native ball-control command, require movement, finite speed
1.2–3.5 m/s and direction dot product 0.85–1.001 relative to the
clearance-tested direction. Do not promote if any shot is queued.
Rotate the existing candidate to the front; retain all other
commands and their order. Native animation selection, touch geometry,
ball physics and clock remain unchanged. Log promotion on initial
recovery decisions only; queue promotion does not prove accepted
animation or actual movement.

Local isolated C++17 compilation (-Wall -Wextra -Werror) and execution
passed 10 predicate assertions and one vector rotation order assertion.
The 10 predicate tests were added to the repository's cumulative
attack-policy-test.cpp. The upstream ball-control insertion anchor
was found exactly once in the pinned source. The complete patched
engine and a real stage 202 match were not compiled/run in this turn.
The currently running stage 200 workflow, PR #75, is unchanged.
This is a private diagnostic candidate, not a production release.
Main unchanged.
