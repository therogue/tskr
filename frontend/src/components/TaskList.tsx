import { useState, useEffect, useRef } from 'react'

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
type DayViewMode = 'list' | 'calendar'

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

// Flatten recurrent tasks in display order (Daily, Weekdays, Weekly, Monthly, Other)
function flattenRecurrent(templates: Task[]): Task[] {
  const groups: Record<string, Task[]> = { Daily: [], Weekdays: [], Weekly: [], Monthly: [], Other: [] }
  templates.forEach(t => {
    const category = classifyRecurrence(t.recurrence_rule)
    groups[category].push(t)
  })
  const orderedKeys: (keyof typeof groups)[] = ['Daily', 'Weekdays', 'Weekly', 'Monthly']
  orderedKeys.forEach(key => {
    if (groups[key].length < 2) {
      groups['Other'].push(...groups[key])
      groups[key] = []
    }
  })
  return [...groups['Daily'], ...groups['Weekdays'], ...groups['Weekly'], ...groups['Monthly'], ...groups['Other']]
}

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

const TrashIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    <line x1="10" y1="11" x2="10" y2="17" />
    <line x1="14" y1="11" x2="14" y2="17" />
  </svg>
)

const HOUR_HEIGHT = 60 // px per hour; 1px per minute
const CALENDAR_TOTAL_HEIGHT = 24 * HOUR_HEIGHT // 1440px
const DEFAULT_DURATION = 30 // minutes, fallback when duration_minutes is null
const SCROLL_TO_HOUR = 8 // auto-scroll to 8am on mount

