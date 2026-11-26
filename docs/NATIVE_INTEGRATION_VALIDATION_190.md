# Stage 190 — cumulative native integration validation

No new football behavior. Descendant of stage 189; main remains unchanged.

## Performed checks
- Fetched the pinned upstream source via GitHub connector and replayed 190 direct literal/constant-concatenated edit pairs in sequence across nine files: aitactics.hpp (28), humanoid.hpp (5), humanoid.cpp (36), humanoidbase.hpp (1), humanoidbase.cpp (9), elizacontroller.cpp (62), teamAIcontroller.hpp (13), teamAIcontroller.cpp (31), AIsupport/AIfunctions.cpp (5). Every checked anchor matched exactly once. This independent static replay does NOT cover all patch files, strategy loops, fixture/instrument transformations, or C++ type checking.
- Re-ran 13 available standalone local stage executables and the two stage 189 parser tests. All exited successfully. These binaries are isolated prior tests, not a cumulative patched engine.
- Executed four local Python tests of the new evidence gate using synthetic reports. All passed.
- Attempted git ls-remote of pinned upstream; DNS resolution failed. No full checkout, patch-only script execution, patched header compile, full build or new real match was possible locally.

## Changes
TRIBUN_POLICY_ONLY=1 runs the complete patched attack-policy executable and diff check before CMake/dependency installation; existing TRIBUN_PATCH_ONLY behavior remains available. New workflow runs full preflight then full engine build and two separate private matches: stage 188 lane baseline and stage 189 coordinated mode. Evidence gate requires successful private match, consistent score, complete five-minute clock and playback, no recorded diagnostic exceptions, valid lane evidence and correct observed coordination mode. Missing paired samples are insufficient evidence, not automatically a gameplay bug. Both profiles' results and logs are archived where available. A failure or missing report cannot silently pass the new gate. The fixtures are not guaranteed identical seeds; this does not prove causal improvement. CI configuration is committed, execution and outcome unverified. No production promotion.
