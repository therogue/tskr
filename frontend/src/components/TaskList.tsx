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
}

interface TaskListProps {
  tasks: Task[]
  onTasksUpdate: (tasks: Task[]) => void
}

const API_URL = 'http://localhost:8000'

function TaskList({ tasks, onTasksUpdate }: TaskListProps) {
  async function handleToggle(task: Task) {
    try {
      const res = await fetch(`${API_URL}/tasks/${task.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed: !task.completed }),
      })
      if (res.ok) {
        const tasksRes = await fetch(`${API_URL}/tasks`)
        const updatedTasks = await tasksRes.json()
        onTasksUpdate(updatedTasks)
      }
    } catch (err) {
      // Ignore errors
    }
  }

  // Get today's date in YYYY-MM-DD format
  const today = new Date()
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`

  // Group tasks by category
  // Daily tasks: only show tasks scheduled for today (prefix match for datetime support)
  const meetings = tasks.filter((t) => t.category === 'M')
  const daily = tasks.filter((t) => t.category === 'D' && t.scheduled_date?.startsWith(todayStr))
  const other = tasks.filter((t) => t.category !== 'M' && t.category !== 'D')

  function formatDateTime(dateStr: string | null): string {
    if (!dateStr) return ''
    // Handle both YYYY-MM-DD and YYYY-MM-DDTHH:MM formats
    const hasTime = dateStr.includes('T')
    const datePart = dateStr.slice(0, 10)
    const [year, month, day] = datePart.split('-').map(Number)
    const date = new Date(year, month - 1, day)
    const dateFormatted = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

    if (hasTime) {
      const timePart = dateStr.slice(11, 16) // HH:MM
      const [hours, minutes] = timePart.split(':').map(Number)
      const ampm = hours >= 12 ? 'pm' : 'am'
      const hours12 = hours % 12 || 12
      const timeFormatted = minutes === 0 ? `${hours12}${ampm}` : `${hours12}:${String(minutes).padStart(2, '0')}${ampm}`
      return `${dateFormatted} ${timeFormatted}`
    }
    return dateFormatted
  }

  function renderTaskItem(task: Task) {
    return (
      <li key={task.id} className={`task-item ${task.completed ? 'completed' : ''}`}>
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
          <span className="task-date">{formatDateTime(task.scheduled_date)}</span>
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

  return (
    <div className="task-panel">
      <h2>Tasks</h2>
      {tasks.length === 0 ? (
        <p className="empty-state">No tasks yet. Chat with the AI to create tasks.</p>
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
