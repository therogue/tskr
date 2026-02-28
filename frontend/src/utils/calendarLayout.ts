// Fallback duration when duration_minutes is null. Assumption: matches TaskList.tsx DEFAULT_DURATION.
export const DEFAULT_DURATION = 30 // minutes

// Minimal task shape required by computeColumnLayout
interface ScheduledTask {
  scheduled_date: string | null
  duration_minutes: number | null
}

/**
 * Compute horizontal column layout for overlapping timed tasks.
 * Assumption: tasks are sorted by scheduled_date ascending.
 * Assumption: scheduled_date is YYYY-MM-DDTHH:MM for all tasks passed here.
 * Returns colIndex (0-based column) and colCount (columns in this task's overlap group).
 */
export function computeColumnLayout(tasks: ScheduledTask[]): Array<{ colIndex: number; colCount: number }> {
  const n = tasks.length
  if (n === 0) return []

  const intervals = tasks.map(task => {
    const timePart = task.scheduled_date!.slice(11, 16)
    const [h, m] = timePart.split(':').map(Number)
    const start = h * 60 + m
    const duration = task.duration_minutes || DEFAULT_DURATION
    return { start, end: start + duration }
  })

  // Greedy column assignment: each task goes to the first column with no overlap
  const colEnd: number[] = []
  const colIndex: number[] = new Array(n).fill(0)
  for (let i = 0; i < n; i++) {
    const { start } = intervals[i]
    let assigned = -1
    for (let c = 0; c < colEnd.length; c++) {
      if (colEnd[c] <= start) { assigned = c; break }
    }
    if (assigned === -1) { assigned = colEnd.length; colEnd.push(0) }
    colIndex[i] = assigned
    colEnd[assigned] = intervals[i].end
  }

  // colCount per task = max colIndex+1 among all tasks that overlap with it
  const colCount: number[] = tasks.map((_, i) => {
    let maxCol = colIndex[i]
    for (let j = 0; j < n; j++) {
      if (intervals[i].start < intervals[j].end && intervals[j].start < intervals[i].end) {
        maxCol = Math.max(maxCol, colIndex[j])
      }
    }
    return maxCol + 1
  })

  return tasks.map((_, i) => ({ colIndex: colIndex[i], colCount: colCount[i] }))
}
