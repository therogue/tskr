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
  duration_minutes: number | null
  projected?: boolean
}

type ViewMode = 'day' | 'all' | 'completed'

interface TaskListProps {
  tasks: Task[]
  viewMode: ViewMode
  selectedDate: string
  todayStr: string
  onViewModeChange: (mode: ViewMode) => void
  onDateChange: (date: string) => void
  onTasksUpdate: () => void
}

const API_URL = 'http://localhost:8000'

// Recurrence pattern classification
// Assumption: recurrence_rule values are lowercase strings like "daily", "weekdays", "monday", "tue,thu", "monthly", "01-15"
function classifyRecurrence(rule: string | null): string {
  if (!rule) return 'Other'
  const r = rule.toLowerCase()
  if (r === 'daily') return 'Daily'
  if (r === 'weekdays') return 'Weekdays'
  // Weekly: contains day names but not daily/weekdays
  const dayNames = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
  if (dayNames.some(d => r.includes(d))) return 'Weekly'
  // Monthly: contains "monthly" or looks like MM-DD pattern
  if (r.includes('monthly') || /^\d{2}-\d{2}$/.test(r)) return 'Monthly'
  return 'Other'
}

function TaskList({ tasks, viewMode, selectedDate, todayStr, onViewModeChange, onDateChange, onTasksUpdate }: TaskListProps) {
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

  function formatDateHeader(dateStr: string): string {
    const [year, month, day] = dateStr.split('-').map(Number)
    const date = new Date(year, month - 1, day)
    return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  }

  function renderTaskItem(task: Task, showDate: boolean = false) {
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
            {showDate ? formatDateTime(task.scheduled_date) : formatTime(task.scheduled_date)}
          </span>
        )}
      </li>
    )
  }

  function renderSection(title: string, sectionTasks: Task[], showDate: boolean = false) {
    if (sectionTasks.length === 0) return null
    return (
      <div className="task-section">
        <h3 className="task-section-title">{title}</h3>
        <ul className="task-list">
          {sectionTasks.map(t => renderTaskItem(t, showDate))}
        </ul>
      </div>
    )
  }

  function renderSubsection(title: string, sectionTasks: Task[], showDate: boolean = false) {
    if (sectionTasks.length === 0) return null
    return (
      <div className="task-subsection">
        <h4 className="task-subsection-title">{title}</h4>
        <ul className="task-list">
          {sectionTasks.map(t => renderTaskItem(t, showDate))}
        </ul>
      </div>
    )
  }

  // Group templates by recurrence pattern, collapsing small groups into Other
  function renderRecurrentSection(templates: Task[], showDate: boolean = false) {
    if (templates.length === 0) return null

    const groups: Record<string, Task[]> = { Daily: [], Weekdays: [], Weekly: [], Monthly: [], Other: [] }
    templates.forEach(t => {
      const category = classifyRecurrence(t.recurrence_rule)
      groups[category].push(t)
    })

    // Collapse groups with < 2 tasks into Other
    const orderedKeys: (keyof typeof groups)[] = ['Daily', 'Weekdays', 'Weekly', 'Monthly']
    orderedKeys.forEach(key => {
      if (groups[key].length < 2) {
        groups['Other'].push(...groups[key])
        groups[key] = []
      }
    })

    const hasSubsections = orderedKeys.some(k => groups[k].length > 0)

    return (
      <div className="task-section">
        <h3 className="task-section-title">Recurrent</h3>
        {hasSubsections ? (
          <>
            {renderSubsection('Daily', groups['Daily'], showDate)}
            {renderSubsection('Weekdays', groups['Weekdays'], showDate)}
            {renderSubsection('Weekly', groups['Weekly'], showDate)}
            {renderSubsection('Monthly', groups['Monthly'], showDate)}
            {renderSubsection('Other', groups['Other'], showDate)}
          </>
        ) : (
          <ul className="task-list">
            {groups['Other'].map(t => renderTaskItem(t, showDate))}
          </ul>
        )}
      </div>
    )
  }

  function renderDayView() {
    const isEmpty = tasks.length === 0
    // Group by category for day view
    const meetings = tasks.filter(t => t.category === 'M')
    const daily = tasks.filter(t => t.category === 'D')
    const other = tasks.filter(t => t.category !== 'M' && t.category !== 'D')

    return (
      <>
        <div className="date-nav">
          <button className="date-nav-btn" onClick={() => {
            // Parse manually to avoid UTC timezone issues
            const [year, month, day] = selectedDate.split('-').map(Number)
            const d = new Date(year, month - 1, day)
            d.setDate(d.getDate() - 1)
            onDateChange(formatDateForInput(d))
          }}>&lt;</button>
          <input
            type="date"
            className="date-picker"
            value={selectedDate}
            onChange={e => onDateChange(e.target.value)}
          />
          <button className="date-nav-btn" onClick={() => {
            // Parse manually to avoid UTC timezone issues
            const [year, month, day] = selectedDate.split('-').map(Number)
            const d = new Date(year, month - 1, day)
            d.setDate(d.getDate() + 1)
            onDateChange(formatDateForInput(d))
          }}>&gt;</button>
          {selectedDate !== todayStr && (
            <button className="today-btn" onClick={() => onDateChange(todayStr)}>Today</button>
          )}
        </div>
        <h2 className="date-header">{formatDateHeader(selectedDate)}</h2>
        {isEmpty ? (
          <p className="empty-state">No tasks for this day.</p>
        ) : (
          <>
            {renderSection('Meetings', meetings)}
            {renderSection('Daily', daily)}
            {renderSection('Tasks', other)}
          </>
        )}
      </>
    )
  }

  function formatDateForInput(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }

  function renderAllTasksView(completedFilter: boolean) {
    // For "All Tasks": show incomplete tasks + templates
    // For "Completed": show completed tasks, group recurring instances by pattern

    // Meetings: category M, not template, matching completed status
    const meetings = tasks.filter(t =>
      t.category === 'M' && !t.is_template && t.completed === completedFilter
    )

    // Recurrent section:
    // - All Tasks: show templates (templates have completed=false)
    // - Completed: show completed instances that have recurrence_rule (came from templates)
    const recurrent = completedFilter
      ? tasks.filter(t => t.completed && t.recurrence_rule && !t.is_template)
      : tasks.filter(t => t.is_template)

    // Projects: categories not in M, T, D, not templates, matching completed status
    const projectTasks = tasks.filter(t =>
      !t.is_template && !['M', 'T', 'D'].includes(t.category) && t.completed === completedFilter
    )
    const projectCategories = [...new Set(projectTasks.map(t => t.category))].sort()

    const isEmpty = meetings.length === 0 && recurrent.length === 0 && projectTasks.length === 0

    return (
      <>
        {isEmpty ? (
          <p className="empty-state">
            {completedFilter ? 'No completed tasks.' : 'No tasks yet. Chat with the AI to create tasks.'}
          </p>
        ) : (
          <>
            {renderSection('Meetings', meetings, true)}
            {renderRecurrentSection(recurrent, true)}
            {projectCategories.map(cat =>
              renderSection(cat, projectTasks.filter(t => t.category === cat), true)
            )}
          </>
        )}
      </>
    )
  }

  return (
    <div className="task-panel">
      <div className="tab-bar">
        <button
          className={`tab ${viewMode === 'day' ? 'active' : ''}`}
          onClick={() => onViewModeChange('day')}
        >
          Day View
        </button>
        <button
          className={`tab ${viewMode === 'all' ? 'active' : ''}`}
          onClick={() => onViewModeChange('all')}
        >
          All Tasks
        </button>
        <button
          className={`tab ${viewMode === 'completed' ? 'active' : ''}`}
          onClick={() => onViewModeChange('completed')}
        >
          Completed
        </button>
      </div>

      <div className="tab-content">
        {viewMode === 'day' && renderDayView()}
        {viewMode === 'all' && renderAllTasksView(false)}
        {viewMode === 'completed' && renderAllTasksView(true)}
      </div>
    </div>
  )
}

export default TaskList
