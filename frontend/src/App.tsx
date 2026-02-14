import { useState, useEffect } from 'react'
import TaskList from './components/TaskList'
import ChatInterface from './components/ChatInterface'

// Assumption: Task matches backend Task model, with optional projected field
interface Task {
  id: string
  task_key: string
  category: string
  task_number: number
  title: string
  completed: boolean
  scheduled_date: string | null  // YYYY-MM-DD or YYYY-MM-DDTHH:MM
  recurrence_rule: string | null
  created_at: string
  is_template: boolean
  parent_task_id: string | null
  duration_minutes: number | null
  projected?: boolean
}

type ViewMode = 'day' | 'all' | 'completed'

const API_URL = 'http://localhost:8000'

// Helper to format Date to YYYY-MM-DD
function formatDateStr(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [viewMode, setViewMode] = useState<ViewMode>('day')

  // Get today's date in YYYY-MM-DD format
  const todayStr = formatDateStr(new Date())
  const [selectedDate, setSelectedDate] = useState<string>(todayStr)

  useEffect(() => {
    fetchTasks()
  }, [viewMode, selectedDate])

  async function fetchTasks() {
    try {
      // Day view uses date-specific endpoint, others use /tasks
      const url = viewMode === 'day'
        ? `${API_URL}/tasks/for-date?date=${selectedDate}`
        : `${API_URL}/tasks`
      const res = await fetch(url)
      const data = await res.json()
      setTasks(data)
    } catch (err) {
      console.error('Failed to fetch tasks:', err)
    }
  }

  function handleTasksUpdate() {
    // Refetch tasks after any update
    fetchTasks()
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Tskr</h1>
      </header>
      <main className="main">
        <TaskList
          tasks={tasks}
          viewMode={viewMode}
          selectedDate={selectedDate}
          todayStr={todayStr}
          onViewModeChange={setViewMode}
          onDateChange={setSelectedDate}
          onTasksUpdate={handleTasksUpdate}
        />
        <ChatInterface onTasksUpdate={handleTasksUpdate} />
      </main>
    </div>
  )
}

export default App
