# Stage 140 — authenticated league control rehearsal
Private --league-control mode requires an additional internal gateway key
for both reading and writing tactics. The existing local capability alone
cannot control a league-mode match. The league endpoint derives team/fixture
from the token and current attempt and forwards through loopback; the key
is never returned to the browser. The private root must be outside the static
web root. CI uses the actual server HTTP handler with a disposable database,
two synthetic league accounts and a foreign-league account, a spectator-only
browser (no test auto-command), and two explicit authenticated commands to
the actual engine. Checks acknowledgement, duplicate retry, unauthorized
rejection and private season result. No actual user traffic or official scores.
The normal diagnostic queue still uses auto-command testing, not league mode;
the production worker and arbitrary command histories remain future work.
