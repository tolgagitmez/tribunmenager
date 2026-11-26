# Stage 142 — worker crash fencing
Stage 136 completed both native processes (exit 0), both browsers failed
(exit 1); host CPU p95 99.75%. Capacity aggregation encountered missing fields.
Do not infer successful concurrent playback. Report allowlisted missing
evidence fields and browser failure category.

Managed diagnostic worker claims get a 30-second renewable lease, checked
every five seconds while children run and before verification. Expired
attempts are marked failed and quarantined; a possible orphan must not
release capacity or publish scores. Old attempt completion is fenced.
No automatic restart or replay of a live match. Explicit cleanup after
verified host reboot is provided as a library operation only, for a
single-host database; same-boot quarantine requires further operator
cleanup tooling. Legacy unmanaged diagnostic claims remain for tests.
This is not a process-tree cleanup guarantee, production scheduler, or
native checkpoint/resume. No official score or main change.
