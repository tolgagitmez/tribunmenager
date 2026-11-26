# Stage 132 — concurrent AV failure isolation
Stage 124 artifact: one match passed at 298.54 observed seconds, 7784 decoded
frames and zero dropped frames; other native report failed generically with
"Native live capture failed". Host CPU reached 100%, minimum available memory
about 13605 MiB. These observations do not identify root cause.

This stage holds an exclusive per-user display reservation across Xvfb capture,
disables Pulse client autospawn (each match already has a private server/socket),
and records allowlisted failure categories and runner exit code rather than
uploading raw logs or private manager URLs. Tests validate independent real
Xvfb displays. Full two-match validation retains all previous coverage and
control gates; a single-thread scaling retry is diagnostic and cannot turn a
failed default test green. No production capacity, no gameplay change.
