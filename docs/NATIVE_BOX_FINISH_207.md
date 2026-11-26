# Stage 207 — controlled central-box finishing

The private off-ball profiles do not automatically enable the old
experimental finishing switch. Add a bounded shot candidate in these
profiles only: open play, AI-controlled active outfield carrier, unique
possession, designated possession and last touch, no retainer, low
nearby ball. Central box geometry, technical shot skill and the
native untransformed shot odds must pass the new helper. Compare the
native shot odds to the best current pass odds (0.10 tolerance).
A qualifying native shot is prioritized within the existing on-ball
queue; all other commands remain available. Existing RNG, aim, power,
animation selection, touch geometry and ball physics are preserved.
The threshold is a heuristic, not a calibrated probability of scoring.
No forced shot contact or goal. Sampled decision logs do not imply
actual execution.

Executed an isolated C++17 executable containing the two exact helpers
and 16 assertions, compiled with -Wall -Wextra -Werror -UNDEBUG.
All assertions passed. Same assertions added to attack-policy-test.cpp.
Full patched compilation and real match validation for stages 206–207
are still pending. Existing PR #75 and #76 kept unchanged; main untouched.
