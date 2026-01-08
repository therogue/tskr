interface Task {
  id: string
  title: string
  completed: boolean
  created_at: string
}

interface TaskListProps {
  tasks: Task[]
}

function TaskList({ tasks }: TaskListProps) {
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
                readOnly
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
