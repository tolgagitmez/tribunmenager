# Stage 192 — offline native policy preflight

The stage 191 PR #74 native build workflow (run 45898537238) was queued
at inspection. No completed compiler or match results were available.
Local git access to github.com still failed DNS resolution.

The pristine upstream aitactics.hpp is copied verbatim from pinned
revision 087414cde936c3e26ed0b8c244d9d85425ec5657 (Apache-2.0 upstream,
original notice retained; Git blob 15754f92c9f9bcdf8563cf67202f418b74a46739).
Run python3 integrations/league-soccer/native_policy_preflight.py on a
checkout of this project with Python 3 and a C++17 compiler. It verifies
revision/blob, replays direct literal header edits and compiles the
actual repository attack-policy-test.cpp with assertions enabled,
then executes the binary. It uses no upstream clone, CMake, rendering
or graphics/audio dependencies. This is NOT a full native engine build.

Static independent replay of the current 28 header edits succeeded;
the test file's 48 distinct capitalized call names were present in the
patch source (lexical check only). Five local synthetic Python replay
and hash tests passed. The complete new preflight has not been executed
locally against the full repository patch/test files, nor has the
342-assertion C++ executable or real match been verified. A separate
workflow is configured. Header replay supports the current direct edit
pattern, not arbitrary dynamic Python patch operations; full native
patch/build remains mandatory. Existing PR #74 and main remain unchanged.
