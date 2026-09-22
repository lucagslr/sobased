import { describe, expect, it } from 'vitest'

import { chf, formatAmount, parseAmount, percentOf, signedChf, sumAmounts } from './money'

describe('formatting', () => {
  it('groups thousands with an apostrophe and always shows cents', () => {
    expect(formatAmount('1234.5')).toBe("1'234.50")
    expect(formatAmount(0)).toBe('0.00')
    expect(formatAmount('1234567.891')).toBe("1'234'567.89")
    expect(formatAmount(-42)).toBe('-42.00')
    expect(chf('19.9')).toBe('19.90 CHF')
    expect(signedChf('120.5', 'expense')).toBe('−120.50 CHF')
    expect(signedChf('900', 'income')).toBe('+900.00 CHF')
  })

  it('never shows NaN', () => {
    expect(formatAmount('abc')).toBe('0.00')
    expect(formatAmount(null)).toBe('0.00')
  })
})

describe('parseAmount', () => {
  it('accepts what people type in Switzerland', () => {
    expect(parseAmount('12,5')).toBe('12.50')
    expect(parseAmount("1'200.-")).toBe('1200.00')
    expect(parseAmount(' 30 ')).toBe('30.00')
    expect(parseAmount('0.05')).toBe('0.05')
  })

  it('refuses zero, negatives, and more than two decimals', () => {
    expect(parseAmount('0')).toBeNull()
    expect(parseAmount('-5')).toBeNull()
    expect(parseAmount('1.005')).toBeNull()
    expect(parseAmount('dix')).toBeNull()
    expect(parseAmount('')).toBeNull()
  })
})

describe('arithmetic', () => {
  it('sums in cents, without float drift', () => {
    expect(sumAmounts(['0.10', '0.20'])).toBe('0.30')
    expect(sumAmounts(['19.90', 19.9, '0.2'])).toBe('40.00')
    expect(sumAmounts([])).toBe('0.00')
  })

  it('caps the percentage at 100 and handles an empty budget', () => {
    expect(percentOf('50', '200')).toBe(25)
    expect(percentOf('300', '200')).toBe(100)
    expect(percentOf('10', '0')).toBe(0)
  })
})
