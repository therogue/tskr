/**
 * #92 Task-cards-in-chat — flag-ON unit tests
 *
 * Verify that when ux_v2=true, an assistant message that has an attached task
 * renders a TaskCard bubble with View / Edit buttons that open TaskModal.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ChatInterface from '../components/ChatInterface'

/* ── feature-flag helpers ─────────────────────────────────────────────── */
function setFlag(key: string, value: boolean) {
  localStorage.setItem(`ff:${key}`, value ? 'true' : 'false')
}
function clearFlags() {
  ;['ux_v2', 'ux_v2.chat_overlay', 'ux_v2.task_modal'].forEach(k =>
    localStorage.removeItem(`ff:${k}`)
  )
}

/* ── mock task ─────────────────────────────────────────────────────────── */
const mockTask = {
  id: 'task-abc',
  task_key: 'TSK-001',
  category: 'work',
  title: 'Write tests for #92',
  completed: false,
  scheduled_date: '2026-05-05',
  duration_minutes: 30,
  priority: 2,
}

/* ── fetch mock that returns a task in the chat response ──────────────── */
function setupFetchMock() {
  const conversationsPayload = [{ id: 1, title: 'Test Convo' }]
  const chatResponsePayload = {
    response: 'Done! I created a task for you.',
    tasks: [{ ...mockTask }],
    conversation_id: 1,
  }
  const conversationMessages = { messages: [] }

  global.fetch = vi.fn(async (url: string, opts?: RequestInit) => {
    const u = String(url)
    if (u.includes('/conversations') && (!opts || opts.method !== 'POST'))
      return { ok: true, json: async () => conversationsPayload }
    if (u.includes('/conversation/new'))
      return { ok: true, json: async () => ({ conversation_id: 2, history: [] }) }
    if (u.includes('/conversation/') && u.includes('/messages'))
      return { ok: true, json: async () => conversationMessages }
    if (u.includes('/chat'))
      return { ok: true, json: async () => chatResponsePayload }
    return { ok: true, json: async () => [] }
  }) as typeof global.fetch
}

describe('#92 Task cards in chat (v2)', () => {
  beforeEach(() => {
    clearFlags()
    setFlag('ux_v2', true)
    setFlag('ux_v2.chat_overlay', true)
    setFlag('ux_v2.task_modal', true)
    setupFetchMock()
  })
  afterEach(() => {
    clearFlags()
    vi.restoreAllMocks()
  })

  it('renders a TaskCard bubble after AI creates a task', async () => {
    const onUpdate = vi.fn()
    render(
      <ChatInterface
        onTasksUpdate={onUpdate}
        tasks={[]}        // no tasks before the message
        visible={true}
        onClose={() => {}}
      />
    )

    // Type and send a message
    const textarea = await screen.findByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'Create a task for writing tests' } })
    fireEvent.submit(textarea.closest('form')!)

    // Wait for the assistant response and task card to appear
    await waitFor(() => {
      expect(screen.getByText(/Done! I created a task for you\./i)).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText('TSK-001')).toBeInTheDocument()
    })
    expect(screen.getByText('Write tests for #92')).toBeInTheDocument()
  })

  it('opens TaskModal when View button clicked on a task card', async () => {
    const onUpdate = vi.fn()
    render(
      <ChatInterface
        onTasksUpdate={onUpdate}
        tasks={[]}
        visible={true}
        onClose={() => {}}
      />
    )

    const textarea = await screen.findByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'Create a task' } })
    fireEvent.submit(textarea.closest('form')!)

    await waitFor(() => expect(screen.getByText('TSK-001')).toBeInTheDocument())

    const viewBtn = screen.getByRole('button', { name: /view/i })
    fireEvent.click(viewBtn)

    // TaskModal renders the task title in an input
    await waitFor(() => {
      const input = screen.getByDisplayValue('Write tests for #92')
      expect(input).toBeInTheDocument()
    })
  })

  it('opens TaskModal when Edit button clicked on a task card', async () => {
    const onUpdate = vi.fn()
    render(
      <ChatInterface
        onTasksUpdate={onUpdate}
        tasks={[]}
        visible={true}
        onClose={() => {}}
      />
    )

    const textarea = await screen.findByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'Create a task' } })
    fireEvent.submit(textarea.closest('form')!)

    await waitFor(() => expect(screen.getByText('TSK-001')).toBeInTheDocument())

    const editBtn = screen.getByRole('button', { name: /^edit$/i })
    fireEvent.click(editBtn)

    await waitFor(() => {
      expect(screen.getByDisplayValue('Write tests for #92')).toBeInTheDocument()
    })
  })

  it('does NOT attach a task card when no new task is created', async () => {
    // Override fetch to return same tasks list (no new tasks)
    global.fetch = vi.fn(async (url: string, opts?: RequestInit) => {
      const u = String(url)
      if (u.includes('/conversations') && (!opts || opts.method !== 'POST'))
        return { ok: true, json: async () => [{ id: 1, title: 'Convo' }] }
      if (u.includes('/conversation/') && u.includes('/messages'))
        return { ok: true, json: async () => ({ messages: [] }) }
      if (u.includes('/chat'))
        return {
          ok: true,
          json: async () => ({
            response: 'No task was created.',
            tasks: [{ ...mockTask }],  // same tasks as before
            conversation_id: 1,
          }),
        }
      return { ok: true, json: async () => [] }
    }) as typeof global.fetch

    render(
      <ChatInterface
        onTasksUpdate={vi.fn()}
        tasks={[mockTask]}   // same task already exists
        visible={true}
        onClose={() => {}}
      />
    )

    const textarea = await screen.findByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'Show me tasks' } })
    fireEvent.submit(textarea.closest('form')!)

    await waitFor(() => expect(screen.getByText(/No task was created\./i)).toBeInTheDocument())

    // TSK-001 should not be displayed as a card (no new/changed task)
    expect(screen.queryByText('TSK-001')).not.toBeInTheDocument()
  })
})
