# Stage 206 — connect off-ball run targets to native lead-pass selection

Stage 200 baseline completed; stage 204 cumulative recovery build/test
runs separately. A selected off-ball target previously served only
the coordination logic. Save fresh reservations for both private
off-ball profiles, without enabling coordinated scoring in lanes-only
mode. The existing stage 186 native lead-pass candidate may now
consider a runner if its reservation matches receiver, carrier and
phase, is at most 250 ms old, and actual velocity is directed toward
the target. Estimated native lead target must be within 3.5 m of the
run reservation. Retain all pre-existing stage 186 requirements:
forward movement, onside margin, receiver distance, projected
defender clearance, pass corridor, minimum odds, reachable lead
target, and native tactical selection thresholds. Independent stage
186 flag remains supported. No forced pass or invented ball trajectory.
A new selection log distinguishes run-linked pass decisions; existing
timing contact log is enabled for these profiles too (it includes all
native long-pass contacts, not proof of this specific decision).

Local isolated C++17 test of the exact two new helpers and reservation
structure compiled with -Wall -Wextra -Werror -UNDEBUG and executed:
16 assertions passed. Added the same cases to attack-policy-test.cpp.
Full patched engine compilation and real matches for this stage have
not run. Existing PR #75 and #76 are unchanged; main unchanged.
The numerical eligibility thresholds are experimental, not tuned
or validated from a set of repeated real matches.
