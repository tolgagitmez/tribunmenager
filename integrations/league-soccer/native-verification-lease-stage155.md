# Stage 155 — managed lease across verification
Stage 154 fixture lifecycle unit tests passed. Stage 152/153 actual
native league tests and Stage 143 concurrent benchmark still running
at review. Avoid duplicating the long real-match workflow until evidence
returns. Existing run_match renewed only while both child processes were
running, and once just before verification. A slow fixture adapter,
trace verification or child cleanup could outlive the 30-second lease.
A background guard renews the same managed attempt every five seconds
during launch, child processes, cleanup and verification. If renewal
fails, stop admitting that result; check lease again on successful exit.
The final transaction still fences attempts. Does not resurrect expired
leases, change TTL or replay a match. Unmanaged diagnostics unchanged.
Contract tests use mocked renewals and actual existing recovery tests;
not proof of real match, capacity or production. No main change.
