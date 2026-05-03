import { useState, useEffect, useRef } from 'react'
import { computeColumnLayout, DEFAULT_DURATION, pxToSnappedMinutes, minutesToTimeStr } from '../utils/calendarLayout'
import { formatTaskCreationDate } from '../utils/date'
import { useFeatureFlag } from '../featureFlags'
import TaskModal from './TaskModal'

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
  priority: number | null  // 0=None, 1=Low, 2=Medium, 3=High, 4=Critical
}

type ViewMode = 'day' | 'all' | 'completed' | 'backlog'
type DayViewMode = 'list' | 'calendar'

interface TaskListProps {
  tasks: Task[]
  // Overdue tasks shown above today's day view. Empty when not viewing today.
  overdueTasks?: Task[]
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

// Priority badge: maps priority int to label and CSS class
// Assumption: priority is 0-4 or null
const PRIORITY_CONFIG: Record<number, { label: string; className: string; description: string }> = {
  4: { label: 'C', className: 'priority-critical', description: 'Critical' },
  3: { label: 'H', className: 'priority-high', description: 'High' },
  2: { label: 'M', className: 'priority-medium', description: 'Medium' },
  1: { label: 'L', className: 'priority-low', description: 'Low' },
  0: { label: '-', className: 'priority-none', description: 'None' },
}

function PriorityBadge({ priority }: { priority: number | null }) {
  if (priority === null || priority === undefined) return null
  const config = PRIORITY_CONFIG[priority]
  if (!config) return null
  return <span className={`priority-badge ${config.className}`} title={config.description}>{config.label}</span>
}

// Format duration_minutes for display (e.g. 90 → "1h 30m", 60 → "1h", 15 → "15m")
function formatDuration(minutes: number | null): string | null {
  if (minutes === null || minutes === undefined || minutes <= 0) return null
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h > 0 && m > 0) return `${h}h ${m}m`
  if (h > 0) return `${h}h`
  return `${m}m`
}

const HOUR_HEIGHT = 60 // px per hour; 1px per minute
const CALENDAR_TOTAL_HEIGHT = 24 * HOUR_HEIGHT // 1440px
const SCROLL_TO_HOUR = 8 // auto-scroll to 8am on mount
// Pixel offsets matching .calendar-hour-label width and .calendar-task-block right
const LABEL_WIDTH = 55 // px
const RIGHT_PAD = 8   // px

