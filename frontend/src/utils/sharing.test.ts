import { describe, expect, it } from 'vitest'

import type { ShareLink } from '@/api/sharing'

import { expiryText, fromLocalInput, quotaText, sortLinks, toLocalInput } from './sharing'

describe('quotaText', () => {
  it('shows the quota when there is one', () => {
    expect(quotaText(3, 10, 'vue')).toBe('3 / 10 vues')
    expect(quotaText(0, 1, 'écoute')).toBe('0 / 1 écoute')
  })
  it('shows the count alone otherwise', () => {
    expect(quotaText(12, null, 'vue')).toBe('12 vues')
    expect(quotaText(1, null, 'écoute')).toBe('1 écoute')
    expect(quotaText(0, null, 'vue')).toBe('0 vue')
  })
})

describe('expiryText', () => {
  const now = new Date('2026-09-22T10:00:00Z')
  it('describes the delay', () => {
    expect(expiryText(null, now)).toBe('')
    expect(expiryText('2026-09-22T09:00:00Z', now)).toBe('expiré')
    expect(expiryText('2026-09-22T10:30:00Z', now)).toBe('expire dans moins d’une heure')
    expect(expiryText('2026-09-22T15:00:00Z', now)).toBe('expire dans 5 h')
    expect(expiryText('2026-09-23T12:00:00Z', now)).toBe('expire demain')
    expect(expiryText('2026-09-30T12:00:00Z', now)).toBe('expire dans 8 j')
  })
})

describe('datetime-local conversion', () => {
  it('round-trips an instant', () => {
    const iso = new Date(2026, 8, 22, 14, 30).toISOString()
    expect(toLocalInput(iso)).toBe('2026-09-22T14:30')
    expect(fromLocalInput('2026-09-22T14:30')).toBe(iso)
    expect(fromLocalInput('')).toBeNull()
    expect(toLocalInput(null)).toBe('')
  })
})

describe('sortLinks', () => {
  const link = (id: number, state: ShareLink['state'], created_at: string) =>
    ({ id, state, created_at }) as ShareLink
  it('puts active links first, newest first', () => {
    const sorted = sortLinks([
      link(1, 'revoked', '2026-09-20'),
      link(2, 'active', '2026-09-18'),
      link(3, 'active', '2026-09-21'),
      link(4, 'expired', '2026-09-22'),
    ])
    expect(sorted.map((l) => l.id)).toEqual([3, 2, 4, 1])
  })
})
