# Stage 198 — per-match diagnostic evidence

The actual stage 191 PR #74 workflow (run 45898537238) has passed the
full native engine build. At the latest inspection the baseline match
is in progress, the experimental match and final evidence validation
are pending, and the artifact list is empty. No real match football
statistics or runtime failure logs are available.

The existing workflow uploaded diagnostics only after both matches and
the evidence gate. Inserted two distinct upload steps, immediately
after each attempted private match, including on match failure if
the build succeeded. Archive only the selected report, game log and
native trace, with seven-day retention. No session-key file, league
database, or entire private directory is included. Missing files warn;
uploads do not establish a successful match. The final existing
evidence gate remains mandatory.

Read-back static checks verified step ordering, distinct artifact names,
and explicit trace paths. The changed workflow has not executed;
the currently running stage 191 workflow cannot retroactively use it.
No new gameplay changes, no restart or modification to the active PR,
and no merge to main.