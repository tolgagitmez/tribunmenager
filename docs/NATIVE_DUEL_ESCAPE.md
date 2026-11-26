# Stage 184 — momentum-aware native duel escape

Private opt-in descendant of stage 183. Reuse native DuelTrial and native
dribble direction selection. For each candidate direction and quantized
speed fraction, estimate reachable player positions at 150, 300, 450,
600 ms using current velocity and an agility-dependent exponential
velocity transition. Compare with nearby defenders' linear predicted
movement, reject paths near pitch boundaries or with insufficient
progress, clearance or facing alignment. Score forward progress,
minimum clearance and separation from the named defender. Require
an improvement of 0.45 over the native candidate's score; retain
native speed caps and existing trial cooldown. This is a heuristic,
not physical trajectory prediction, and does not create new animations
or guarantee a feint. Existing shielding and passing decisions remain.

The experiment is off by default; TRIBUN_AV_DUEL_ESCAPE=1 enables
it through the idle-recovery private match path, exclusive of stages
181–183 flags. Report started, progressed, lost, cancelled and unresolved
experimental trials. Progress is a native sampled criterion: retained
control, at least 2m advancement and at least 1m past the named defender
with separation >=1.5m. Reset cancellations may not log an outcome.
Baseline has no experimental trials; compare general match metrics,
not raw trial counts. CI configured for two independent private matches.

The two isolated C++ functions and 12 assertions were copied into a
standalone file, compiled locally with C++17 -Wall -Wextra -Werror
and all passed. Full native patch/build and real matches not verified;
Python parser tests added, not run locally. Main and Windows launcher
unchanged. New native build required.
