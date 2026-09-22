/**
 * Money, the Swiss way (SPECIFICATIONS §9): "1'234.50 CHF". Amounts travel
 * as decimal strings ("1234.50") between the API and the app; they are never
 * turned into floats for arithmetic, only for display and comparison.
 */

/** "1'234.50" (no unit). Accepts the API's strings and plain numbers. */
export function formatAmount(value: string | number | null | undefined): string {
  const number = Number(value ?? 0)
  if (!Number.isFinite(number)) return '0.00'
  const sign = number < 0 ? '-' : ''
  const [whole, cents] = Math.abs(number).toFixed(2).split('.')
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, "'")
  return `${sign}${grouped}.${cents}`
}

/** "1'234.50 CHF" */
export function chf(value: string | number | null | undefined): string {
  return `${formatAmount(value)} CHF`
}

/** "−120.50 CHF" for an expense, "+900.00 CHF" for an income. */
export function signedChf(amount: string | number, kind: 'expense' | 'income'): string {
  return `${kind === 'expense' ? '−' : '+'}${chf(amount)}`
}

/** Sum of decimal strings, as a decimal string (cents arithmetic: exact). */
export function sumAmounts(values: (string | number)[]): string {
  const cents = values.reduce<number>((total, value) => total + Math.round(Number(value) * 100), 0)
  return (cents / 100).toFixed(2)
}

/** User input ("12,5", "1'200.-", " 30 ") -> "12.50" | "1200.00" | "30.00", or null. */
export function parseAmount(input: string): string | null {
  const cleaned = input.replace(/\s|'/g, '').replace(/\.-$/, '').replace(',', '.')
  if (!/^\d+(\.\d{0,2})?$/.test(cleaned)) return null
  const number = Number(cleaned)
  if (!(number > 0)) return null
  return number.toFixed(2)
}

/** 0-100, capped: how much of `planned` is `actual`. */
export function percentOf(actual: string | number, planned: string | number): number {
  const total = Number(planned)
  if (!(total > 0)) return 0
  return Math.min(100, Math.round((Number(actual) / total) * 100))
}
