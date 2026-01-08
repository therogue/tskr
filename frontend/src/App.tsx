import { useState, useEffect } from 'react'
import TaskList from './components/TaskList'
import ChatInterface from './components/ChatInterface'

// Assumption: Task matches backend Task model
interface Task {
  id: string
  title: string
  completed: boolean
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
        <TaskList tasks={tasks} />
        <ChatInterface onTasksUpdate={handleTasksUpdate} />
      </main>
    </div>
  )
}

export default App
