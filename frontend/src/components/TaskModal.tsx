// Task detail modal — opens on double-click.
// Edits: title, priority, scheduled_date, duration_minutes.
// notes field is intentionally absent (column does not exist on Task model — see resolved Q1 in docs/ux-v2/implementation.md).

import { useState, useEffect, useRef } from 'react'

interface Task {
  id: string
  task_key: string
  category: string
  title: string
  completed: boolean
  scheduled_date: string | null
  duration_minutes: number | null
  priority: number | null
}

interface TaskModalProps {
  task: Task
  onClose: () => void
  onSave: (updated: Task) => void
  onDelete: (id: string) => void
}

const API_URL = 'http://localhost:8000'

const PRIORITY_OPTIONS = [
  { value: 0, label: 'None' },
  { value: 1, label: 'Low' },
  { value: 2, label: 'Medium' },
  { value: 3, label: 'High' },
  { value: 4, label: 'Critical' },
]

function TaskModal({ task, onClose, onSave, onDelete }: TaskModalProps) {
  const [title, setTitle] = useState(task.title)
  const [priority, setPriority] = useState<number>(task.priority ?? 0)
  const [scheduledDate, setScheduledDate] = useState(task.scheduled_date ?? '')
  const [durationMinutes, setDurationMinutes] = useState<string>(
    task.duration_minutes != null ? String(task.duration_minutes) : ''
  )
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  async function handleSave() {
    if (!title.trim() || saving) return
    setSaving(true)
    try {
      const body: Record<string, unknown> = {
        title: title.trim(),
        priority,
      }
      if (scheduledDate) body.scheduled_date = scheduledDate
      else body.scheduled_date = null
      const dur = parseInt(durationMinutes, 10)
      body.duration_minutes = isNaN(dur) || dur <= 0 ? null : dur

      const res = await fetch(`${API_URL}/tasks/${task.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const updated = await res.json()
      onSave({ ...task, ...updated })
    } catch {
      // Ignore errors
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    try {
      await fetch(`${API_URL}/tasks/${task.id}`, { method: 'DELETE' })
      onDelete(task.id)
    } catch {
      // Ignore errors
    }
  }

  return (
    <div
      className="task-modal-overlay"
      ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div className="task-modal" role="dialog" aria-label={`Edit task: ${task.title}`}>
        <div className="task-modal-header">
          <span className="task-modal-key">{task.task_key}</span>
          <h3 className="task-modal-title">Edit Task</h3>
          <button className="task-modal-close" onClick={onClose} aria-label="Close modal" type="button">✕</button>
        </div>

        <div className="task-modal-body">
          <label className="task-modal-label">
            Title
            <input
              className="task-modal-input"
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Task title"
              autoFocus
            />
          </label>

          <label className="task-modal-label">
            Priority
            <select
              className="task-modal-select"
              value={priority}
              onChange={e => setPriority(Number(e.target.value))}
            >
              {PRIORITY_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>

          <label className="task-modal-label">
            Scheduled Date / Time
            <input
              className="task-modal-input"
              type="datetime-local"
              value={scheduledDate?.slice(0, 16) ?? ''}
              onChange={e => setScheduledDate(e.target.value)}
            />
          </label>

          <label className="task-modal-label">
            Duration (minutes)
            <input
              className="task-modal-input"
              type="number"
              min={1}
              value={durationMinutes}
              onChange={e => setDurationMinutes(e.target.value)}
              placeholder="e.g. 30"
            />
          </label>
        </div>

        <div className="task-modal-footer">
          {confirmDelete ? (
            <div className="task-modal-confirm-delete">
              <span>Delete this task?</span>
              <button type="button" className="task-modal-btn task-modal-btn--danger" onClick={handleDelete}>
                Yes, delete
              </button>
              <button type="button" className="task-modal-btn task-modal-btn--ghost" onClick={() => setConfirmDelete(false)}>
                Cancel
              </button>
            </div>
          ) : (
            <>
              <button
                type="button"
                className="task-modal-btn task-modal-btn--danger-ghost"
                onClick={() => setConfirmDelete(true)}
              >
                Delete
              </button>
              <div className="task-modal-footer-right">
                <button type="button" className="task-modal-btn task-modal-btn--ghost" onClick={onClose}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="task-modal-btn task-modal-btn--primary"
                  onClick={handleSave}
                  disabled={saving || !title.trim()}
                >
                  {saving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default TaskModal
