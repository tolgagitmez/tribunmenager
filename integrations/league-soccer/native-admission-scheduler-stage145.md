# Stage 145 — conservative local scheduling
Stage 137 native processes both exited 0, browsers both exited 1,
CPU p95 99.75%; no qualified concurrent slots. New opt-in supervisor
dispatches private diagnostic jobs from the existing durable queue, one
reservation per fresh pressure sample, with host-wide per-user flock and
atomic claims counting quarantines. Admission requires same boot/runtime,
affinity and cgroup configuration, report age <=1 hour, actual 295–305s
matches, successful browser playback, audio ownership, command evidence
and headroom. Group CPU <=80%, throttled periods <=5%, memory headroom
>=1024MiB; retain existing host gates. These are conservative provisional
thresholds. Benchmark group summary uses leaf samples; parent limits are
checked in live sampling for memory and CPU quota, not full ancestor
utilization. No GPU capacity yet, no automatic fallback, no official
fixture rescheduling, no cluster management or production qualification.
The scheduler uses diagnostic auto-command workers only. Do not run
legacy independent workers alongside it. Main unchanged.
