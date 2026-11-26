# Stage 152 — private single-fixture diagnostic launcher
Stage 150 failed at browser media-authorization assertion after build.
A foreign native account resolves its own future fixture (409), not the
active fixture in the other league. Anonymous requests remain 403.
Test exact status and separate active attempts; no authorization loosening.
Retry temporary playlist startup errors in league mode. Actual E2E rerun
required; old report lacked HTTP status so diagnosis is code-based.

Linux, prepared runtime, Chrome/Playwright installed (npm ci and npx
playwright install --with-deps chrome), required engine dependencies.
Example only (paths must be real, private, and output must not exist):
```sh
python3 integrations/league-soccer/native_private_beta.py /private/runtime /private/test-152 --private-diagnostic
```
Open printed local login URL, paste token from private manager-session.txt.
One match starts after 60 seconds. Host-pressure check and worker lease
required; explicit single diagnostic reservation is NOT capacity
qualification. Other two games remain queued. Browser verifier uses
local spectator while operator may watch and change tactics separately;
extra browser adds load. No automatic replay, no remote access, no
commercial or general beta publication. Output contains private media;
keep outside static root, do not upload or redistribute. Main untouched.
