# Stage 130 — persistent league AV pilot
The existing 24-hour scheduler remains authoritative. With TRIBUN_NATIVE_AV_QUEUE=1
it transactionally queues the same due frozen league fixtures in a separate SQLite
table. Default off. A separate explicit CLI invocation can claim and execute one
private audiovisual match using a passing same-host capacity report. It does not
start automatically, publish URLs, or modify official fixture scores, standings,
season state or transfers. Results require real native trace, clock, HLS/audio,
browser completion and two manager diagnostic acknowledgements. These automated
commands are test inputs, not actual authenticated user decisions. Reservations
survive restarts and are not automatically reclaimed after a crash, to avoid
duplicate matches. Operator recovery, continuous workers, authenticated live
manager transport and authority cutover remain pending. Do not enable publicly.
