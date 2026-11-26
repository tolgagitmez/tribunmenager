# Stage 197 — attack intensity evidence

Existing native attack-report.cjs already samples controlled time in the
attacking third and box, forward/backward same-carrier displacement and
box crossings. Preserve these values and derived ratios in
native_match_quality.py, rather than relying on shots and goals alone.

The new helper reports per-team attacking-third and box shares of
observed controlled time, controlled box crossings per shared sampled
open-play minute and net forward displacement per same-carrier minute.
Zero denominators produce null. Invalid counts, nonfinite movement
and inconsistent subset times are rejected. These are sampled measures
of existing motor telemetry, not individual dribble counts or evidence
of causation. No new match AI behavior.

Six tests of the helper ran locally with Python unittest and passed.
Repository integration and actual new reports are not yet verified.

PR #74 / Actions run 45898537238: full build succeeded; baseline private
match remains in progress; experimental match and evidence gate pending.
Artifact list was empty at last check. No match statistics can be
reported yet. The running workflow uses stage 191 code and is unchanged;
new report fields will only appear in runs using stage 197. Main unchanged.
