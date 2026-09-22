/** Labels and small helpers of the bookkeeping screens (SPEC §13). */
import type { DisplayStatus, Frequency, PaymentStatus, TransactionKind } from '@/api/finance'

export const KIND_LABELS: Record<TransactionKind, string> = {
  expense: 'Dépense',
  income: 'Recette',
}

export const PAYMENT_STATUS_LABELS: Record<PaymentStatus, string> = {
  to_pay: 'À payer',
  paid: 'Payé',
}

/** SPECIFICATIONS §9: to pay (orange) > to justify (red) > to reimburse > ok. */
export const DISPLAY_STATUS: Record<DisplayStatus, { label: string; tone: string }> = {
  to_pay: { label: 'À payer', tone: 'bg-warning-soft text-warning' },
  needs_receipt: { label: 'À justifier', tone: 'bg-danger-soft text-danger' },
  to_reimburse: { label: 'À rembourser', tone: 'bg-surface-2 text-fg' },
  ok: { label: 'OK', tone: 'bg-surface-2 text-muted' },
}

export const FREQUENCY_LABELS: Record<Frequency, string> = {
  monthly: 'Chaque mois',
  yearly: 'Chaque année',
}

export const MONTH_NAMES = [
  'janvier',
  'février',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'août',
  'septembre',
  'octobre',
  'novembre',
  'décembre',
]

/** "le 5 de chaque mois", "le 31 (ou dernier jour) de chaque mois", "chaque 1er mars". */
export function describeSchedule(frequency: Frequency, day: number, month: number): string {
  const dayLabel = day === 1 ? '1er' : String(day)
  if (frequency === 'yearly') return `chaque ${dayLabel} ${MONTH_NAMES[month - 1]}`
  return day > 28 ? `le ${day} (ou dernier jour) de chaque mois` : `le ${dayLabel} de chaque mois`
}

/** First and last day of a period preset, as YYYY-MM-DD. */
export type PeriodPreset = 'month' | 'quarter' | 'year' | 'all'

export function periodBounds(
  preset: PeriodPreset,
  now = new Date(),
): { after: string; before: string } {
  const pad = (n: number) => String(n).padStart(2, '0')
  const key = (y: number, m: number, d: number) => `${y}-${pad(m)}-${pad(d)}`
  const year = now.getFullYear()
  const month = now.getMonth() + 1
  const lastDay = (y: number, m: number) => new Date(y, m, 0).getDate()
  if (preset === 'month')
    return { after: key(year, month, 1), before: key(year, month, lastDay(year, month)) }
  if (preset === 'quarter') {
    const first = month - ((month - 1) % 3)
    return { after: key(year, first, 1), before: key(year, first + 2, lastDay(year, first + 2)) }
  }
  if (preset === 'year') return { after: key(year, 1, 1), before: key(year, 12, 31) }
  return { after: '', before: '' }
}
