import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'
import { setupFetchMock } from '../test/mocks/server'

describe('App shell', () => {
  beforeEach(() => {
    setupFetchMock()
  })

  it('renders the header with logo text', async () => {
    render(<App />)
    expect(screen.getByText('Hakadorio')).toBeInTheDocument()
  })

  it('renders the settings button', async () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /settings/i })).toBeInTheDocument()
  })

  it('opens SettingsModal when settings button is clicked', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: /settings/i }))
    // SettingsModal has a conflict resolution section
    await waitFor(() => {
      expect(screen.getByText(/allow overlap/i)).toBeInTheDocument()
    })
  })

  it('opens QuickEntry on Ctrl+. keydown', async () => {
    render(<App />)
    await userEvent.keyboard('{Control>}.{/Control}')
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/create a task/i)).toBeInTheDocument()
    })
  })

  it('closes QuickEntry on Escape', async () => {
    render(<App />)
    await userEvent.keyboard('{Control>}.{/Control}')
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/create a task/i)).toBeInTheDocument()
    })
    await userEvent.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByPlaceholderText(/create a task/i)).not.toBeInTheDocument()
    })
  })

  it('renders app with structural classes present', async () => {
    const { container } = render(<App />)
    expect(container.querySelector('.app')).toBeInTheDocument()
    expect(container.querySelector('.header')).toBeInTheDocument()
    expect(container.querySelector('.main')).toBeInTheDocument()
  })
})
