# Stage 211 — repair of two standalone C++ fixture tests that blocked the native pilot job

Finding (GitHub Actions, "League-Soccer native pilot", job native-trace, step
"Python shadow queue tests"): all four runs on the stage 210 branch
(45905741649, 45905800722, 45905806653, 45905851116) failed at that step, so the
job never reached "Build pinned upstream and capture full match". The stage 210
rejection diagnostics therefore have not run on the real engine.

Reproduced locally with `python3 -m unittest discover -s tests -p 'test_native_*.py'`:
401 tests, 2 errors, both C++ compile errors
(`PressureHold185Enabled` was not declared in this scope) in
tests/test_native_hold_up.py::test_cpp_policy and
tests/test_native_activation_redesign.py::test_revised_gates_and_unchanged_success.
Identical failure at the stage 209 parent (caea60d). The symbol was introduced
by commit 710b807 (stage 185), which made HoldTrial::Ready reference it while the
two fixtures compile HOLD_UP_RULES alone.

Change: tests only. Both fixtures now declare `PressureHold185Enabled()` returning
false, the default of the real function (it needs TRIBUN_AV_PRESSURE_HOLD and
TRIBUN_AV_IDLE_RECOVERY). A stub returning true was tried first and failed the
tests' own assertions, so the closed gate is the faithful choice. No engine,
patch, selection, physics or match-duration code changed.

Local result: 401 tests OK. This only restores the Python test step. It is not
evidence about match quality; the real-engine validation of the stage 210
diagnostics still depends on the CI run after this commit.
