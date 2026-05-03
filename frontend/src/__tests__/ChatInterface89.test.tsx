// Tests for #89: Chat overlay (ux_v2.chat_overlay=true)
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatInterface from '../components/ChatInterface'
import { setupFetchMock } from '../test/mocks/server'
import { setFlag } from '../featureFlags'
import { CONVERSATIONS_RECENT } from '../test/fixtures/tasks'

const defaultProps = {
  onTasksUpdate: vi.fn(),
  visible: false,
  onClose: vi.fn(),
}

describe('#89 — Chat overlay (ux_v2 + ux_v2.chat_overlay)', () => {
  beforeEach(() => {
    setupFetchMock()
    setFlag('ux_v2', true)
    setFlag('ux_v2.chat_overlay', true)
    defaultProps.onTasksUpdate.mockReset()
    defaultProps.onClose.mockReset()
  })

  afterEach(() => {
    setFlag('ux_v2', false)
    setFlag('ux_v2.chat_overlay', true)
    localStorage.removeItem('ff:ux_v2')
    localStorage.removeItem('ff:ux_v2.chat_overlay')
  })

  it('renders .chat-panel--overlay when ux_v2 + chat_overlay are true', () => {
    const { container } = render(<ChatInterface {...defaultProps} visible={true} />)
    expect(container.querySelector('.chat-panel--overlay')).toBeInTheDocument()
  })

  it('applies translateX(0) when visible=true', () => {
    const { container } = render(<ChatInterface {...defaultProps} visible={true} />)
    const overlay = container.querySelector('.chat-panel--overlay') as HTMLElement
    expect(overlay.style.transform).toBe('translateX(0)')
  })

  it('applies translateX(102%) when visible=false', () => {
    const { container } = render(<ChatInterface {...defaultProps} visible={false} />)
    const overlay = container.querySelector('.chat-panel--overlay') as HTMLElement
    expect(overlay.style.transform).toBe('translateX(102%)')
  })

  it('close button calls onClose', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} visible={true} />)
    await user.click(screen.getByRole('button', { name: /close chat/i }))
    expect(defaultProps.onClose).toHaveBeenCalledTimes(1)
  })

  it('history button opens HistoryDrawer (v2) with GET /conversations', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} visible={true} />)
    await user.click(screen.getByTitle(/chat history/i))
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u]: [string]) => u.includes('/conversations') && !u.includes('limit'))).toBe(true)
    })
    await waitFor(() => {
      expect(screen.getByText('All Chats')).toBeInTheDocument()
    })
  })

  it('HistoryDrawer shows conversations and switches on click', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} visible={true} />)
    await user.click(screen.getByTitle(/chat history/i))
    await waitFor(() => screen.getByText(CONVERSATIONS_RECENT[0].title))
    await user.click(screen.getByText(CONVERSATIONS_RECENT[0].title))
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u]: [string]) => u.includes(`/conversations/${CONVERSATIONS_RECENT[0].id}`))).toBe(true)
    })
  })

  it('falls back to legacy layout when chat_overlay=false', () => {
    setFlag('ux_v2.chat_overlay', false)
    const { container } = render(<ChatInterface
      onTasksUpdate={vi.fn()}
      collapsed={false}
      onToggleCollapse={vi.fn()}
    />)
    expect(container.querySelector('.chat-panel--overlay')).not.toBeInTheDocument()
    expect(container.querySelector('.chat-panel')).toBeInTheDocument()
  })
})
