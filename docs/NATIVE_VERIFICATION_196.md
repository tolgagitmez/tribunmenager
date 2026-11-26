# Stage 196 — native match comparison provenance

Observed full engine build success on PR #74, run 45898537238.
Latest observed relevant steps:
- Build pinned engine: completed / success
- Baseline private match: in_progress / no conclusion
- Experimental private match: pending / no conclusion
- Validate real match evidence for both profiles: pending / no conclusion
No downloadable artifacts were returned during inspection. No actual football totals
or stall counts are available. The active PR was not modified.

The stage 196 branch preserves configSha256 and traceSha256 from the
already verified recording in successful private beta reports. Comparison
checks exact fixture equality and whether the trace hashes differ.
Missing values stay null; malformed hashes raise a validation error.
Exact fixture identity includes the seed and configuration, but does not
guarantee repeatability or establish causal improvement. Different trace
hashes alone cannot prove independent simulations. Older reports lack
these fields. Stage 191 running matches are not retroactively changed.

Three local isolated Python tests of the new identity/provenance
functions passed. Three repository integration regression cases were
added but the entire repository suite and updated private launcher
have not been run. Main unchanged. No new gameplay changes.
