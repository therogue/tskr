import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import QuickEntry from '../components/QuickEntry'
import { setupFetchMock } from '../test/mocks/server'

const defaultProps = {
  onClose: vi.fn(),
  onTasksUpdate: vi.fn(),
}

describe('QuickEntry', () => {
  beforeEach(() => {
    setupFetchMock()
    defaultProps.onClose.mockReset()
    defaultProps.onTasksUpdate.mockReset()
  })

  it('renders the text input', () => {
    render(<QuickEntry {...defaultProps} />)
    expect(screen.getByPlaceholderText(/create a task/i)).toBeInTheDocument()
  })

  it('auto-focuses the input on render', () => {
    render(<QuickEntry {...defaultProps} />)
    expect(screen.getByPlaceholderText(/create a task/i)).toHaveFocus()
  })

  it('closes on Escape key', async () => {
    render(<QuickEntry {...defaultProps} />)
    await userEvent.keyboard('{Escape}')
    expect(defaultProps.onClose).toHaveBeenCalledTimes(1)
  })

  it('submits on Enter, fires /conversation/new then /chat, calls onTasksUpdate', async () => {
    const user = userEvent.setup()
    render(<QuickEntry {...defaultProps} />)
    await user.type(screen.getByPlaceholderText(/create a task/i), 'Add gym{Enter}')
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u, i]: [string, RequestInit]) =>
        u.includes('/conversation/new') && i?.method === 'POST'
      )).toBe(true)
      expect(calls.some(([u, i]: [string, RequestInit]) =>
        u.endsWith('/chat') && i?.method === 'POST'
      )).toBe(true)
    })
    expect(defaultProps.onTasksUpdate).toHaveBeenCalled()
  })
})
