// In-chat task card shown below assistant message when an AI action creates/edits a task.
// "View" and "Edit" both open TaskModal from TaskList.

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

interface TaskCardProps {
  task: Task
  onView?: (task: Task) => void
  onEdit?: (task: Task) => void
}

const PRIORITY_LABEL: Record<number, string> = {
  4: 'Critical', 3: 'High', 2: 'Medium', 1: 'Low', 0: 'None',
}
const PRIORITY_CLASS: Record<number, string> = {
  4: 'priority-critical', 3: 'priority-high', 2: 'priority-medium', 1: 'priority-low', 0: 'priority-none',
}

function formatScheduled(date: string | null): string | null {
  if (!date) return null
  const hasTime = date.includes('T')
  const datePart = date.slice(0, 10)
  const [y, m, d] = datePart.split('-').map(Number)
  const dateFormatted = new Date(y, m - 1, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  if (hasTime) {
    const [h, min] = date.slice(11, 16).split(':').map(Number)
    const ampm = h >= 12 ? 'pm' : 'am'
    const h12 = h % 12 || 12
    const timeStr = min === 0 ? `${h12}${ampm}` : `${h12}:${String(min).padStart(2, '0')}${ampm}`
    return `${dateFormatted} ${timeStr}`
  }
  return dateFormatted
}

function TaskCard({ task, onView, onEdit }: TaskCardProps) {
  const priorityLabel = PRIORITY_LABEL[task.priority ?? 0] ?? 'None'
  const priorityClass = PRIORITY_CLASS[task.priority ?? 0] ?? 'priority-none'
  const scheduled = formatScheduled(task.scheduled_date)

  return (
    <div className="task-card-bubble" data-testid="task-card">
      <div className="task-card-header">
        <span className="task-card-key">{task.task_key}</span>
        <span className={`task-card-priority ${priorityClass}`}>{priorityLabel}</span>
        {task.completed && <span className="task-card-done">Done</span>}
      </div>
      <p className="task-card-title">{task.title}</p>
      {(scheduled || task.duration_minutes) && (
        <div className="task-card-meta">
          {scheduled && <span className="task-card-date">{scheduled}</span>}
          {task.duration_minutes && <span className="task-card-dur">{task.duration_minutes}m</span>}
        </div>
      )}
      <div className="task-card-actions">
        {onView && (
          <button type="button" className="task-card-btn task-card-btn--view" onClick={() => onView(task)}>
            View
          </button>
        )}
        {onEdit && (
          <button type="button" className="task-card-btn task-card-btn--edit" onClick={() => onEdit(task)}>
            Edit
          </button>
        )}
      </div>
    </div>
  )
}

export default TaskCard
