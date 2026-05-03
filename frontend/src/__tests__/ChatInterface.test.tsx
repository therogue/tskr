import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatInterface from '../components/ChatInterface'
import { setupFetchMock } from '../test/mocks/server'
import { CONVERSATIONS_RECENT, CONVERSATION_1 } from '../test/fixtures/tasks'

const defaultProps = {
  onTasksUpdate: vi.fn(),
  collapsed: false,
  onToggleCollapse: vi.fn(),
}

describe('ChatInterface', () => {
  beforeEach(() => {
    setupFetchMock()
    defaultProps.onTasksUpdate.mockReset()
    defaultProps.onToggleCollapse.mockReset()
  })

  it('fires POST /conversation/new on mount', async () => {
    render(<ChatInterface {...defaultProps} />)
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u, i]: [string, RequestInit]) =>
        u.includes('/conversation/new') && i?.method === 'POST'
      )).toBe(true)
    })
  })

  it('renders the chat panel heading', () => {
    render(<ChatInterface {...defaultProps} />)
    expect(screen.getByRole('heading', { name: /^chat$/i })).toBeInTheDocument()
  })

  it('send button is not disabled when loading is false (current behavior: disabled only during load)', () => {
    render(<ChatInterface {...defaultProps} />)
    expect(screen.getByRole('button', { name: /send/i })).not.toBeDisabled()
  })

  it('sends message on form submit', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} />)
    const input = screen.getByPlaceholderText(/ask me/i)
    await user.type(input, 'Hello')
    await user.click(screen.getByRole('button', { name: /send/i }))
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u, i]: [string, RequestInit]) =>
        u.includes('/chat') && i?.method === 'POST'
      )).toBe(true)
    })
  })

  it('calls onTasksUpdate after receiving a response', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} />)
    const input = screen.getByPlaceholderText(/ask me/i)
    await user.type(input, 'Hi')
    await user.click(screen.getByRole('button', { name: /send/i }))
    await waitFor(() => {
      expect(defaultProps.onTasksUpdate).toHaveBeenCalled()
    })
  })

  it('shows assistant response bubble', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} />)
    const input = screen.getByPlaceholderText(/ask me/i)
    await user.type(input, 'Hi')
    await user.click(screen.getByRole('button', { name: /send/i }))
    await waitFor(() => {
      expect(screen.getByText('Sure, I can help with that.')).toBeInTheDocument()
    })
  })

  it('shows typing indicator text while loading', async () => {
    let resolveChat: (value: Response) => void
    const chatPromise = new Promise<Response>((resolve) => { resolveChat = resolve })
    setupFetchMock([{
      match: (u) => u.endsWith('/chat'),
      handler: () => chatPromise,
    }])
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} />)
    const input = screen.getByPlaceholderText(/ask me/i)
    await user.type(input, 'Hi')
    await user.click(screen.getByRole('button', { name: /send/i }))
    // While the promise is pending, loading indicator shows
    await waitFor(() => {
      expect(screen.getByText(/thinking/i)).toBeInTheDocument()
    })
    // Resolve to clean up
    resolveChat!(new Response(JSON.stringify({ response: 'ok', tasks: [], title: null }), {
      headers: { 'Content-Type': 'application/json' },
    }))
  })

  it('history button fires GET /conversations?limit=3', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} />)
    const histBtn = screen.getByTitle(/chat history/i)
    await user.click(histBtn)
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u]: [string]) => u.includes('/conversations') && u.includes('limit=3'))).toBe(true)
    })
    // Shows history items
    await waitFor(() => {
      expect(screen.getByText(CONVERSATIONS_RECENT[0].title)).toBeInTheDocument()
    })
  })

  it('switching to All Chats fires GET /conversations (no limit)', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} />)
    await user.click(screen.getByTitle(/chat history/i))
    await waitFor(() => screen.getByText(CONVERSATIONS_RECENT[0].title))
    await user.click(screen.getByText(/all chats/i))
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u]: [string]) => u.includes('/conversations') && !u.includes('limit'))).toBe(true)
    })
  })

  it('clicking a history item fires GET /conversations/:id and loads messages', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} />)
    await user.click(screen.getByTitle(/chat history/i))
    await waitFor(() => screen.getByText(CONVERSATIONS_RECENT[0].title))
    await user.click(screen.getByText(CONVERSATIONS_RECENT[0].title))
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u]: [string]) => u.includes(`/conversations/${CONVERSATION_1.id}`))).toBe(true)
    })
    await waitFor(() => {
      expect(screen.getByText('Hi there!')).toBeInTheDocument()
    })
  })

  it('New Chat button fires POST /conversation/new and clears messages', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} />)
    // First send a message so there's content
    const input = screen.getByPlaceholderText(/ask me/i)
    await user.type(input, 'Hi')
    await user.click(screen.getByRole('button', { name: /send/i }))
    await waitFor(() => screen.getByText('Sure, I can help with that.'))
    // Click New Chat
    await user.click(screen.getByText(/new chat/i))
    await waitFor(() => {
      expect(screen.queryByText('Sure, I can help with that.')).not.toBeInTheDocument()
    })
  })

  it('collapsed prop applies the collapsed class', () => {
    const { container } = render(<ChatInterface {...defaultProps} collapsed={true} />)
    expect(container.querySelector('.chat-panel.collapsed')).toBeInTheDocument()
  })

  it('collapse toggle button calls onToggleCollapse', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} />)
    await user.click(screen.getByTitle(/collapse chat/i))
    expect(defaultProps.onToggleCollapse).toHaveBeenCalledTimes(1)
  })

  it('Enter key submits the message', async () => {
    const user = userEvent.setup()
    render(<ChatInterface {...defaultProps} />)
    const input = screen.getByPlaceholderText(/ask me/i)
    await user.type(input, 'Hello{Enter}')
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u, i]: [string, RequestInit]) =>
        u.includes('/chat') && i?.method === 'POST'
      )).toBe(true)
    })
  })
})
