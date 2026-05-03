import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { getFlag, setFlag, ALL_FLAGS, type FlagId } from '../featureFlags'

describe('Feature flag system', () => {
  beforeEach(() => {
    // Clear all flags from localStorage before each test
    ALL_FLAGS.forEach(id => localStorage.removeItem('ff:' + id))
    // Remove any URL search params (jsdom allows this)
    window.history.replaceState(null, '', '/')
  })

  afterEach(() => {
    ALL_FLAGS.forEach(id => localStorage.removeItem('ff:' + id))
  })

  it('returns default value when no localStorage or URL param', () => {
    expect(getFlag('ux_v2')).toBe(false)
    expect(getFlag('ux_v2.chat_overlay')).toBe(true)
    expect(getFlag('ux_v2.task_modal')).toBe(true)
    expect(getFlag('ux_v2.theme_toggle')).toBe(false)
  })

  it('reads localStorage over default', () => {
    localStorage.setItem('ff:ux_v2', 'true')
    expect(getFlag('ux_v2')).toBe(true)
    localStorage.setItem('ff:ux_v2', 'false')
    expect(getFlag('ux_v2')).toBe(false)
  })

  it('setFlag persists to localStorage and dispatches flag-change event', () => {
    const events: Array<{ id: FlagId; value: boolean }> = []
    const handler = (e: Event) => events.push((e as CustomEvent).detail)
    window.addEventListener('flag-change', handler)

    setFlag('ux_v2', true)
    expect(localStorage.getItem('ff:ux_v2')).toBe('true')
    expect(events).toHaveLength(1)
    expect(events[0]).toEqual({ id: 'ux_v2', value: true })

    window.removeEventListener('flag-change', handler)
  })

  it('URL param ?ux_v2=1 takes precedence over localStorage', () => {
    localStorage.setItem('ff:ux_v2', 'false')
    window.history.replaceState(null, '', '/?ux_v2=1')
    expect(getFlag('ux_v2')).toBe(true)
  })

  it('URL param ?ux_v2=0 takes precedence over localStorage true', () => {
    localStorage.setItem('ff:ux_v2', 'true')
    window.history.replaceState(null, '', '/?ux_v2=0')
    expect(getFlag('ux_v2')).toBe(false)
  })

  it('ALL_FLAGS lists all four flags', () => {
    expect(ALL_FLAGS).toContain('ux_v2')
    expect(ALL_FLAGS).toContain('ux_v2.chat_overlay')
    expect(ALL_FLAGS).toContain('ux_v2.task_modal')
    expect(ALL_FLAGS).toContain('ux_v2.theme_toggle')
  })
})
