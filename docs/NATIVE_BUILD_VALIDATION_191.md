# Stage 191 — native build and evidence validation

No football behavior changes. Main is untouched. Stage 190 had no
returned combined commit statuses or PR workflow runs; the connector
does not enumerate push workflow runs through its commit-run endpoint.
A direct local git ls-remote still fails DNS resolution. No full engine
build or new real match was performed locally.

The stage 190 evidence gate could pass even if diagnostic parsers
returned None without raising an exception, or both score fields were
missing. Require diagnostic objects (including stall carrier and
dribble touch/separation), valid two-team scores, valid nonnegative
integer sample counts, and explicit mode evidence. Missing diagnostics
are listed, not interpreted as successful execution. Empty objects are
allowed for inactive experimental modes; this is a presence/shape
check, not proof of every feature being exercised. Seven locally
reproduced Python regression tests passed, including three new tests.
The cumulative policy source contains 342 assert occurrences, not a
verified execution count.

The new workflow is triggered by PR targeting the stage 190 experimental
branch, captures actual policy/engine compiler logs with pipefail,
and attempts the experimental match if the engine built even when the
baseline match fails. No automatic main merge or deployment.
Independent fixtures do not guarantee matched seeds. A completed
workflow and real match evidence remain necessary before promoting
the experiments.