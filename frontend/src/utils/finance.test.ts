import { describe, expect, it } from 'vitest'

import { describeSchedule, periodBounds } from './finance'

describe('describeSchedule', () => {
  it('reads like a sentence', () => {
    expect(describeSchedule('monthly', 1, 1)).toBe('le 1er de chaque mois')
    expect(describeSchedule('monthly', 15, 1)).toBe('le 15 de chaque mois')
    expect(describeSchedule('monthly', 31, 1)).toBe('le 31 (ou dernier jour) de chaque mois')
    expect(describeSchedule('yearly', 1, 3)).toBe('chaque 1er mars')
  })
})

describe('periodBounds', () => {
  const now = new Date(2026, 8, 23) // 23 September 2026

  it('gives the month, the quarter and the year', () => {
    expect(periodBounds('month', now)).toEqual({ after: '2026-09-01', before: '2026-09-30' })
    expect(periodBounds('quarter', now)).toEqual({ after: '2026-07-01', before: '2026-09-30' })
    expect(periodBounds('year', now)).toEqual({ after: '2026-01-01', before: '2026-12-31' })
    expect(periodBounds('all', now)).toEqual({ after: '', before: '' })
  })

  it('handles February and the last quarter', () => {
    expect(periodBounds('month', new Date(2028, 1, 10)).before).toBe('2028-02-29')
    expect(periodBounds('quarter', new Date(2026, 11, 1))).toEqual({
      after: '2026-10-01',
      before: '2026-12-31',
    })
  })
})
