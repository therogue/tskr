// Feature flag system for UX v2 revamp (#86).
//
// Runtime precedence (highest to lowest):
//   1. URL query param:  ?ux_v2=1  or  ?ux_v2.chat_overlay=0
//   2. localStorage:     localStorage['ff:ux_v2']
//   3. Defaults below
//
// Usage:
//   const v2 = useFeatureFlag('ux_v2')
//   const chatOverlay = useFeatureFlag('ux_v2.chat_overlay')

import { useState, useEffect } from 'react'

export type FlagId =
  | 'ux_v2'
  | 'ux_v2.chat_overlay'
  | 'ux_v2.task_modal'
  | 'ux_v2.theme_toggle'

const FLAG_DEFAULTS: Record<FlagId, boolean> = {
  'ux_v2': false,
  'ux_v2.chat_overlay': true,  // enabled by default when master is on
  'ux_v2.task_modal': true,    // enabled by default when master is on
  'ux_v2.theme_toggle': false, // opt-in; dark only until explicitly enabled
}

const LS_PREFIX = 'ff:'
const FLAG_CHANGE_EVENT = 'flag-change'

function getUrlParam(id: FlagId): boolean | null {
  if (typeof window === 'undefined') return null
  const params = new URLSearchParams(window.location.search)
  const raw = params.get(id) ?? params.get(id.replace(/\./g, '_'))
  if (raw === null) return null
  return raw === '1' || raw === 'true'
}

export function getFlag(id: FlagId): boolean {
  const fromUrl = getUrlParam(id)
  if (fromUrl !== null) return fromUrl

  const fromStorage = typeof window !== 'undefined'
    ? window.localStorage.getItem(LS_PREFIX + id)
    : null
  if (fromStorage !== null) return fromStorage === 'true'

  return FLAG_DEFAULTS[id]
}

export function setFlag(id: FlagId, value: boolean): void {
  window.localStorage.setItem(LS_PREFIX + id, String(value))
  window.dispatchEvent(new CustomEvent(FLAG_CHANGE_EVENT, { detail: { id, value } }))
}

export function useFeatureFlag(id: FlagId): boolean {
  const [value, setValue] = useState(() => getFlag(id))

  useEffect(() => {
    function handleChange(e: Event) {
      const detail = (e as CustomEvent<{ id: FlagId; value: boolean }>).detail
      if (detail.id === id) setValue(detail.value)
    }
    window.addEventListener(FLAG_CHANGE_EVENT, handleChange)
    return () => window.removeEventListener(FLAG_CHANGE_EVENT, handleChange)
  }, [id])

  return value
}

// Check if the debug panel should be visible:
// - In development (import.meta.env.DEV), or
// - When URL contains ?ff=1
export function isDebugMode(): boolean {
  if (typeof window === 'undefined') return false
  if (import.meta.env.DEV) return true
  return new URLSearchParams(window.location.search).get('ff') === '1'
}

export const ALL_FLAGS = Object.keys(FLAG_DEFAULTS) as FlagId[]
