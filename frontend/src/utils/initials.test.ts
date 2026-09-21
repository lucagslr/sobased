import { describe, expect, it } from 'vitest'

import { initials } from './initials'

describe('initials', () => {
  it('uses first and last word', () => {
    expect(initials('Luca Gslr')).toBe('LG')
    expect(initials('  Noam   de la  Antonio ')).toBe('NA')
  })

  it('uses two letters of a single word', () => {
    expect(initials('shorty7g')).toBe('SH')
  })

  it('never returns an empty string', () => {
    expect(initials('')).toBe('?')
  })
})