function TaskList({ tasks, overdueTasks = [], viewMode, selectedDate, todayStr, onViewModeChange, onDateChange, onTasksUpdate }: TaskListProps) {
  const uxV2 = useFeatureFlag('ux_v2')
  const taskModalEnabled = useFeatureFlag('ux_v2.task_modal')
  const [dayViewMode, setDayViewMode] = useState<DayViewMode>('list')
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const clickTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())
  const calendarRef = useRef<HTMLDivElement>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const lastClickedIndexRef = useRef<number | null>(null)
  const orderedVisibleTasksRef = useRef<Task[]>([])
  const [confirmDelete, setConfirmDelete] = useState<{ message: string; ids: string[]; x: number; y: number } | null>(null)

  // Drag state: stored in ref to avoid re-renders on every pointermove
  interface DragData {
    taskId: string
    element: HTMLElement
    startClientY: number
    startTopPx: number
    currentTopPx: number
    hasMoved: boolean
    // For group drag: other selected task ids → their original top px
    groupOrigTops: Map<string, number>
  }
  const dragStateRef = useRef<DragData | null>(null)
  const dragJustFinishedRef = useRef(false)
  const [draggingTaskId, setDraggingTaskId] = useState<string | null>(null)
  // Map of task id → calendar block DOM element, for group drag visual
  const taskBlockRefsMap = useRef<Map<string, HTMLElement>>(new Map())

  // Bulk reschedule popup
  const [reschedulePopup, setReschedulePopup] = useState<{ x: number; y: number } | null>(null)
  const [rescheduleDate, setRescheduleDate] = useState<string>('')

  // Clear selection when switching main tabs
  useEffect(() => {
    setSelectedIds(new Set())
    lastClickedIndexRef.current = null
  }, [viewMode])

  // Auto-scroll calendar to ~8am when switching to calendar view
  useEffect(() => {
    if (dayViewMode === 'calendar' && calendarRef.current) {
      calendarRef.current.scrollTop = SCROLL_TO_HOUR * HOUR_HEIGHT
    }
  }, [dayViewMode, selectedDate])

  async function handleToggle(task: Task) {
    const newCompleted = !task.completed
    const isBulk = selectedIds.has(task.id) && selectedIds.size > 1
    const ids = isBulk ? Array.from(selectedIds) : [task.id]
    try {
      await Promise.all(ids.map(id =>
        fetch(`${API_URL}/tasks/${id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ completed: newCompleted }),
        })
      ))
      onTasksUpdate()
      if (isBulk) setSelectedIds(new Set())
    } catch (err) {
      // Ignore errors
    }
  }

  function handleDelete(task: Task, e: React.MouseEvent) {
    setConfirmDelete({
      message: 'Are you sure you want to delete this task?',
      ids: [task.id],
      x: e.clientX,
      y: e.clientY,
    })
  }

  function handleDeleteSelected(e: React.MouseEvent) {
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    const count = ids.length
    const message = count === 1
      ? 'Are you sure you want to delete this task?'
      : `Are you sure you want to delete ${count} tasks?`
    setConfirmDelete({ message, ids, x: e.clientX, y: e.clientY })
  }

  async function confirmDeleteAction(ids: string[]) {
    if (!confirmDelete) return
    try {
      await Promise.all(ids.map(id => fetch(`${API_URL}/tasks/${id}`, { method: 'DELETE' })))
      setSelectedIds(prev => {
        const next = new Set(prev)
        ids.forEach(id => next.delete(id))
        return next
      })
      onTasksUpdate()
    } catch (err) {
      // Ignore errors
    }
    setConfirmDelete(null)
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

  // Double-click detection: single click → existing select/toggle; double click → open TaskModal.
  // Only active when ux_v2=true AND ux_v2.task_modal=true.
  function handleRowActivate(task: Task, indexInOrdered: number, e: React.MouseEvent) {
    if (!uxV2 || !taskModalEnabled) {
      handleSelectBoxClick(task, indexInOrdered, e)
      return
    }
    if (clickTimers.current.has(task.id)) {
      // Second click within 300ms → double-click: open modal
      clearTimeout(clickTimers.current.get(task.id))
      clickTimers.current.delete(task.id)
      setSelectedTask(task)
    } else {
      // First click: set a timer; if no second click in 300ms, treat as single click
      const timer = setTimeout(() => {
        clickTimers.current.delete(task.id)
        handleSelectBoxClick(task, indexInOrdered, e)
      }, 300)
      clickTimers.current.set(task.id, timer)
    }
  }

  function handleDragStart(e: React.PointerEvent, task: Task, startTopPx: number) {
    // Only drag timed tasks; ignore clicks on interactive children
    if (!task.scheduled_date?.includes('T')) return
    if ((e.target as HTMLElement).closest('.task-checkbox, .task-delete-btn')) return
    // Do NOT call e.preventDefault() here — it would suppress the subsequent click
    // event and break task selection. Text selection is prevented in handleDragMove
    // once the movement threshold is crossed.

    const el = e.currentTarget as HTMLElement
    el.setPointerCapture(e.pointerId)

    // Precompute original top positions for other selected timed tasks (group drag)
    const groupOrigTops = new Map<string, number>()
    if (selectedIds.has(task.id) && selectedIds.size > 1) {
      for (const id of selectedIds) {
        if (id === task.id) continue
        const t = tasks.find(t => t.id === id)
        if (t?.scheduled_date?.includes('T')) {
          const timePart = t.scheduled_date.slice(11, 16)
          const [h, m] = timePart.split(':').map(Number)
          groupOrigTops.set(id, h * HOUR_HEIGHT + m * (HOUR_HEIGHT / 60))
        }
      }
    }

    dragStateRef.current = {
      taskId: task.id,
      element: el,
      startClientY: e.clientY,
      startTopPx,
      currentTopPx: startTopPx,
      hasMoved: false,
      groupOrigTops,
    }
  }

  function handleDragMove(e: React.PointerEvent) {
    const ds = dragStateRef.current
    if (!ds || ds.taskId !== (e.currentTarget as HTMLElement).dataset.taskId) return

    const deltaY = e.clientY - ds.startClientY
    if (!ds.hasMoved && Math.abs(deltaY) < 5) return

    // Prevent text selection and scroll during drag (safe here — pointermove
    // preventDefault does NOT suppress the click event, unlike pointerdown)
    e.preventDefault()

    if (!ds.hasMoved) {
      ds.hasMoved = true
      setDraggingTaskId(ds.taskId)
    }

    const rawTop = ds.startTopPx + deltaY
    const snappedMinutes = pxToSnappedMinutes(rawTop)
    ds.currentTopPx = snappedMinutes // 1px == 1 minute
    ds.element.style.top = `${snappedMinutes}px`

    // Move other selected tasks by the same raw delta
    for (const [id, origTop] of ds.groupOrigTops) {
      const otherEl = taskBlockRefsMap.current.get(id)
      if (otherEl) otherEl.style.top = `${pxToSnappedMinutes(origTop + deltaY)}px`
    }
  }

  async function handleDragEnd(_e: React.PointerEvent, task: Task) {
    const ds = dragStateRef.current
    if (!ds || ds.taskId !== task.id) return

    const wasDragging = ds.hasMoved
    dragStateRef.current = null
    setDraggingTaskId(null)

    if (!wasDragging) return

    // Suppress the click that fires after pointerup
    dragJustFinishedRef.current = true

    const snappedMinutes = pxToSnappedMinutes(ds.currentTopPx)
    const newTime = minutesToTimeStr(snappedMinutes)
    const datePart = task.scheduled_date!.slice(0, 10)
    const deltaMinutes = snappedMinutes - ds.startTopPx // startTopPx is in px == minutes

    const patches: Promise<Response>[] = [
      fetch(`${API_URL}/tasks/${task.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scheduled_date: `${datePart}T${newTime}` }),
      }),
    ]

    // Patch other selected timed tasks by the same delta
    for (const [id, origTop] of ds.groupOrigTops) {
      const t = tasks.find(t => t.id === id)
      if (!t?.scheduled_date?.includes('T')) continue
      const newMinutes = pxToSnappedMinutes(origTop + deltaMinutes)
      const tDatePart = t.scheduled_date.slice(0, 10)
      patches.push(
        fetch(`${API_URL}/tasks/${id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scheduled_date: `${tDatePart}T${minutesToTimeStr(newMinutes)}` }),
        })
      )
    }

    try {
      await Promise.all(patches)
      onTasksUpdate()
    } catch {
      // Ignore errors
    }
  }

  function handleDragCancel() {
    const ds = dragStateRef.current
    if (!ds) return
    ds.element.style.top = `${ds.startTopPx}px`
    for (const [id, origTop] of ds.groupOrigTops) {
      const otherEl = taskBlockRefsMap.current.get(id)
      if (otherEl) otherEl.style.top = `${origTop}px`
    }
    dragStateRef.current = null
    setDraggingTaskId(null)
  }

  function openReschedulePopup(e: React.MouseEvent) {
    setRescheduleDate(selectedDate)
    setReschedulePopup({ x: e.clientX, y: e.clientY })
  }

  async function applyReschedule() {
    if (!rescheduleDate) return
    try {
      await Promise.all(
        Array.from(selectedIds).map(id => {
          // Selection may include overdue tasks (rendered above today's day view) which are not in `tasks`.
          const t = tasks.find(t => t.id === id) ?? overdueTasks.find(t => t.id === id)
          // Preserve existing time if the task has one; otherwise use date-only
          const existingTime = t?.scheduled_date?.includes('T')
            ? t.scheduled_date.slice(11, 16)
            : null
          const newScheduledDate = existingTime
            ? `${rescheduleDate}T${existingTime}`
            : rescheduleDate
          return fetch(`${API_URL}/tasks/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scheduled_date: newScheduledDate }),
          })
        })
      )
      onTasksUpdate()
      setSelectedIds(new Set())
    } catch {
      // Ignore errors
    }
    setReschedulePopup(null)
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
      task.is_template ? 'projected' : '',
      isSelected ? 'selected' : ''
    ].filter(Boolean).join(' ')

    return (
      <li
        key={task.id + (task.is_template ? '-template' : '')}
        className={classes}
        title={`Created: ${formatTaskCreationDate(task.created_at)}`}
        onMouseDown={(e) => e.shiftKey && e.preventDefault()}
        onClick={(e) => handleRowActivate(task, indexInOrdered, e)}
      >
        <input
          type="checkbox"
          className="task-checkbox"
          checked={task.completed}
          onChange={() => handleToggle(task)}
          onClick={(e) => e.stopPropagation()}
        />
        <span className="task-key">{task.task_key}</span>
        <PriorityBadge priority={task.priority} />
        <span className="task-title">{task.title}</span>
        {formatDuration(task.duration_minutes) && (
          <span className="task-duration">{formatDuration(task.duration_minutes)}</span>
        )}
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
          onClick={(e) => { e.stopPropagation(); handleDelete(task, e) }}
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
    const layouts = computeColumnLayout(timedTasks)
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

              const isDraggingThis = draggingTaskId === task.id
              const classes = [
                'calendar-task-block',
                task.completed ? 'completed' : '',
                task.is_template ? 'projected' : '',
                isSelected ? 'selected' : '',
                isDraggingThis ? 'dragging' : '',
              ].filter(Boolean).join(' ')

              const { colIndex, colCount } = layouts[i]
              // When overlapping, divide horizontal space into columns.
              // LABEL_WIDTH + RIGHT_PAD (63px total) match CSS .calendar-hour-label and right: 8px
              const overlapStyle = colCount > 1 ? {
                left: `calc(${LABEL_WIDTH}px + ${colIndex} * (100% - ${LABEL_WIDTH + RIGHT_PAD}px) / ${colCount})`,
                right: 'auto',
                width: `calc((100% - ${LABEL_WIDTH + RIGHT_PAD}px) / ${colCount})`,
              } : {}

              return (
                <div
                  key={task.id + (task.is_template ? '-template' : '')}
                  className={classes}
                  data-task-id={task.id}
                  title={`Created: ${formatTaskCreationDate(task.created_at)}`}
                  ref={(el) => {
                    if (el) taskBlockRefsMap.current.set(task.id, el)
                    else taskBlockRefsMap.current.delete(task.id)
                  }}
                  style={{ top: topPx, height: Math.max(heightPx, 16), ...overlapStyle }}
                  onMouseDown={(e) => e.shiftKey && e.preventDefault()}
                  onClick={(e) => {
                    if (dragJustFinishedRef.current) { dragJustFinishedRef.current = false; return }
                    handleSelectBoxClick(task, indexInOrdered, e)
                  }}
                  onPointerDown={(e) => handleDragStart(e, task, topPx)}
                  onPointerMove={handleDragMove}
                  onPointerUp={(e) => handleDragEnd(e, task)}
                  onPointerCancel={handleDragCancel}
                >
                  <input
                    type="checkbox"
                    className="task-checkbox"
                    checked={task.completed}
                    onChange={() => handleToggle(task)}
                    onClick={(e) => e.stopPropagation()}
                  />
                  <span className="calendar-task-key">{task.task_key}</span>
                  <PriorityBadge priority={task.priority} />
                  <span className="calendar-task-title">{task.title}</span>
                  <button
                    type="button"
                    className="task-delete-btn"
                    aria-label="Delete task"
                    onClick={(e) => { e.stopPropagation(); handleDelete(task, e) }}
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
        <div className={`day-view-toggle${uxV2 ? ' day-view-toggle--v2' : ''}`}>
          <div className="day-view-toggle-tabs">
            <button
              className={dayViewMode === 'list' ? 'active' : ''}
              onClick={() => setDayViewMode('list')}
            >List</button>
            <button
              className={dayViewMode === 'calendar' ? 'active' : ''}
              onClick={() => setDayViewMode('calendar')}
            >Calendar</button>
          </div>
          {uxV2 && (
            <span className="dbl-click-hint">Double-click a task to edit</span>
          )}
          {selectedIds.size > 0 && (
            <div className={`day-view-actions${uxV2 ? ' day-view-actions--v2' : ''}`}>
              <button type="button" className="reschedule-selected-btn" onClick={openReschedulePopup}>
                Reschedule
              </button>
              {selectedIds.size > 1 && (
                <button type="button" className="delete-selected-btn" onClick={handleDeleteSelected}>
                  <TrashIcon /> Delete
                </button>
              )}
              {/* Slot reserved for "Move to backlog" — tracked as Issue 5 */}
            </div>
          )}
        </div>
        {dayViewMode === 'list' ? (
          isEmpty && overdueTasks.length === 0 ? (
            <p className="empty-state">No tasks for this day.</p>
          ) : (
            <>
              {(() => {
                // Overdue first (only populated when viewing today, per App.tsx).
                // showDate=true on overdue rows so users see the original scheduled date.
                const ordered = [...overdueTasks, ...meetings, ...daily, ...other]
                orderedVisibleTasksRef.current = ordered
                let idx = 0
                const overdueSection = renderSection('Overdue', overdueTasks, true, idx)
                idx += overdueTasks.length
                const meetingsSection = renderSection('Meetings', meetings, false, idx)
                idx += meetings.length
                const dailySection = renderSection('Daily', daily, false, idx)
                idx += daily.length
                const otherSection = renderSection('Tasks', other, false, idx)
                return (
                  <>
                    {overdueSection}
                    {meetingsSection}
                    {dailySection}
                    {otherSection}
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
    // — All Tasks: show templates (templates have completed=false)
    // — Completed: show completed instances that have recurrence_rule (came from templates)
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

  function renderBacklogView() {
    const meetings = tasks.filter(t =>
      t.category === 'M' && !t.is_template && !t.completed && !t.scheduled_date
    )
    const regularTasks = tasks.filter(t =>
      t.category === 'T' && !t.is_template && !t.completed && !t.scheduled_date
    )
    const projectTasks = tasks.filter(t =>
      !t.is_template && !['M', 'T', 'D'].includes(t.category) && !t.completed && !t.scheduled_date
    )
    const projectCategories = [...new Set(projectTasks.map(t => t.category))].sort()

    const isEmpty = meetings.length === 0 && regularTasks.length === 0 && projectTasks.length === 0
    const ordered: Task[] = [
      ...meetings,
      ...regularTasks,
      ...projectCategories.flatMap(cat => projectTasks.filter(t => t.category === cat)),
    ]
    orderedVisibleTasksRef.current = ordered

    let sectionStart = 0
    return (
      <>
        {isEmpty ? (
          <p className="empty-state">No backlog tasks.</p>
        ) : (
          <>
            {renderSection('Meetings', meetings, true, sectionStart)}
            {renderSection('Tasks', regularTasks, true, sectionStart += meetings.length)}
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
      <div className={`tab-bar${uxV2 ? ' tab-bar--v2' : ''}`}>
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
        <button
          className={`tab ${viewMode === 'backlog' ? 'active' : ''}`}
          onClick={() => onViewModeChange('backlog')}
        >
          Backlog
        </button>
      </div>

      {confirmDelete && (
        <div
          className="confirm-popup"
          style={{
            left: confirmDelete.x,
            top: Math.max(8, Math.min(confirmDelete.y, window.innerHeight - 100)),
            transform: 'translateX(-100%)',
          }}
        >
          <p className="confirm-message">{confirmDelete.message}</p>
          <div className="confirm-actions">
            <button type="button" className="confirm-cancel-btn" onClick={() => setConfirmDelete(null)}>Cancel</button>
            <button type="button" className="confirm-delete-btn" onClick={() => confirmDeleteAction(confirmDelete.ids)}>Delete</button>
          </div>
        </div>
      )}

      {reschedulePopup && (
        <div
          className="confirm-popup reschedule-popup"
          style={{
            left: reschedulePopup.x,
            top: Math.max(8, Math.min(reschedulePopup.y, window.innerHeight - 160)),
            transform: 'translateX(-100%)',
          }}
        >
          <p className="confirm-message">Reschedule {selectedIds.size} task{selectedIds.size !== 1 ? 's' : ''}</p>
          <div className="reschedule-fields">
            <label className="reschedule-label">
              Date
              <input
                type="date"
                className="reschedule-input"
                value={rescheduleDate}
                onChange={e => setRescheduleDate(e.target.value)}
              />
            </label>
          </div>
          <div className="confirm-actions">
            <button type="button" className="confirm-cancel-btn" onClick={() => setReschedulePopup(null)}>Cancel</button>
            <button type="button" className="confirm-delete-btn" onClick={applyReschedule} disabled={!rescheduleDate}>Apply</button>
          </div>
        </div>
      )}

      <div className="tab-content">
        {viewMode === 'day' && renderDayView()}
        {viewMode === 'all' && renderAllTasksView(false)}
        {viewMode === 'completed' && renderAllTasksView(true)}
        {viewMode === 'backlog' && renderBacklogView()}
      </div>

      {selectedTask && (
        <TaskModal
          task={selectedTask}
          onClose={() => setSelectedTask(null)}
          onSave={(updated) => {
            setSelectedTask(null)
            onTasksUpdate()
            // Suppress the stale "title" that triggered the double-click
            void updated
          }}
          onDelete={(_id) => {
            setSelectedTask(null)
            onTasksUpdate()
          }}
        />
      )}
    </div>
  )
}

export default TaskList
