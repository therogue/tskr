// Tests for #87: Fixed-width tabbed views (flag ON)
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from '../App'
import { setupFetchMock } from '../test/mocks/server'
import { setFlag } from '../featureFlags'

describe('#87 — Fixed-width layout (ux_v2=true)', () => {
  beforeEach(() => {
    setupFetchMock()
    setFlag('ux_v2', true)
  })

  afterEach(() => {
    setFlag('ux_v2', false)
    localStorage.removeItem('ff:ux_v2')
  })

  it('renders .main--v2 class when ux_v2=true', () => {
    const { container } = render(<App />)
    expect(container.querySelector('.main--v2')).toBeInTheDocument()
  })

  it('renders .right-panel inside .main--v2', () => {
    const { container } = render(<App />)
    const main = container.querySelector('.main--v2')
    expect(main?.querySelector('.right-panel')).toBeInTheDocument()
  })

  it('does NOT render .main--v2 when ux_v2=false', () => {
    setFlag('ux_v2', false)
    const { container } = render(<App />)
    expect(container.querySelector('.main--v2')).not.toBeInTheDocument()
    expect(container.querySelector('.main:not(.main--v2)')).toBeInTheDocument()
  })

  it('renders tab-bar--v2 class on task list tabs when ux_v2=true', () => {
    const { container } = render(<App />)
    expect(container.querySelector('.tab-bar--v2')).toBeInTheDocument()
  })

  it('still renders all four tabs in v2 mode', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /day view/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /all tasks/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /completed/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /backlog/i })).toBeInTheDocument()
  })
})
