// Theme hook for v2 (ux_v2=true + ux_v2.theme_toggle=true).
// Reads/writes localStorage['theme'] and toggles document.documentElement.dataset.theme.
// Defaults to dark. Under ux_v2=false the hook has no visible effect since the legacy
// CSS hard-codes values that don't respond to data-theme.

import { useState, useEffect } from 'react'

export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'theme'

function getStoredTheme(): Theme {
  if (typeof window === 'undefined') return 'dark'
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === 'light' ? 'light' : 'dark'
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(getStoredTheme)

  useEffect(() => {
    applyTheme(theme)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  function toggle() {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark')
  }

  return [theme, toggle]
}
