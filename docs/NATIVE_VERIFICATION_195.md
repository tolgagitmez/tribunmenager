# Stage 195 — stall comparison evidence

PR #74 run 45898537238 was still building the complete pinned engine
at inspection. Attempt to retrieve job 140178385868 logs returned
404 BlobNotFound. Local git ls-remote returned Could not resolve host.
No concrete compiler error or completed match was available. No changes
to the active PR, full engine source or main.

Extended the stage 194 read-only match comparison to distinguish
stationary controlled carrier episodes and longest duration, native
wall-clock gaps and longest duration, and carrier trace sampling gaps
from encoded-image repetition. Only complete carrier/clock observations
are compared; absent or errored observations remain null. Counts must
be nonnegative integers and zero count must agree with zero duration.
These are distinct observational signals, not proof of a deadlock or
causal improvement. Four new synthetic cases plus five prior cases ran
locally: 9 passed. No real match results yet.
