# Stage 204 — cumulative idle recovery full-engine validation

Stages 201–203 are now scheduled for integrated CI on a separate branch:
sustained safe movement, guarded native ball-control queue priority,
and forward/continuity direction scoring. No new gameplay edits in 204.
An isolated C++17 executable copied from the fetched combined helpers
and regression block compiled with -Wall -Wextra -Werror -UNDEBUG and
executed successfully. The block contains 37 assert statements,
including a loop. This is not a full engine build.

The workflow targets stage 200, retains both explicit private profiles
(lanes and coordinated), full patched policy compilation, actual native
build, per-match archives, and the strict evidence gate. It additionally
runs native_compare_194.py on the two completed reports, prints the
result and preserves idle-comparison.json. Both matches use the same
new recovery code: this is not an isolated recovery-off/on comparison.
Compare against earlier stage 200 reports only with fixture provenance
and appropriate caution. No causal improvement or release claim.

Observed PR #75 run 45901946530: full engine build succeeded; baseline
match still running and experimental match pending, with no artifacts
at last check. This workflow remains unchanged. Stage 204 tests are
requested by a separate draft PR, main remains untouched.
