import { useState, useEffect } from 'react'

const API_URL = 'http://localhost:8000'

interface UserSettings {
  default_category: string
  default_priority: string
  conflict_resolution: string
}

interface SettingsModalProps {
  onClose: () => void
  taskCategories: string[]
}

const PRIORITY_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
]

const CONFLICT_OPTIONS = [
  {
    value: 'unschedule',
    label: 'Move conflicting task to unscheduled',
    description: 'Keep your current calendar clean by removing the overlap',
  },
  {
    value: 'backlog',
    label: 'Move to backlog',
    description: 'Add conflicting tasks to your global list for later review',
  },
  {
    value: 'overlap',
    label: 'Allow overlap',
    description: 'Show multiple tasks occurring at the same time',
  },
]

export default function SettingsModal({ onClose, taskCategories }: SettingsModalProps) {
  const [saved, setSaved] = useState<UserSettings | null>(null)
  const [form, setForm] = useState<UserSettings | null>(null)
  const [showUnsavedDialog, setShowUnsavedDialog] = useState(false)

  useEffect(() => {
    fetch(`${API_URL}/settings`)
      .then(r => r.json())
      .then((data: UserSettings) => {
        setSaved(data)
        setForm(data)
      })
  }, [])

  const isDirty = saved && form && (
    form.default_category !== saved.default_category ||
    form.default_priority !== saved.default_priority ||
    form.conflict_resolution !== saved.conflict_resolution
  )

  function handleClose() {
    if (isDirty) {
      setShowUnsavedDialog(true)
    } else {
      onClose()
    }
  }

  async function handleSave() {
    if (!form) return
    await fetch(`${API_URL}/settings`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    setSaved(form)
    onClose()
  }

  if (!form) return null

  // Build category options: standard + any custom from existing tasks, always include current value
  const standardCats = ['T', 'D', 'M']
  const extraCats = taskCategories.filter(c => !standardCats.includes(c))
  const allCats = [...standardCats, ...extraCats]
  if (!allCats.includes(form.default_category)) {
    allCats.push(form.default_category)
  }

  return (
    <div className="settings-overlay" onClick={handleClose}>
      <div className="settings-modal" onClick={e => e.stopPropagation()}>

        <div className="settings-header">
          <div>
            <h2 className="settings-title">User Settings</h2>
            <p className="settings-subtitle">Manage your task preferences and scheduling behavior</p>
          </div>
          <button className="settings-close-btn" onClick={handleClose}>&#x2715;</button>
        </div>

        <div className="settings-body">
          <section className="settings-section">
            <h3 className="settings-section-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
              Default Task Settings
            </h3>
            <div className="settings-section-divider" />
            <div className="settings-row">
              <div className="settings-field">
                <label className="settings-label">Default Category</label>
                <select
                  className="settings-select"
                  value={form.default_category}
                  onChange={e => setForm({ ...form, default_category: e.target.value })}
                >
                  {allCats.map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
                <span className="settings-hint">Automatically assigned to new tasks</span>
              </div>
              <div className="settings-field">
                <label className="settings-label">Default Priority</label>
                <select
                  className="settings-select"
                  value={form.default_priority}
                  onChange={e => setForm({ ...form, default_priority: e.target.value })}
                >
                  {PRIORITY_OPTIONS.map(p => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
                <span className="settings-hint">Initial importance level for quick creation</span>
              </div>
            </div>
          </section>

          <section className="settings-section">
            <h3 className="settings-section-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="10" y1="16" x2="14" y2="16"/></svg>
              Conflict Resolution
            </h3>
            <div className="settings-section-divider" />
            <p className="settings-conflict-desc">Choose how the app should handle tasks that overlap in your schedule.</p>
            <div className="settings-radio-group">
              {CONFLICT_OPTIONS.map(opt => (
                <label
                  key={opt.value}
                  className={`settings-radio-option${form.conflict_resolution === opt.value ? ' selected' : ''}`}
                >
                  <input
                    type="radio"
                    name="conflict_resolution"
                    value={opt.value}
                    checked={form.conflict_resolution === opt.value}
                    onChange={() => setForm({ ...form, conflict_resolution: opt.value })}
                  />
                  <div className="settings-radio-content">
                    <span className="settings-radio-label">{opt.label}</span>
                    <span className="settings-radio-desc">{opt.description}</span>
                  </div>
                </label>
              ))}
            </div>
          </section>
        </div>

        <div className="settings-footer">
          <button className="settings-discard-btn" onClick={onClose}>Discard</button>
          <button className="settings-save-btn" onClick={handleSave}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
            Save Changes
          </button>
        </div>

        {showUnsavedDialog && (
          <div className="settings-unsaved-overlay" onClick={() => setShowUnsavedDialog(false)}>
            <div className="settings-unsaved-dialog" onClick={e => e.stopPropagation()}>
              <button className="settings-unsaved-close" onClick={() => setShowUnsavedDialog(false)}>&#x2715;</button>
              <div className="settings-unsaved-icon">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              </div>
              <h3 className="settings-unsaved-title">Unsaved Changes</h3>
              <p className="settings-unsaved-text">You have unsaved changes in your settings. Are you sure you want to leave without saving?</p>
              <div className="settings-unsaved-actions">
                <button className="settings-unsaved-discard-btn" onClick={onClose}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                  Discard Changes
                </button>
                <button className="settings-unsaved-keep-btn" onClick={() => setShowUnsavedDialog(false)}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  Keep Editing
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
