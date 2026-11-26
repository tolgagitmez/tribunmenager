# Stage 189 — coordinated native run destinations

Private opt-in extension of stage 188. TRIBUN_AV_COORDINATED_RUNS=1
requires TRIBUN_AV_OFFBALL_LANES=1. A team stores the primary and secondary
runner's most recent selected start and target coordinates, carrier ID,
phase and native time. The other runner's reservation is valid for at
most 250 ms, with matching carrier/phase and different player identity.
In eligible stage 188 candidates, reject endpoint separation below 4 m
or synchronized straight-line path samples at 50% and 75% below 2.5 m.
Add bounded preference for separation and distinct lateral lanes.
Only selected native force-field attraction targets are stored.
If no safe candidate is found, retain ordinary native fallback; this is
not a hard physical collision rule. Evaluation order, stale data inside
the time window, force-field forces and different actual arrival times
can still result in overlapping movement. No actual defender attraction
or explicit decoy/overlap role has been implemented. No new animations,
ball physics, or forced runs.

Reports separate paired and unpaired sampled selections, not completed
runs. Baseline uses stage 188, experimental adds the reservation policy.
CI configured for independent matches, not verified identical seeds.
Full cumulative patch/build and real matches not verified.
Locally reproduced exact reservation and scoring functions compiled
with g++ -std=c++17 -Wall -Wextra -Werror; 16 assertions passed.
Locally reproduced parser and its two unit tests also passed.
Main unchanged. Next priority: validate cumulative native build and real
match evidence before extending the experimental behavior.
