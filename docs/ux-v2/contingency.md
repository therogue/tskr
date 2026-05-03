# Contingency — Keeping the Epic in Sync with `main`

## Sync cadence

- After **every merge to `main`**: `git fetch origin && git merge origin/main` into `feat/86-ux-revamp`. No rebase — preserve history.
- Fallback if main is noisy: **weekly Monday sync**.
- Owner: whoever holds the epic branch at the time.

## Per-sync checklist

1. Resolve merge conflicts (concentrated in `App.tsx`, `App.css`, `TaskList.tsx`, `ChatInterface.tsx`).
2. Run `pnpm test:unit && pnpm test:e2e` with master flag **OFF** → must pass.
3. Run same suites with master flag **ON** → failures mean the v2 path needs porting.
4. Push merged epic. Sub-issue PRs rebase automatically.

## Drift handling by change type

| `main` change | Action |
|---------------|--------|
| New backend endpoint / schema (no UI) | Add regression test for the new endpoint to baseline suite. No v2 port needed. |
| New UI on a screen **not** rewritten (SettingsModal, QuickEntry) | Merge brings it for free. Add test if none shipped. No v2 port. |
| New UI on a screen **we are rewriting** (App.tsx, TaskList.tsx, ChatInterface.tsx) | Port to v2 path. Open follow-up commit `Issue 86 - Port <feature> into v2`. Add to translation matrix. |
| Conflicting refactor | Take v2 rewrite as base; re-apply main's intent on top. Document in merge commit. |
| Hotfix / CVE | Cherry-pick into epic immediately. |

## Pre-final-merge checklist (`feat/86-ux-revamp → main`)

- [ ] `git diff origin/main..feat/86-ux-revamp --stat` — no surprise files outside `frontend/` and `docs/ux-v2/`
- [ ] Last main→epic sync within previous 24h
- [ ] `pnpm test:unit && pnpm test:e2e` green with flag OFF **and** ON
- [ ] Master flag default is `false` in shipped code
- [ ] Manual QA on fresh clone with `?ux_v2=1`
- [ ] All resolved questions confirmed (notes column follow-up filed, chat task-payload approach documented)

## Rollback plan

| Scenario | Action |
|----------|--------|
| Regression after epic lands on main | One-line PR flipping `ux_v2` default back to `false`. Code stays; users return to legacy path immediately. |
| Single v2 feature is the culprit | Flip that sub-flag default to `false` (e.g. `ux_v2.chat_overlay`). Rest of v2 stays on. |
| Cleanup | Remove legacy code + flags in a separate future PR once v2 has soaked. |
