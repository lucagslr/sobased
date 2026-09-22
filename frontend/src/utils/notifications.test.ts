import { describe, expect, it } from 'vitest'

import { detail, relativeTime, sentence } from './notifications'

const actor = {
  id: 1,
  username: 'sam',
  display_name: 'Sam',
  avatar_url: null,
} as const

describe('sentence', () => {
  it('phrases every kind', () => {
    expect(sentence({ kind: 'assignment', payload: { title: 'Brief' }, actor })).toBe(
      'Sam t’a assigné « Brief »',
    )
    expect(sentence({ kind: 'mention', payload: { title: 'Mix' }, actor })).toBe(
      'Sam t’a mentionné dans « Mix »',
    )
    expect(
      sentence({ kind: 'asset_status', payload: { title: 'Cover', to_status: 'approved' }, actor }),
    ).toBe('Sam a passé « Cover » en validé')
    expect(
      sentence({ kind: 'invitation', payload: { scope_name: 'SHORTY7G', role: 'Éditeur' }, actor }),
    ).toBe('Sam t’a ajouté à « SHORTY7G » (Éditeur)')
    expect(
      sentence({
        kind: 'share_opened',
        payload: { title: 'Écoute privée', recipient_label: 'Radio X' },
        actor: null,
      }),
    ).toBe('Le lien « Écoute privée » a été ouvert (Radio X)')
  })

  it('falls back on the stored actor name when the user is gone', () => {
    expect(
      sentence({ kind: 'assignment', payload: { title: 'Brief', actor_name: 'Ana' }, actor: null }),
    ).toBe('Ana t’a assigné « Brief »')
  })
})

describe('detail', () => {
  it('gives the second line', () => {
    expect(detail({ kind: 'mention', payload: { excerpt: '@luca ?' } })).toBe('@luca ?')
    expect(detail({ kind: 'asset_status', payload: { note: 'Prête' } })).toBe('Prête')
    expect(detail({ kind: 'assignment', payload: { project_name: 'MARCHIOLY' } })).toBe('MARCHIOLY')
    expect(detail({ kind: 'share_opened', payload: {} })).toBe('')
  })
})

describe('relativeTime', () => {
  const now = new Date('2026-09-23T12:00:00Z')
  it('speaks French', () => {
    expect(relativeTime('2026-09-23T11:59:40Z', now)).toBe('à l’instant')
    expect(relativeTime('2026-09-23T11:55:00Z', now)).toBe('il y a 5 min')
    expect(relativeTime('2026-09-23T09:00:00Z', now)).toBe('il y a 3 h')
    expect(relativeTime('2026-09-22T09:00:00Z', now)).toBe('hier')
    expect(relativeTime('2026-09-20T09:00:00Z', now)).toBe('il y a 3 j')
    expect(relativeTime('2026-09-01T09:00:00Z', now)).toBe('01.09.2026')
  })
})
