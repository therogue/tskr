# Feature Flags — UX v2

## Flag IDs

| Flag | Default | Purpose |
|------|---------|---------|
| `ux_v2` | `false` | Master switch. OFF = old UI; ON = new UI. |
| `ux_v2.chat_overlay` | `true` (when master ON) | Chat slides as overlay over widget panel. False = chat renders inline. |
| `ux_v2.task_modal` | `true` (when master ON) | Double-click opens TaskModal. False = double-click is no-op. |
| `ux_v2.theme_toggle` | `false` (when master ON) | Renders sun/moon theme toggle in header. False = dark only. |

## Runtime precedence

URL query param → `localStorage['ff:<id>']` → default

Examples:
- `?ux_v2=1` — force master ON
- `?ux_v2=0` — force master OFF
- `?ux_v2.theme_toggle=1` — enable theme toggle without touching localStorage
- `localStorage.setItem('ff:ux_v2', 'true')` in DevTools

## Dev panel

Add `?ff=1` to the URL or open **Settings → Feature Flags** (dev builds only) to see a checkbox panel for all flags. Toggling persists to localStorage and triggers a live re-render via the `flag-change` CustomEvent.

## CSS gating

When `ux_v2 = true`, `data-ux-v2` is set on `<html>`. Legacy CSS values are scoped under `:root:not([data-ux-v2])`. New CSS variables apply globally via `:root` and are overridden per theme via `[data-theme="dark"]` / `[data-theme="light"]`.

## Behavior matrix

| `ux_v2` | `chat_overlay` | `task_modal` | `theme_toggle` | Result |
|---------|---------------|-------------|----------------|--------|
| false | — | — | — | Old layout: 50/50 flex split, collapsed strip, no widgets |
| true | true | true | false | New layout + widgets + chat overlay + task modal, dark only |
| true | false | true | false | New layout + widgets, chat inline, task modal, dark only |
| true | true | false | false | New layout + widgets + chat overlay, double-click no-op |
| true | true | true | true | Full v2: new layout + widgets + overlay + modal + theme toggle |

## Implementation

Source: `frontend/src/featureFlags.ts`  
Hook: `useFeatureFlag(id: FlagId): boolean`  
Debug UI: `frontend/src/components/FeatureFlagPanel.tsx` (appended to SettingsModal in dev/`?ff=1`)
