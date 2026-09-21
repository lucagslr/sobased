import { describe, expect, it } from 'vitest'

import { isThemeChoice, resolveTheme } from './theme'

describe('resolveTheme', () => {
  it('follows the OS preference for "system"', () => {
    expect(resolveTheme('system', true)).toBe('dark')
    expect(resolveTheme('system', false)).toBe('light')
  })

  it('ignores the OS preference for explicit choices', () => {
    expect(resolveTheme('light', true)).toBe('light')
    expect(resolveTheme('dark', false)).toBe('dark')
  })
})

describe('isThemeChoice', () => {
  it('accepts only the three known values', () => {
    expect(isThemeChoice('dark')).toBe(true)
    expect(isThemeChoice('neon')).toBe(false)
    expect(isThemeChoice(null)).toBe(false)
  })
})
