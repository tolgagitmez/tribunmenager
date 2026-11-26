# Stage 131 — private season ledger
The AV worker now recomputes the native participation sidecar and writes a
private result and player ledger in the same transaction as successful job
completion. Existing league scores, player state and transfers are untouched.
Team goals for/against, points, appearance minutes, fitness and card discipline
use the original native score/participation and the existing season rules.
Individual scorer/assist identity is not exported reliably and is not invented.
Older score-only records are not backfilled. Previous rounds must be complete
in the private ledger; a missing round blocks settlement. Unit tests use
synthetic evidence; real end-to-end queue execution remains blocked by failed
multi-match capacity tests. Capacity diagnostics now retain failure category
when a native or browser report is missing, not raw private logs.
