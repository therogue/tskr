import '@testing-library/jest-dom'
import { vi, afterEach } from 'vitest'

// Stub matchMedia (not available in jsdom)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Stub scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn()

// Restore stubs after each test
afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
