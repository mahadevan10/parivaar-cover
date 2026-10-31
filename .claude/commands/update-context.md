---
description: Refresh the context docs for the folder you own from recent work
---

Update the project context docs so the next Claude session can pick up where this one left off.

1. Work out which area this developer owns: `frontend/` or `backend/`. Use the current branch prefix (`fe/` or `be/`) and the files changed. Only touch that area's docs.
2. Gather what changed: `git log --oneline -15`, `git diff main...HEAD --stat`, `git status --short`, plus anything decided in this conversation.
3. Update `<area>/CONTEXT.md` (create it with the same sections if missing):
   - Set the "Last updated" line to today's date and the current branch.
   - **Status**: what works now, what is broken or untested. Replace outdated lines, don't append history.
   - **Decisions**: add any new decision with a one-line why. Keep old ones unless reversed.
   - **Next**: the ordered list of what to do next. Remove finished items.
   - **Open questions**: add new ones, remove answered ones.
   - **Run**: commands, ports and env vars as they are now.
4. If the area has other docs (for example `frontend/docs/api-contract.md` or `frontend/docs/voice.md`) and the work changed what they describe, update them too.
5. In the root `CLAUDE.md`, only fill in or correct this area's row in the "Hackathon build" column of the tech stack table and this area's lines under "Running locally". Don't change anything else there.
6. Never edit the other developer's folder, `shared/` or `stage1_ppt/`. If something there looks out of date, list it in your reply instead.
7. Follow the product copy rules: short plain sentences, no dashes as punctuation.
8. Reply with a short summary of what you changed. Don't commit unless asked.

$ARGUMENTS
