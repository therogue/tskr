// Tests for #90: Suggestion chips (ux_v2 + ux_v2.chat_overlay=true)
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatInterface from '../components/ChatInterface'
import { setupFetchMock } from '../test/mocks/server'
import { setFlag } from '../featureFlags'

const defaultProps = {
  onTasksUpdate: vi.fn(),
  visible: true,
  onClose: vi.fn(),
}

describe('#90 — Suggestion chips', () => {
  beforeEach(() => {
    setupFetchMock()
    setFlag('ux_v2', true)
    setFlag('ux_v2.chat_overlay', true)
    defaultProps.onTasksUpdate.mockReset()
  })

  afterEach(() => {
    setFlag('ux_v2', false)
    setFlag('ux_v2.chat_overlay', true)
    localStorage.removeItem('ff:ux_v2')
    localStorage.removeItem('ff:ux_v2.chat_overlay')
  })

  it('shows EmptyState with chips when no messages', () => {
    render(<ChatInterface {...defaultProps} />)
    expect(screen.getByText(/hi! what would you like to do/i)).toBeInTheDocument()
    // At least one chip visible
    const chips = screen.getAllByRole('button', { name: /today|tomorrow|overdue|week/i })
    expect(chips.length).toBeGreaterThan(0)
  })

  it('clicking a chip sends the prompt via POST /chat', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} />)
    const chips = screen.getAllByRole('button', { name: /today|tomorrow|overdue|week/i })
    await user.click(chips[0])
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u, i]: [string, RequestInit]) =>
        u.endsWith('/chat') && i?.method === 'POST'
      )).toBe(true)
    })
  })

  it('shows persistent chip strip above input after messages are present', async () => {
    const user = userEvent.setup()
    const { container } = render(<ChatInterface {...defaultProps} />)
    // Click a chip to send a message
    const chips = screen.getAllByRole('button', { name: /today|tomorrow|overdue|week/i })
    await user.click(chips[0])
    await waitFor(() => screen.getByText('Sure, I can help with that.'))
    // Chip strip should now be visible
    expect(container.querySelector('.chat-chips-strip')).toBeInTheDocument()
  })

  it('EmptyState is hidden when messages are present', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} />)
    const chips = screen.getAllByRole('button', { name: /today|tomorrow|overdue|week/i })
    await user.click(chips[0])
    await waitFor(() => screen.getByText('Sure, I can help with that.'))
    expect(screen.queryByText(/hi! what would you like to do/i)).not.toBeInTheDocument()
  })
})
