import { useState, useEffect } from 'react'
import TaskList from './components/TaskList'
import ChatInterface from './components/ChatInterface'

// Assumption: Task matches backend Task model
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
}

const API_URL = 'http://localhost:8000'

function App() {
  const [tasks, setTasks] = useState<Task[]>([])

  useEffect(() => {
    fetchTasks()
  }, [])

  async function fetchTasks() {
    try {
      const res = await fetch(`${API_URL}/tasks`)
      const data = await res.json()
      setTasks(data)
    } catch (err) {
      console.error('Failed to fetch tasks:', err)
    }
  }

  function handleTasksUpdate(newTasks: Task[]) {
    setTasks(newTasks)
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Deskbot</h1>
      </header>
      <main className="main">
        <TaskList tasks={tasks} onTasksUpdate={handleTasksUpdate} />
        <ChatInterface onTasksUpdate={handleTasksUpdate} />
      </main>
    </div>
  )
}

export default App
