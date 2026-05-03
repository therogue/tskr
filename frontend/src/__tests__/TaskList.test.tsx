import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TaskList from '../components/TaskList'
import { setupFetchMock } from '../test/mocks/server'
import {
  TASK_A, TASK_B, TASK_DONE, TASK_BACKLOG, TASK_MEETING, TASK_OVERDUE,
  FOR_DATE_TASKS, ALL_TASKS, OVERDUE_TASKS, TODAY,
} from '../test/fixtures/tasks'

const defaultProps = {
  tasks: FOR_DATE_TASKS,
  overdueTasks: [],
  viewMode: 'day' as const,
  selectedDate: TODAY,
  todayStr: TODAY,
  onViewModeChange: vi.fn(),
  onDateChange: vi.fn(),
  onTasksUpdate: vi.fn(),
}

describe('TaskList — tabs', () => {
  beforeEach(() => {
    setupFetchMock()
    defaultProps.onViewModeChange.mockReset()
    defaultProps.onDateChange.mockReset()
    defaultProps.onTasksUpdate.mockReset()
  })

  it('renders all four tab buttons', () => {
    render(<TaskList {...defaultProps} />)
    expect(screen.getByRole('button', { name: /day view/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /all tasks/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /completed/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /backlog/i })).toBeInTheDocument()
  })

  it('clicking a tab calls onViewModeChange', async () => {
    const user = userEvent.setup()
    render(<TaskList {...defaultProps} />)
    await user.click(screen.getByRole('button', { name: /all tasks/i }))
    expect(defaultProps.onViewModeChange).toHaveBeenCalledWith('all')
  })

  it('active tab has the active class', () => {
    render(<TaskList {...defaultProps} viewMode="backlog" />)
    const backlogBtn = screen.getByRole('button', { name: /backlog/i })
    expect(backlogBtn).toHaveClass('active')
  })
})

describe('TaskList — Day view list', () => {
  beforeEach(() => {
    setupFetchMock()
    defaultProps.onViewModeChange.mockReset()
    defaultProps.onTasksUpdate.mockReset()
  })

  it('renders tasks in Day view', () => {
    render(<TaskList {...defaultProps} />)
    expect(screen.getByText(TASK_A.title)).toBeInTheDocument()
    expect(screen.getByText(TASK_B.title)).toBeInTheDocument()
  })

  it('renders Meetings section when meeting tasks exist', () => {
    render(<TaskList {...defaultProps} tasks={FOR_DATE_TASKS} />)
    expect(screen.getByText('Meetings')).toBeInTheDocument()
    expect(screen.getByText(TASK_MEETING.title)).toBeInTheDocument()
  })

  it('renders Overdue section when overdue tasks are provided', () => {
    render(<TaskList {...defaultProps} overdueTasks={OVERDUE_TASKS} />)
    expect(screen.getByText('Overdue')).toBeInTheDocument()
    expect(screen.getByText(TASK_OVERDUE.title)).toBeInTheDocument()
  })

  it('checkbox calls PATCH on toggle', async () => {
    const user = userEvent.setup()
    render(<TaskList {...defaultProps} tasks={[TASK_A]} />)
    const checkbox = screen.getAllByRole('checkbox')[0]
    await user.click(checkbox)
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u, i]: [string, RequestInit]) =>
        u.includes(`/tasks/${TASK_A.id}`) && i?.method === 'PATCH'
      )).toBe(true)
    })
  })

  it('clicking a task row selects it (adds selected class)', async () => {
    const user = userEvent.setup()
    const { container } = render(<TaskList {...defaultProps} tasks={[TASK_A, TASK_B]} />)
    await user.click(screen.getByText(TASK_A.title))
    const taskItem = container.querySelector('.task-item.selected')
    expect(taskItem).toBeInTheDocument()
  })

  it('Ctrl+click toggles selection on a second row', async () => {
    const user = userEvent.setup()
    const { container } = render(<TaskList {...defaultProps} tasks={[TASK_A, TASK_B]} />)
    await user.click(screen.getByText(TASK_A.title))
    await user.keyboard('{Control>}')
    await user.click(screen.getByText(TASK_B.title))
    await user.keyboard('{/Control}')
    const selected = container.querySelectorAll('.task-item.selected')
    expect(selected.length).toBe(2)
  })

  it('Reschedule button appears when ≥1 task selected', async () => {
    const user = userEvent.setup()
    render(<TaskList {...defaultProps} tasks={[TASK_A, TASK_B]} />)
    await user.click(screen.getByText(TASK_A.title))
    expect(screen.getByRole('button', { name: /reschedule/i })).toBeInTheDocument()
  })

  it('Bulk Delete button appears only when ≥2 tasks selected', async () => {
    const user = userEvent.setup()
    const { container } = render(<TaskList {...defaultProps} tasks={[TASK_A, TASK_B]} />)
    // One selected — bulk delete button (.delete-selected-btn) should not be present
    await user.click(screen.getByText(TASK_A.title))
    expect(container.querySelector('.delete-selected-btn')).not.toBeInTheDocument()
    // Two selected — bulk delete appears
    await user.keyboard('{Control>}')
    await user.click(screen.getByText(TASK_B.title))
    await user.keyboard('{/Control}')
    expect(container.querySelector('.delete-selected-btn')).toBeInTheDocument()
  })

  it('per-row trash button opens confirm popup', async () => {
    const user = userEvent.setup()
    render(<TaskList {...defaultProps} tasks={[TASK_A]} />)
    await user.click(screen.getByRole('button', { name: /delete task/i }))
    expect(screen.getByText(/are you sure/i)).toBeInTheDocument()
  })

  it('confirming delete calls DELETE endpoint', async () => {
    const user = userEvent.setup()
    const { container } = render(<TaskList {...defaultProps} tasks={[TASK_A]} />)
    await user.click(screen.getByRole('button', { name: /delete task/i }))
    await waitFor(() => screen.getByText(/are you sure/i))
    // Confirm button has class confirm-delete-btn and text "Delete"
    await user.click(container.querySelector('.confirm-delete-btn')!)
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u, i]: [string, RequestInit]) =>
        u.includes(`/tasks/${TASK_A.id}`) && i?.method === 'DELETE'
      )).toBe(true)
    })
  })

  it('task row has a title attribute containing creation date', () => {
    render(<TaskList {...defaultProps} tasks={[TASK_A]} />)
    const row = screen.getByTitle(/created:/i)
    expect(row).toBeInTheDocument()
  })

  it('switching to another tab clears selection', async () => {
    const user = userEvent.setup()
    const { container, rerender } = render(<TaskList {...defaultProps} tasks={[TASK_A, TASK_B]} />)
    await user.click(screen.getByText(TASK_A.title))
    expect(container.querySelector('.task-item.selected')).toBeInTheDocument()
    rerender(<TaskList {...defaultProps} tasks={ALL_TASKS} viewMode="all" />)
    expect(container.querySelector('.task-item.selected')).not.toBeInTheDocument()
  })
})

