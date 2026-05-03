// Productive widgets panel — sits in the right column (v2 layout).
// All data comes from the tasks prop; no new API calls.
//
// NOTE (weekly bars): uses completed && scheduled_date as a proxy for
// "completed on that day" since the Task model has no completed_at timestamp.
// A future backend change to add completed_at would improve accuracy.

import { useMemo } from 'react'
import ProgressRing from './ProgressRing'
import Icon from './Icon'

interface Task {
  id: string
  title: string
  completed: boolean
  scheduled_date: string | null
  duration_minutes: number | null
  priority: number | null
  is_template?: boolean
}

interface WidgetPanelProps {
  tasks: Task[]
  selectedDate: string
  onOpenChat: () => void
}

const PRIORITY_COLOR: Record<number, string> = {
  4: '#e74c3c',
  3: '#e67e22',
  2: '#f1c40f',
  1: '#2ecc71',
  0: '#607080',
}

function getISOWeekStart(dateStr: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  const day = date.getDay()
  const diff = day === 0 ? -6 : 1 - day // Monday=0
  const monday = new Date(date)
  monday.setDate(date.getDate() + diff)
  return monday
}

function isoDateStr(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function formatTimeLeft(scheduledDate: string): string {
  const [, timePart] = scheduledDate.split('T')
  if (!timePart) return ''
  const [h, m] = timePart.split(':').map(Number)
  const taskMinutes = h * 60 + m
  const now = new Date()
  const nowMinutes = now.getHours() * 60 + now.getMinutes()
  const diff = taskMinutes - nowMinutes
  if (diff <= 0) return 'Now'
  const dh = Math.floor(diff / 60)
  const dm = diff % 60
  if (dh > 0 && dm > 0) return `in ${dh}h ${dm}m`
  if (dh > 0) return `in ${dh}h`
  return `in ${dm}m`
}

function WidgetPanel({ tasks, selectedDate, onOpenChat }: WidgetPanelProps) {
  // Today's Progress
  const todayTasks = useMemo(
    () => tasks.filter(t => !t.is_template && t.scheduled_date?.slice(0, 10) === selectedDate),
    [tasks, selectedDate]
  )
  const doneTasks = todayTasks.filter(t => t.completed)
  const lastDone = doneTasks.length > 0 ? doneTasks[doneTasks.length - 1] : null

  // Next Up: first uncompleted timed task today, sorted by scheduled_time
  const nextUp = useMemo(() => {
    return tasks
      .filter(t => !t.completed && t.scheduled_date?.includes('T') && t.scheduled_date?.slice(0, 10) === selectedDate)
      .sort((a, b) => (a.scheduled_date ?? '').localeCompare(b.scheduled_date ?? ''))[0] ?? null
  }, [tasks, selectedDate])

  // This Week: bar chart — completed tasks per day for the current ISO week
  const weekBars = useMemo(() => {
    const monday = getISOWeekStart(selectedDate)
    return Array.from({ length: 7 }, (_, i) => {
      const day = new Date(monday)
      day.setDate(monday.getDate() + i)
      const dayStr = isoDateStr(day)
      return tasks.filter(t => t.completed && t.scheduled_date?.slice(0, 10) === dayStr).length
    })
  }, [tasks, selectedDate])

  const maxBar = Math.max(...weekBars, 1)
  const DAY_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']

  // Compare with last week
  const lastWeekBars = useMemo(() => {
    const monday = getISOWeekStart(selectedDate)
    return Array.from({ length: 7 }, (_, i) => {
      const day = new Date(monday)
      day.setDate(monday.getDate() + i - 7)
      const dayStr = isoDateStr(day)
      return tasks.filter(t => t.completed && t.scheduled_date?.slice(0, 10) === dayStr).length
    })
  }, [tasks, selectedDate])

  const thisWeekTotal = weekBars.reduce((a, b) => a + b, 0)
  const lastWeekTotal = lastWeekBars.reduce((a, b) => a + b, 0)
  const weekDiff = lastWeekTotal > 0
    ? Math.round(((thisWeekTotal - lastWeekTotal) / lastWeekTotal) * 100)
    : null

  return (
    <div className="widget-panel">
      <div className="widget-panel-header">
        <span className="widget-panel-title">Dashboard</span>
        <button className="widget-ask-ai-btn" onClick={onOpenChat} type="button">
          <Icon n="sparkle" size={14} />
          Ask AI
        </button>
      </div>

      {/* Widget 1: Today's Progress */}
      <div className="widget-card" data-testid="widget-progress">
        <div className="widget-card-header">
          <span className="widget-card-label">Today's Progress</span>
        </div>
        <div className="widget-progress-body">
          <ProgressRing done={doneTasks.length} total={todayTasks.length} />
          <div className="widget-progress-info">
            <div className="widget-progress-count">
              <span className="widget-progress-done">{doneTasks.length}</span>
              <span className="widget-progress-sep">/</span>
              <span className="widget-progress-total">{todayTasks.length}</span>
              <span className="widget-progress-label">tasks</span>
            </div>
            {lastDone && (
              <div className="widget-progress-last">
                Last: <span>{lastDone.title}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Widget 2: Next Up */}
      <div className="widget-card" data-testid="widget-next-up">
        <div className="widget-card-header">
          <span className="widget-card-label">Next Up</span>
        </div>
        {nextUp ? (
          <div className="widget-next-up">
            <div
              className="widget-next-priority-bar"
              style={{ background: PRIORITY_COLOR[nextUp.priority ?? 0] ?? PRIORITY_COLOR[0] }}
            />
            <div className="widget-next-content">
              <span className="widget-next-title">{nextUp.title}</span>
              <div className="widget-next-meta">
                {nextUp.scheduled_date && (
                  <span className="widget-next-time">{nextUp.scheduled_date.slice(11, 16)}</span>
                )}
                {nextUp.duration_minutes && (
                  <span className="widget-next-duration">{nextUp.duration_minutes}m</span>
                )}
                {nextUp.scheduled_date && (
                  <span className="widget-next-badge">{formatTimeLeft(nextUp.scheduled_date)}</span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <p className="widget-empty-text">No upcoming tasks today.</p>
        )}
      </div>

      {/* Widget 3: This Week */}
      <div className="widget-card" data-testid="widget-week">
        <div className="widget-card-header">
          <span className="widget-card-label">This Week</span>
          {weekDiff !== null && (
            <span className={`widget-week-diff ${weekDiff >= 0 ? 'positive' : 'negative'}`}>
              {weekDiff >= 0 ? '↑' : '↓'} {Math.abs(weekDiff)}% vs last week
            </span>
          )}
        </div>
        <div className="widget-week-bars">
          {weekBars.map((count, i) => (
            <div key={i} className="widget-week-bar-col">
              <div
                className="widget-week-bar"
                style={{ height: `${Math.round((count / maxBar) * 44)}px` }}
                title={`${DAY_LABELS[i]}: ${count} task${count !== 1 ? 's' : ''}`}
              />
              <span className="widget-week-day">{DAY_LABELS[i]}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default WidgetPanel
