import { useState, useEffect } from 'react'
import TaskList from './components/TaskList'
import ChatInterface from './components/ChatInterface'
import SettingsModal from './components/SettingsModal'

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
  priority: number | null  // 0=None, 1=Low, 2=Medium, 3=High, 4=Critical
  projected?: boolean
}

type ViewMode = 'day' | 'all' | 'completed' | 'backlog'

const API_URL = 'http://localhost:8000'

// Helper to format Date to YYYY-MM-DD
function formatDateStr(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [viewMode, setViewMode] = useState<ViewMode>('day')
  const [showSettings, setShowSettings] = useState(false)
  
  const CHAT_COLLAPSED_KEY = 'chatCollapsed'
  const [chatCollapsed, setChatCollapsed] = useState<boolean>(() => {
    return localStorage.getItem(CHAT_COLLAPSED_KEY) === 'true'
  })

  function handleToggleChat() {
    setChatCollapsed(prev => {
      const next = !prev
      localStorage.setItem(CHAT_COLLAPSED_KEY, String(next))
      return next
    })
  }

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
        <h1><img src="/hakadorio-logo.png" alt="hakadorio" className="header-logo" />Hakadorio</h1>
        <button className="header-settings-btn" onClick={() => setShowSettings(true)} aria-label="Settings">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </button>
      </header>
      {showSettings && (
        <SettingsModal
          onClose={() => setShowSettings(false)}
          taskCategories={[...new Set(tasks.map(t => t.category))]}
        />
      )}
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
        <ChatInterface onTasksUpdate={handleTasksUpdate} collapsed={chatCollapsed} onToggleCollapse={handleToggleChat} />
      </main>
    </div>
  )
}

export default App
