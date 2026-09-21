import { describe, expect, it } from 'vitest'

import { atLeast } from './roles'

describe('atLeast', () => {
  it('compares roles by rank', () => {
    expect(atLeast('admin', 'editor')).toBe(true)
    expect(atLeast('editor', 'editor')).toBe(true)
    expect(atLeast('commenter', 'editor')).toBe(false)
    expect(atLeast('owner', 'admin')).toBe(true)
  })

  it('treats a missing role (shell, signed out) as no right at all', () => {
    expect(atLeast(null, 'viewer')).toBe(false)
    expect(atLeast(undefined, 'viewer')).toBe(false)
  })
})