describe('TaskList — Day view calendar', () => {
  beforeEach(() => {
    setupFetchMock()
    defaultProps.onTasksUpdate.mockReset()
  })

  it('switches to Calendar view when Calendar button is clicked', async () => {
    const user = userEvent.setup()
    const { container } = render(<TaskList {...defaultProps} />)
    await user.click(screen.getByRole('button', { name: /calendar/i }))
    expect(container.querySelector('.calendar-container')).toBeInTheDocument()
  })

  it('renders a timed task block in the calendar grid', async () => {
    const user = userEvent.setup()
    const { container } = render(<TaskList {...defaultProps} tasks={[TASK_A]} />)
    await user.click(screen.getByRole('button', { name: /calendar/i }))
    const block = container.querySelector('[data-task-id]')
    expect(block).toBeInTheDocument()
  })

  it('timed task block has a positive top style value (positioned)', async () => {
    const user = userEvent.setup()
    const { container } = render(<TaskList {...defaultProps} tasks={[TASK_A]} />)
    await user.click(screen.getByRole('button', { name: /calendar/i }))
    const block = container.querySelector('[data-task-id]') as HTMLElement | null
    expect(block).not.toBeNull()
    const top = parseInt(block!.style.top || '0', 10)
    expect(top).toBeGreaterThan(0) // 10:00 = 600px
  })
})

describe('TaskList — All Tasks view', () => {
  beforeEach(() => {
    setupFetchMock()
  })

  it('shows all incomplete tasks and templates in All Tasks view', () => {
    const allIncompleteTasks = ALL_TASKS.filter(t => !t.completed && !t.is_template)
    render(<TaskList {...defaultProps} tasks={allIncompleteTasks} viewMode="all" />)
    expect(screen.getByText(TASK_A.title)).toBeInTheDocument()
    expect(screen.queryByText(TASK_DONE.title)).not.toBeInTheDocument()
  })
})

describe('TaskList — Completed view', () => {
  beforeEach(() => {
    setupFetchMock()
  })

  it('shows completed tasks in Completed view', () => {
    const completedTasks = ALL_TASKS.filter(t => t.completed)
    render(<TaskList {...defaultProps} tasks={completedTasks} viewMode="completed" />)
    expect(screen.getByText(TASK_DONE.title)).toBeInTheDocument()
  })
})

describe('TaskList — Backlog view', () => {
  beforeEach(() => {
    setupFetchMock()
  })

  it('shows unscheduled tasks in Backlog view', () => {
    const backlogTasks = ALL_TASKS.filter(t => !t.scheduled_date && !t.completed)
    render(<TaskList {...defaultProps} tasks={backlogTasks} viewMode="backlog" />)
    expect(screen.getByText(TASK_BACKLOG.title)).toBeInTheDocument()
  })
})
