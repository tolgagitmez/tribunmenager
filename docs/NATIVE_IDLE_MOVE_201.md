# Stage 201 — bounded stationary-carrier recovery intent

Stage 200 actual match evidence showed stationary-carrier episodes lasting
37.0 s and 12.1 s while the native clock continued (zero clock gaps).
The stage 172 recovery requests were mainly safe-move (40 and 26).
Requests are not successful execution and cannot establish why a
specific carrier failed to move. Source inspection showed that safe
movement input was issued for one decision only, then the watch
waited 400 ms before issuing another request.

In the private IdleRecoveryEnabled path, keep a selected safe movement
request available for up to 300 ms. Require the current eligible
observation and repeat native opponent clearance and pitch-boundary
checks each decision; stop on unsafe opening, possession loss,
movement beyond existing watch limits, phase/time reset, or manual
movement. Preserve native ball control, movement selection, and the
400 ms interval for pass/clearance searches. No forced touches,
animation resets, changes to clock or release of production flags.
This is a candidate fix for discontinuous intent, not a demonstrated
cause of every stall or a verified gameplay improvement.

Executed isolated C++17 test with the exact revised IdleRecoveryWatch
and added assertions, using -Wall -Wextra -Werror; passed. Added the
same regression cases to attack-policy-test.cpp. Full engine and
actual match with this revision not executed. Local upstream git
DNS still fails. PR #75 run 45901946530 uses stage 200 and is left
unchanged to preserve the profile comparison. Main unchanged.
