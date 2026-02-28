import { describe, it, expect } from 'vitest'
import { computeColumnLayout, DEFAULT_DURATION } from './calendarLayout'

// Minimal task stub. Assumption: scheduled_date is YYYY-MM-DDTHH:MM.
function task(time: string, duration: number | null = 30) {
  return { scheduled_date: `2026-02-22T${time}`, duration_minutes: duration }
}

describe('computeColumnLayout', () => {
  it('empty array returns empty', () => {
    expect(computeColumnLayout([])).toEqual([])
  })

  it('single task: colIndex=0, colCount=1', () => {
    expect(computeColumnLayout([task('09:00', 60)])).toEqual([
      { colIndex: 0, colCount: 1 },
    ])
  })

  it('two non-overlapping tasks: each gets colCount=1', () => {
    // A: 09:00-10:00, B: 10:00-11:00 — adjacent, not overlapping (start < end is strict)
    expect(computeColumnLayout([task('09:00', 60), task('10:00', 60)])).toEqual([
      { colIndex: 0, colCount: 1 },
      { colIndex: 0, colCount: 1 },
    ])
  })

  it('two overlapping tasks: split into 2 columns', () => {
    // A: 09:00-10:00, B: 09:30-10:30 — overlap
    expect(computeColumnLayout([task('09:00', 60), task('09:30', 60)])).toEqual([
      { colIndex: 0, colCount: 2 },
      { colIndex: 1, colCount: 2 },
    ])
  })

  it('same start time: split into 2 columns', () => {
    // A: 08:00-12:00, B: 08:00-09:00 — full overlap
    expect(computeColumnLayout([task('08:00', 240), task('08:00', 60)])).toEqual([
      { colIndex: 0, colCount: 2 },
      { colIndex: 1, colCount: 2 },
    ])
  })

  it('three mutually overlapping tasks: three columns', () => {
    // A: 09:00-10:30, B: 09:30-11:00, C: 10:00-11:00 — all overlap each other
    expect(computeColumnLayout([task('09:00', 90), task('09:30', 90), task('10:00', 60)])).toEqual([
      { colIndex: 0, colCount: 3 },
      { colIndex: 1, colCount: 3 },
      { colIndex: 2, colCount: 3 },
    ])
  })

  it('chain overlap: A-B overlap, B-C overlap, A-C do not — max 2 columns', () => {
    // A: 09:00-10:00, B: 09:30-10:30, C: 10:00-11:00
    // A and C are exactly adjacent (not overlapping), so C reuses A's column
    expect(computeColumnLayout([task('09:00', 60), task('09:30', 60), task('10:00', 60)])).toEqual([
      { colIndex: 0, colCount: 2 },
      { colIndex: 1, colCount: 2 },
      { colIndex: 0, colCount: 2 },
    ])
  })

  it('null duration falls back to DEFAULT_DURATION', () => {
    // A: 09:00-(DEFAULT_DURATION)min, B starts within that window → overlap
    const halfDefault = Math.floor(DEFAULT_DURATION / 2)
    const result = computeColumnLayout([task('09:00', null), task(`09:${String(halfDefault).padStart(2, '0')}`, 30)])
    expect(result[0].colCount).toBe(2)
    expect(result[1].colCount).toBe(2)
    expect(result[0].colIndex).not.toBe(result[1].colIndex)
  })
})
