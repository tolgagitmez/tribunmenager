# Stage 203 — consistent safe forward recovery direction

Stage 201 sustained the recovery request for at most 300 ms and stage
202 prioritized a matching native ball-control command when no shot
was queued. Stage 203 addresses a potential oscillation: the earlier
controller selected the largest clearance independently each decision.

Among the existing five forward/lateral direction candidates, keep the
strict clearance >1.65 m and existing pitch-boundary checks. Score
finite candidates using clearance capped at 5 m, a 0.65 forward-direction
weight and a 0.8 alignment weight only while a recovery window is
active. A blocked direction cannot win; a sufficiently safer direction
can override the continuity preference. The prior direction is cleared
on recovery reset/stop. Native animation selection and ball physics
remain unchanged. The weights are experimental and have not yet been
tuned with real match evidence.

An isolated C++17 executable containing the exact scoring helper and
ten regression assertions was compiled with -Wall -Wextra -Werror
and executed successfully. Those assertions also appear in the
cumulative attack-policy-test.cpp. No full engine compile or real
match with stage 203 was performed.

Observed stage 200 PR #75 / run 45901946530: full engine build successful;
baseline match in progress; experimental match pending; no artifacts
yet. Keep that workflow unchanged for a clean profile comparison.
No merge to main.
