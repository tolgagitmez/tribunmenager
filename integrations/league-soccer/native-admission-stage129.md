# Stage 129 — conservative admission policy

This is a diagnostic FIFO/reservation library and a CLI dry-run, not a public
scheduler or process supervisor. No production fixtures are launched. Without
a same-boot, same-runtime, same CPU-affinity-count, same default software
profile passing report, admission is zero. Hardware paths stay explicitly
manual until actual device and multi-match evidence exist.

Thresholds are provisional diagnostic policy: CPU p95 and current CPU <=85%,
at least 1024 MiB available memory and 2048 MiB free disk. They are not
production capacity or cgroup-aware guarantees. Evidence is trusted local
diagnostic output only, not a signed authorization. No cross-host inference.
Capacity report is now tagged with the host boot hash, runtime manifest digest,
logical CPU count and video profile. Earlier reports lack these fields and are
not automatically accepted. Re-run on the intended host.

Example after a benchmark on the same host:
    python3 integrations/league-soccer/native_admission.py /path/to/runtime /path/to/output --evidence /path/to/capacity-report.json -- match-1 match-2 match-3

The queue requires an explicit release per completed reservation. The CLI only
prints proposed admissions. Next: integrate authenticated durable job state
and bounded workers with cgroup-aware metrics, retry/expiry and season authority
before allowing production fixtures. Main and gameplay remain unchanged.