function TaskList({ tasks, viewMode, selectedDate, todayStr, onViewModeChange, onDateChange, onTasksUpdate }: TaskListProps) {
  const [dayViewMode, setDayViewMode] = useState<DayViewMode>('list')
  const calendarRef = useRef<HTMLDivElement>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const lastClickedIndexRef = useRef<number | null>(null)
  const orderedVisibleTasksRef = useRef<Task[]>([])

  // Auto-scroll calendar to ~8am when switching to calendar view
  useEffect(() => {
    if (dayViewMode === 'calendar' && calendarRef.current) {
      calendarRef.current.scrollTop = SCROLL_TO_HOUR * HOUR_HEIGHT
    }
  }, [dayViewMode, selectedDate])

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

  async function handleDelete(task: Task) {
    try {
      const res = await fetch(`${API_URL}/tasks/${task.id}`, { method: 'DELETE' })
      if (res.ok) {
        onTasksUpdate()
      }
    } catch (err) {
      // Ignore errors
    }
  }

  function handleSelectBoxClick(task: Task, indexInOrdered: number, e: React.MouseEvent) {
    e.stopPropagation()
    const ordered = orderedVisibleTasksRef.current
    if (!ordered) return

    if (e.ctrlKey || e.metaKey) {
      // CTRL+click: toggle this task
      setSelectedIds(prev => {
        const next = new Set(prev)
        if (next.has(task.id)) next.delete(task.id)
        else next.add(task.id)
        return next
      })
      lastClickedIndexRef.current = indexInOrdered
    } else if (e.shiftKey) {
      // SHIFT+click: select range
      const last = lastClickedIndexRef.current ?? indexInOrdered
      const lo = Math.min(last, indexInOrdered)
      const hi = Math.max(last, indexInOrdered)
      const ids = new Set<string>()
      for (let i = lo; i <= hi; i++) ids.add(ordered[i].id)
      setSelectedIds(ids)
    } else {
      // Normal click: select only this, or deselect if already selected
      setSelectedIds(prev => {
        if (prev.has(task.id)) {
          const next = new Set(prev)
          next.delete(task.id)
          return next
        }
        return new Set([task.id])
      })
      lastClickedIndexRef.current = indexInOrdered
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

  function renderTaskItem(task: Task, indexInOrdered: number, showDate: boolean = false) {
    const isSelected = selectedIds.has(task.id)
    const classes = [
      'task-item',
      task.completed ? 'completed' : '',
      task.projected ? 'projected' : '',
      isSelected ? 'selected' : ''
    ].filter(Boolean).join(' ')

    return (
      <li
        key={task.id + (task.projected ? '-projected' : '')}
        className={classes}
        onMouseDown={(e) => e.shiftKey && e.preventDefault()}
        onClick={(e) => handleSelectBoxClick(task, indexInOrdered, e)}
      >
        <input
          type="checkbox"
          className="task-checkbox"
          checked={task.completed}
          onChange={() => handleToggle(task)}
          onClick={(e) => e.stopPropagation()}
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
        <button
          type="button"
          className="task-delete-btn"
          aria-label="Delete task"
          onClick={(e) => { e.stopPropagation(); handleDelete(task) }}
        >
          <TrashIcon />
        </button>
      </li>
    )
  }

  function renderSection(title: string, sectionTasks: Task[], showDate: boolean, startIndex: number) {
    if (sectionTasks.length === 0) return null
    return (
      <div className="task-section">
        <h3 className="task-section-title">{title}</h3>
        <ul className="task-list">
          {sectionTasks.map((t, i) => renderTaskItem(t, startIndex + i, showDate))}
        </ul>
      </div>
    )
  }

  function renderSubsection(title: string, sectionTasks: Task[], showDate: boolean, startIndex: number) {
    if (sectionTasks.length === 0) return null
    return (
      <div className="task-subsection">
        <h4 className="task-subsection-title">{title}</h4>
        <ul className="task-list">
          {sectionTasks.map((t, i) => renderTaskItem(t, startIndex + i, showDate))}
        </ul>
      </div>
    )
  }

  // Group templates by recurrence pattern, collapsing small groups into Other
  function renderRecurrentSection(templates: Task[], showDate: boolean, startIndex: number) {
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
    const subsections: { title: string; tasks: Task[] }[] = [
      { title: 'Daily', tasks: groups['Daily'] },
      { title: 'Weekdays', tasks: groups['Weekdays'] },
      { title: 'Weekly', tasks: groups['Weekly'] },
      { title: 'Monthly', tasks: groups['Monthly'] },
      { title: 'Other', tasks: groups['Other'] },
    ]
    let runningIndex = startIndex

    return (
      <div className="task-section">
        <h3 className="task-section-title">Recurrent</h3>
        {hasSubsections ? (
          <>
            {subsections.map(({ title, tasks: t }) => {
              const si = runningIndex
              runningIndex += t.length
              return renderSubsection(title, t, showDate, si)
            })}
          </>
        ) : (
          <ul className="task-list">
            {groups['Other'].map((t, i) => renderTaskItem(t, startIndex + i, showDate))}
          </ul>
        )}
      </div>
    )
  }

  function renderCalendarView() {
    // Split tasks: timed (scheduled_date contains 'T') vs untimed
    const timedTasks = [...tasks.filter(t => t.scheduled_date && t.scheduled_date.includes('T'))].sort(
      (a, b) => (a.scheduled_date! < b.scheduled_date! ? -1 : 1)
    )
    const untimedTasks = tasks.filter(t => !t.scheduled_date || !t.scheduled_date.includes('T'))
    const ordered: Task[] = [...untimedTasks, ...timedTasks]
    orderedVisibleTasksRef.current = ordered

    // Generate hour labels 0-23
    const hours = Array.from({ length: 24 }, (_, i) => i)

    function formatHourLabel(hour: number): string {
      if (hour === 0) return '12am'
      if (hour < 12) return `${hour}am`
      if (hour === 12) return '12pm'
      return `${hour - 12}pm`
    }

    return (
      <>
        {untimedTasks.length > 0 && (
          <div className="calendar-unscheduled">
            <h3 className="task-section-title">Unscheduled</h3>
            <ul className="task-list">
              {untimedTasks.map((t, i) => renderTaskItem(t, i))}
            </ul>
          </div>
        )}
        <div className="calendar-container" ref={calendarRef}>
          <div className="calendar-grid" style={{ height: CALENDAR_TOTAL_HEIGHT }}>
            {hours.map(hour => (
              <div key={hour} className="calendar-hour-row" style={{ top: hour * HOUR_HEIGHT, height: HOUR_HEIGHT }}>
                <span className="calendar-hour-label">{formatHourLabel(hour)}</span>
              </div>
            ))}
            {timedTasks.map((task, i) => {
              const indexInOrdered = untimedTasks.length + i
              const isSelected = selectedIds.has(task.id)
              // Assumption: scheduled_date format is YYYY-MM-DDTHH:MM
              const timePart = task.scheduled_date!.slice(11, 16)
              const [h, m] = timePart.split(':').map(Number)
              const topPx = h * HOUR_HEIGHT + m * (HOUR_HEIGHT / 60)
              const duration = task.duration_minutes || DEFAULT_DURATION
              const heightPx = duration * (HOUR_HEIGHT / 60)

              const classes = [
                'calendar-task-block',
                task.completed ? 'completed' : '',
                task.projected ? 'projected' : '',
                isSelected ? 'selected' : ''
              ].filter(Boolean).join(' ')

              return (
                <div
                  key={task.id + (task.projected ? '-projected' : '')}
                  className={classes}
                  style={{ top: topPx, height: Math.max(heightPx, 16) }}
                  onMouseDown={(e) => e.shiftKey && e.preventDefault()}
                  onClick={(e) => handleSelectBoxClick(task, indexInOrdered, e)}
                >
                  <input
                    type="checkbox"
                    className="task-checkbox"
                    checked={task.completed}
                    onChange={() => handleToggle(task)}
                    onClick={(e) => e.stopPropagation()}
                  />
                  <span className="calendar-task-key">{task.task_key}</span>
                  <span className="calendar-task-title">{task.title}</span>
                  <button
                    type="button"
                    className="task-delete-btn"
                    aria-label="Delete task"
                    onClick={(e) => { e.stopPropagation(); handleDelete(task) }}
                  >
                    <TrashIcon />
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      </>
    )
  }

  function renderDayView() {
    const isEmpty = tasks.length === 0
    // Group by category for list view
    const meetings = tasks.filter(t => t.category === 'M')
    const daily = tasks.filter(t => t.category === 'D')
    const other = tasks.filter(t => t.category !== 'M' && t.category !== 'D')

    return (
      <>
        <div className="date-nav">
          <button className="date-nav-btn" onClick={() => {
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
        <div className="day-view-toggle">
          <button
            className={dayViewMode === 'list' ? 'active' : ''}
            onClick={() => setDayViewMode('list')}
          >List</button>
          <button
            className={dayViewMode === 'calendar' ? 'active' : ''}
            onClick={() => setDayViewMode('calendar')}
          >Calendar</button>
        </div>
        {dayViewMode === 'list' ? (
          isEmpty ? (
            <p className="empty-state">No tasks for this day.</p>
          ) : (
            <>
              {(() => {
                const ordered = [...meetings, ...daily, ...other]
                orderedVisibleTasksRef.current = ordered
                return (
                  <>
                    {renderSection('Meetings', meetings, false, 0)}
                    {renderSection('Daily', daily, false, meetings.length)}
                    {renderSection('Tasks', other, false, meetings.length + daily.length)}
                  </>
                )
              })()}
            </>
          )
        ) : (
          renderCalendarView()
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

    // Regular tasks: category T, not template, matching completed status
    const regularTasks = tasks.filter(t =>
      t.category === 'T' && !t.is_template && t.completed === completedFilter
    )

    // Projects: categories not in M, T, D, not templates, matching completed status
    const projectTasks = tasks.filter(t =>
      !t.is_template && !['M', 'T', 'D'].includes(t.category) && t.completed === completedFilter
    )
    const projectCategories = [...new Set(projectTasks.map(t => t.category))].sort()

    const isEmpty = meetings.length === 0 && recurrent.length === 0 && regularTasks.length === 0 && projectTasks.length === 0
    const recurrentFlat = flattenRecurrent(recurrent)
    const ordered: Task[] = [
      ...meetings,
      ...recurrentFlat,
      ...regularTasks,
      ...projectCategories.flatMap(cat => projectTasks.filter(t => t.category === cat)),
    ]
    orderedVisibleTasksRef.current = ordered

    let sectionStart = 0
    return (
      <>
        {isEmpty ? (
          <p className="empty-state">
            {completedFilter ? 'No completed tasks.' : 'No tasks yet. Chat with the AI to create tasks.'}
          </p>
        ) : (
          <>
            {renderSection('Meetings', meetings, true, sectionStart)}
            {renderRecurrentSection(recurrent, true, sectionStart += meetings.length)}
            {renderSection('Tasks', regularTasks, true, sectionStart += recurrentFlat.length)}
            {projectCategories.map(cat => {
              const catTasks = projectTasks.filter(t => t.category === cat)
              const si = sectionStart
              sectionStart += catTasks.length
              return renderSection(cat, catTasks, true, si)
            })}
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
