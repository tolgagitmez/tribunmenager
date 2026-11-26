# Stage 200 — real match failure diagnosis and profile forwarding fix

Observed GitHub Actions run 45898537238 (stage 191, PR #74):
full CMake build and both private five-minute matches succeeded, but
the final evidence gate failed. Actual report data from job logs:

| Metric | Intended lanes | Intended coordinated |
|---|---:|---:|
| Score | 0–0 | 0–0 |
| Real match seconds | 299.9534 | 299.9308 |
| Shots | 6 | 2 |
| Shots on target | 1 | 1 |
| Passes / completed | 50 / 34 | 62 / 43 |
| Controlled box entries | 3 | 1 |
| Stationary carrier episodes | 12 | 7 |
| Longest stationary carrier (ms) | 37000 | 12100 |
| Native clock wall gaps | 0 | 0 |
| Dropped browser frames | 0 | 0 |
| Longest identical reduced image (s) | 3.4 | 3.4 |
| Offball selections / coordination records | 0 / 0 | 0 / 0 |

The root configuration defect is in native_alpha.clean_env: it
correctly strips all inherited TRIBUN_* flags, but the CI relied on
those inherited flags to select the experiments. Both launched matches
therefore ran without the intended offball/coordination profile.
The final gate correctly rejected missing lane evidence (both), and
missing coordinated evidence (second). Differences are not causal or
matched-fixture proof. Long stationary carrier episodes still require
separate targeted improvement. No clock gaps were observed.

Fix: explicit Linux private CLI --native-attack-profile
(default/lanes/coordinated) passes to native_alpha --attack-profile.
Only match launch receives the allowlisted two flags. All build and
ordinary launch environments still strip inherited experimental flags.
Nondefault profiles reject prepare-only, WSL GPU and the remote Windows
launcher. CI selects the two profiles explicitly; no relaxed gate.
Five local tests using the exact copied clean_env/match_env helpers
passed. Full repository and end-to-end profile routing still require
CI execution. The native engine source itself is unchanged in this
stage, and the full game is not yet qualified. Main is untouched.
