# Stage 209 — attack integration, recovery rollback after failed real match

Stage 204 baseline actual archived report (run 45903395880, artifact
15156694798) returned passed=false / RuntimeError. Native clock reached
300000 ms, wall duration 300.1077 s, score 0–0, one shot (on target),
one controlled box entry, 12 stationary episodes, longest 49200 ms,
zero native clock gaps and zero dropped browser frames. Report
contains zero sampled run targets. The exact RuntimeError cause is
not established by the report alone. Game log contains 62 safe-move
requests and 62 sampled stage 202 queue promotion records. Neither
proves motion. During the long second-half episode player 20 retained
unique control and was almost stationary, frequently facing away from
the attacking direction. The stage 200 lanes match had 3400 ms longest
stall, but fixtures are not verified matched; the differences do not
prove the stage 201–203 policy caused the regression.

To avoid accumulating unqualified recovery modifications, restore the
exact stage 200 stage-172 code region in the new experimental branch.
Remove the tests specific to stages 201–203 only; original idle tests
and all stages 206–208 attack changes remain. The stage 204 branch
and its in-progress second match are unchanged.

Actually compiled and ran the isolated combined C++17 run-reservation,
box-finishing, and primary-run helpers with 48 assertions copied from
the repository, using -Wall -Wextra -Werror -UNDEBUG; exit 0.
This is not a full integration test. New workflow requests the full
pinned build and two private lanes/coordinated matches; both include
the attack changes, neither includes the stage 201–203 recovery code.
No causal A/B claim. No main merge or production qualification.
