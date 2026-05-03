import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SettingsModal from '../components/SettingsModal'
import { setupFetchMock } from '../test/mocks/server'

const defaultProps = {
  onClose: vi.fn(),
  taskCategories: ['T', 'M'],
}

describe('SettingsModal', () => {
  beforeEach(() => {
    setupFetchMock()
    defaultProps.onClose.mockReset()
  })

  it('renders conflict-resolution options', async () => {
    render(<SettingsModal {...defaultProps} />)
    await waitFor(() => {
      expect(screen.getByText(/allow overlap/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/move to backlog/i)).toBeInTheDocument()
  })

  it('save fires PATCH /settings and closes modal', async () => {
    const user = userEvent.setup()
    render(<SettingsModal {...defaultProps} />)
    // Wait for settings to load
    await waitFor(() => screen.getByText(/allow overlap/i))
    const saveBtn = screen.getByRole('button', { name: /save/i })
    await user.click(saveBtn)
    await waitFor(() => {
      const calls = (globalThis as unknown as { fetch: ReturnType<typeof vi.fn> }).fetch.mock.calls
      expect(calls.some(([u, i]: [string, RequestInit]) =>
        u.includes('/settings') && i?.method === 'PATCH'
      )).toBe(true)
    })
    expect(defaultProps.onClose).toHaveBeenCalled()
  })
})
