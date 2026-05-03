# UX Revamp v2 — Overview

Epic issue: [#86 Revamp the UI/UX for better productivity](https://github.com/therogue/hakadorio-community/issues/86)

Design reference: `G:\Coding\Git\tskr\res\UI_UX\v2\samples\Hakadorio Chat.html`

Epic branch: `feat/86-ux-revamp`  
Baseline test branch: `chore/ux-v2-test-baseline` (merged to `main` first)

## Sub-issues

| Issue | Title | Branch | Status |
|-------|-------|--------|--------|
| [#87](https://github.com/therogue/hakadorio-community/issues/87) | Fixed width for tabbed views | `feat/87-fixed-width-tabs` | pending |
| [#88](https://github.com/therogue/hakadorio-community/issues/88) | Add productive widgets | `feat/88-widgets-panel` | pending |
| [#89](https://github.com/therogue/hakadorio-community/issues/89) | Chat panel covers widgets only when needed | `feat/89-chat-overlay` | pending |
| [#90](https://github.com/therogue/hakadorio-community/issues/90) | Suggestive chat follow-ups | `feat/90-suggestive-followups` | pending |
| [#91](https://github.com/therogue/hakadorio-community/issues/91) | Task detail modal on double-click | `feat/91-task-detail-modal` | pending |
| [#92](https://github.com/therogue/hakadorio-community/issues/92) | Task cards in chat | `feat/92-task-cards-in-chat` | pending |

## Key docs

- [Implementation plan](implementation.md) — per-sub-issue breakdown, carry-over matrix
- [Feature flags](feature-flags.md) — tiered flag scheme, runtime behavior, dev panel
- [Regression tests](regression-tests.md) — baseline inventory, how to run, per-PR additions
- [Contingency](contingency.md) — main-drift sync cadence, rollback plan

## Constraint

Backend is **untouched**. All changes are in `frontend/`.
