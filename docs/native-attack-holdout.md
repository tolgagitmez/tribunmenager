# Pilot 38 — same-runtime held-out retest
The pilot 37 review unit tests passed (run 45724811356). Historical retention, box-run, and timed-attack experiments are still executing actual matches; do not select a winner before reports exist. The holdout runner accepts historical reports, recomputes the screening results, then uses a single shared control for each of three new fixtures (seeds 91001–91003) and isolated candidate profiles. It verifies exact fixed ticks, actual timed contacts, fixture SHA, binary SHA and runtime manifest SHA for every match. A changed input aborts the comparison. Incomplete samples remain incomplete. No eligible historical policy means zero matches are launched. Even a positive holdout result requires a separate interaction test and manual release review; no flag combination or production activation.
After historical artifacts are available, from repository root:
```bash
TRIBUN_INSTALL_NATIVE_DEPS=1 TRIBUN_PREPARE_ONLY=1 TRIBUN_NATIVE_RUNTIME_OUT=/tmp/holdout-runtime bash integrations/league-soccer/run-pilot.sh /tmp/holdout-unused.ndjson --demo
node integrations/league-soccer/attack-holdout-fixtures.cjs /tmp/holdout-fixtures
python3 integrations/league-soccer/attack-holdout.py /tmp/holdout-runtime /tmp/holdout-fixtures /tmp/holdout-results --retention /path/to/retention.json --box-runs /path/to/box-runs.json --timed-attack /path/to/timed-attack.json
```
Supply only available reports; one timed-attack pair does not pass historical screening. Do not run redundant expensive jobs until original results are available. Unit workflow tests the selection and provenance contracts only. No native gameplay changes or new release fingerprint in this step.
