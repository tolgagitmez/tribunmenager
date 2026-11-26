# Stage 208 — safe primary runner trigger

Stage 200 actual CI run 45901946530 completed both matches but failed
the coordinated evidence gate. Both matches scored 0–0. Lanes vs
coordinated: shots 4/6, on target 1/2, completed passes 48/38,
controlled box entries 2/2, controlled box time 2600/2200 ms,
stationary carrier episodes 7/18, longest 3400/4900 ms.
Each report contains one sampled secondary run, no primary run;
coordinated report contains one unpaired sample, zero paired.
Fixture hashes differ; no causal improvement claimed.
Sparse selection records do not prove that no unsampled run happened.

Native primary attacking runs use a 500 ms trigger and aggregate
distance/density heuristic. In private coordinated mode only, if
the existing heuristic declines an otherwise selected runner,
test three local forward targets (4 m forward, lateral 0/−3/+3 m).
Require unique active AI carrier, current possession and last touch,
open play, no retainer, no triangle, eligible outfield runner, and
the existing safe depth, width, pass-distance, offside margin,
predicted opponent endpoint/corridor and teammate/run separation
thresholds. If a target qualifies, allow the original ApplyAttackingRun
path. The existing lane selection must still choose its own safe
target; this probe does not force a run direction or guarantee a
paired selection, contact or reception. Log alternate trigger only.
Old trigger and other profiles unchanged.

Actual local C++17 compilation/execution of exact helper and 16
assertions passed (-Wall -Wextra -Werror -UNDEBUG), also added to
attack-policy-test.cpp. Pinned upstream trigger anchor verified once.
Full engine and real matches for stages 206–208 not yet validated.
PR #76 stage 204 engine build already successful; matches in progress
at last check. No alteration to active PR or main.
