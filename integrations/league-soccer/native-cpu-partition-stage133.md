# Stage 133 CPU partition diagnostics
Opt-in taskset partitions available logical CPUs between each match's native
and browser descendants, minimum two logical CPUs per match. This is not a
CPU reservation from other host tasks, and logical CPU siblings may still
share physical cores. Capture resolution, encoder CRF, target FPS, audio
and native clock unchanged. A bounded scaling worker is used in this test;
the combination is diagnostic, not a controlled comparison of either change.
Sample cgroup v2 quota, memory, usage and throttling when available; missing
telemetry is not evidence of no throttling. The cgroup may contain unrelated
processes. Admission explicitly rejects the partitioned experimental profile.
No main branch or official result change.
