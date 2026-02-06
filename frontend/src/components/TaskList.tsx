interface Task {
  id: string
  task_key: string
  category: string
  task_number: number
  title: string
  completed: boolean
  scheduled_date: string | null
  recurrence_rule: string | null
  created_at: string
  is_template: boolean
  parent_task_id: string | null
  projected?: boolean
}

type ViewMode = 'day' | 'category'

interface TaskListProps {
  tasks: Task[]
  viewMode: ViewMode
  onViewModeChange: (mode: ViewMode) => void
  onTasksUpdate: () => void
}

const API_URL = 'http://localhost:8000'

function TaskList({ tasks, viewMode, onViewModeChange, onTasksUpdate }: TaskListProps) {
  async function handleToggle(task: Task) {
    try {
      const res = await fetch(`${API_URL}/tasks/${task.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed: !task.completed }),
      })
      if (res.ok) {
        onTasksUpdate()
      }
    } catch (err) {
      // Ignore errors
    }
  }

  function formatDateTime(dateStr: string | null): string {
    if (!dateStr) return ''
    const hasTime = dateStr.includes('T')
    const datePart = dateStr.slice(0, 10)
    const [year, month, day] = datePart.split('-').map(Number)
    const date = new Date(year, month - 1, day)
    const dateFormatted = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

    if (hasTime) {
      const timePart = dateStr.slice(11, 16)
      const [hours, minutes] = timePart.split(':').map(Number)
      const ampm = hours >= 12 ? 'pm' : 'am'
      const hours12 = hours % 12 || 12
      const timeFormatted = minutes === 0 ? `${hours12}${ampm}` : `${hours12}:${String(minutes).padStart(2, '0')}${ampm}`
      return `${dateFormatted} ${timeFormatted}`
    }
    return dateFormatted
  }

  function formatTime(dateStr: string | null): string {
    if (!dateStr || !dateStr.includes('T')) return ''
    const timePart = dateStr.slice(11, 16)
    const [hours, minutes] = timePart.split(':').map(Number)
    const ampm = hours >= 12 ? 'pm' : 'am'
    const hours12 = hours % 12 || 12
    return minutes === 0 ? `${hours12}${ampm}` : `${hours12}:${String(minutes).padStart(2, '0')}${ampm}`
  }

  function renderTaskItem(task: Task) {
    const classes = [
      'task-item',
      task.completed ? 'completed' : '',
      task.projected ? 'projected' : ''
    ].filter(Boolean).join(' ')

    return (
      <li key={task.id + (task.projected ? '-projected' : '')} className={classes}>
        <input
          type="checkbox"
          className="task-checkbox"
          checked={task.completed}
          onChange={() => handleToggle(task)}
        />
        <span className="task-key">{task.task_key}</span>
        <span className="task-title">{task.title}</span>
        {task.recurrence_rule && (
          <span className="task-recurring" title={`Repeats: ${task.recurrence_rule}`}>&#x21bb;</span>
        )}
        {task.scheduled_date && (
          <span className="task-date">
            {viewMode === 'day' ? formatTime(task.scheduled_date) : formatDateTime(task.scheduled_date)}
          </span>
        )}
      </li>
    )
  }

  function renderSection(title: string, sectionTasks: Task[]) {
    if (sectionTasks.length === 0) return null
    return (
      <div className="task-section">
        <h3 className="task-section-title">{title}</h3>
        <ul className="task-list">
          {sectionTasks.map(renderTaskItem)}
        </ul>
      </div>
    )
  }

  // Group tasks by category
  const meetings = tasks.filter((t) => t.category === 'M')
  const daily = tasks.filter((t) => t.category === 'D')
  const other = tasks.filter((t) => t.category !== 'M' && t.category !== 'D')

  const isEmpty = tasks.length === 0
  const emptyMessage = viewMode === 'day'
    ? 'No tasks for today.'
    : 'No tasks yet. Chat with the AI to create tasks.'

  return (
    <div className="task-panel">
      <div className="task-header">
        <h2>{viewMode === 'day' ? 'Today' : 'All Tasks'}</h2>
        <button
          className="view-toggle"
          onClick={() => onViewModeChange(viewMode === 'day' ? 'category' : 'day')}
        >
          {viewMode === 'day' ? 'All' : 'Today'}
        </button>
      </div>
      {isEmpty ? (
        <p className="empty-state">{emptyMessage}</p>
      ) : (
        <>
          {renderSection('Meetings', meetings)}
          {renderSection('Daily', daily)}
          {renderSection('Tasks', other)}
        </>
      )}
    </div>
  )
}

export default TaskList
