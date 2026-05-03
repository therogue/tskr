// Debug panel for toggling feature flags.
// Rendered inside SettingsModal when isDebugMode() returns true.

import { useState, useEffect } from 'react'
import { ALL_FLAGS, getFlag, setFlag, type FlagId } from '../featureFlags'

function FeatureFlagPanel() {
  const [flags, setFlags] = useState<Record<FlagId, boolean>>(() =>
    Object.fromEntries(ALL_FLAGS.map(id => [id, getFlag(id)])) as Record<FlagId, boolean>
  )

  useEffect(() => {
    function handleChange() {
      setFlags(Object.fromEntries(ALL_FLAGS.map(id => [id, getFlag(id)])) as Record<FlagId, boolean>)
    }
    window.addEventListener('flag-change', handleChange)
    return () => window.removeEventListener('flag-change', handleChange)
  }, [])

  function toggle(id: FlagId) {
    const next = !flags[id]
    setFlag(id, next)
    setFlags(prev => ({ ...prev, [id]: next }))
  }

  return (
    <div className="feature-flag-panel">
      <h3 className="feature-flag-panel-title">Feature Flags (dev)</h3>
      <p className="feature-flag-panel-hint">
        Changes persist to localStorage. URL params (?ux_v2=1) take priority.
      </p>
      <ul className="feature-flag-list">
        {ALL_FLAGS.map(id => (
          <li key={id} className="feature-flag-item">
            <label className="feature-flag-label">
              <input
                type="checkbox"
                checked={flags[id]}
                onChange={() => toggle(id)}
                className="feature-flag-checkbox"
              />
              <span className="feature-flag-id">{id}</span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default FeatureFlagPanel
