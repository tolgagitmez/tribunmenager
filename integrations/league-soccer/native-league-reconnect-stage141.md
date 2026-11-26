# Stage 141 — repeated manager commands and reconnect
The authenticated read endpoint exposes only its own side's latest request ID,
pending values, submitted/applied counters and last engine acknowledgement.
Read snapshot is locked. Retry the same request ID after disconnect; no
automatic duplicate engine command. The worker must remain alive; this is
client reconnect, not engine process recovery. League verification recomputes
the full native command history from the trace and recorded request values.
Zero or multiple commands per side are accepted if consecutive, valid and
acknowledged; unresolved commands fail closed for now. Local benchmark keeps
its strict two-command diagnostic contract. CI exercises two revisions per
team, no formation change on second command, reconnect and duplicate retry.
No main or official results changed. Real manager traffic and process crash
recovery remain unqualified.
