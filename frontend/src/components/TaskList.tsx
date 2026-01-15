interface Task {
  id: string
  title: string
  completed: boolean
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
        // Refresh tasks list
        const tasksRes = await fetch(`${API_URL}/tasks`)
        const updatedTasks = await tasksRes.json()
        onTasksUpdate(updatedTasks)
      }
    } catch (err) {
      // Ignore errors
    }
  }

  return (
    <div className="task-panel">
      <h2>Tasks</h2>
      {tasks.length === 0 ? (
        <p className="empty-state">No tasks yet. Chat with the AI to create tasks.</p>
      ) : (
        <ul className="task-list">
          {tasks.map((task) => (
            <li key={task.id} className={`task-item ${task.completed ? 'completed' : ''}`}>
              <input
                type="checkbox"
                className="task-checkbox"
                checked={task.completed}
                onChange={() => handleToggle(task)}
              />
              <span className="task-title">{task.title}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default TaskList
