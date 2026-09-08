# Trade Superstars — project conventions

## Commits

- When I say "commit", stage **exactly** the files relevant to the change we just
  made. Never `git add -A`, never sweep in unrelated files.
- Concise imperative message ("Add ingest adapter", not "Added..." / "This adds...").
- **Push after every commit.** "Commit" means commit *and* `git push` — I expect to
  see it on GitHub. Don't leave commits sitting locally.
- Show `git log --oneline` afterward, and confirm the push landed.
- Never commit `backend/.env` or any secret, key, or credential.

## Code style

- Concise and idiomatic. Match the surrounding code.
- Comment only non-obvious behavior — why, not what.
- No over-engineering, no speculative abstraction. Build what the task needs.

## Scope

- Do only what the current task asks.
- If a real architectural decision comes up, stop and ask. Don't decide it silently.

## Verify, don't assume

- When using an external API or data source, probe the real shape first — confirm
  field names, types, and units before relying on them.
- Prefer showing real output over asserting something works.
