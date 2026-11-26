# Stage 151 — version-bound deployment review
Stage 150 setup contracts and audio isolation passed; real fixture still
pending at review time. Stage 138 two concurrent matches failed; do not
promote. Fix transient startup race in native league manager panel (bounded
retry for 404/409/503/network failure, no retry of authorization denial).
New diagnostic release binding requires clean tracked Git state, exact
commit, runtime manifest and executable hashes, same boot/cgroup/CPU
identity and one-hour freshness. Full league E2E and same-host qualified
capacity for at least three simultaneous matches (available tier four)
are required for private round review. Optional hardware match checks
are separate, not capacity proof. Unsigned local evidence is not CI
attestation; no authority or security approval. Commercial rights,
public security and authoritative cutover remain explicitly blocked.
CI reruns actual one-match rehearsal, then verifies gate refuses release
without capacity and rights. Hardware/rights stamps require an actual
runtime, and cannot unblock production. No main change.
