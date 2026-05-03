// Tests for #91: Task detail modal on double-click (flag ON)
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TaskList from '../components/TaskList'
import { setupFetchMock } from '../test/mocks/server'
import { setFlag } from '../featureFlags'
import { TASK_A, TASK_B, FOR_DATE_TASKS, TODAY } from '../test/fixtures/tasks'

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

describe('#91 — Task detail modal', () => {
  beforeEach(() => {
    setupFetchMock()
    setFlag('ux_v2', true)
    setFlag('ux_v2.task_modal', true)
    defaultProps.onTasksUpdate.mockReset()
  })

  afterEach(() => {
    setFlag('ux_v2', false)
    setFlag('ux_v2.task_modal', true)
    localStorage.removeItem('ff:ux_v2')
    localStorage.removeItem('ff:ux_v2.task_modal')
  })

  it('double-click opens TaskModal with task values pre-filled', async () => {
    const user = userEvent.setup({ delay: null })
    render(<TaskList {...defaultProps} tasks={[TASK_A]} />)
    const row = screen.getByText(TASK_A.title)
    await user.dblClick(row)
    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: /edit task/i })).toBeInTheDocument()
    })
    expect(screen.getByDisplayValue(TASK_A.title)).toBeInTheDocument()
  })

  it('single-click still selects the task (no modal)', async () => {
    const user = userEvent.setup({ delay: null })
    const { container } = render(<TaskList {...defaultProps} tasks={[TASK_A, TASK_B]} />)
    await user.click(screen.getByText(TASK_A.title))
    // wait for click timer to fire (300ms)
    await act(() => new Promise(r => setTimeout(r, 350)))
    expect(container.querySelector('.task-item.selected')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('Save in modal fires PATCH and calls onTasksUpdate', async () => {
    const user = userEvent.setup({ delay: null })
    render(<TaskList {...defaultProps} tasks={[TASK_A]} />)
    await user.dblClick(screen.getByText(TASK_A.title))
    await waitFor(() => screen.getByRole('dialog'))
    // Clear and retype title
    const titleInput = screen.getByDisplayValue(TASK_A.title)
    await user.clear(titleInput)
    await user.type(titleInput, 'Updated title')
    await user.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u, i]: [string, RequestInit]) =>
        u.includes(`/tasks/${TASK_A.id}`) && i?.method === 'PATCH'
      )).toBe(true)
    })
    expect(defaultProps.onTasksUpdate).toHaveBeenCalled()
  })

  it('Delete in modal fires DELETE and calls onTasksUpdate', async () => {
    const user = userEvent.setup({ delay: null })
    render(<TaskList {...defaultProps} tasks={[TASK_A]} />)
    await user.dblClick(screen.getByText(TASK_A.title))
    await waitFor(() => screen.getByRole('dialog'))
    await user.click(screen.getByRole('button', { name: /^delete$/i }))
    await user.click(screen.getByRole('button', { name: /yes, delete/i }))
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u, i]: [string, RequestInit]) =>
        u.includes(`/tasks/${TASK_A.id}`) && i?.method === 'DELETE'
      )).toBe(true)
    })
    expect(defaultProps.onTasksUpdate).toHaveBeenCalled()
  })

  it('modal does NOT open when ux_v2.task_modal=false', async () => {
    setFlag('ux_v2.task_modal', false)
    const user = userEvent.setup({ delay: null })
    render(<TaskList {...defaultProps} tasks={[TASK_A]} />)
    await user.dblClick(screen.getByText(TASK_A.title))
    await act(() => new Promise(r => setTimeout(r, 350)))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
