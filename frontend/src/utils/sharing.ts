/** Share-link helpers: labels, states, "expires in", quotas. Pure, tested. */
import type { ShareEvent, ShareLink, ShareState, ShareTarget } from '@/api/sharing'

export const STATE_META: Record<ShareState, { label: string; tone: string }> = {
  active: { label: 'Actif', tone: 'bg-success-soft text-success' },
  expired: { label: 'Expiré', tone: 'bg-surface-2 text-muted' },
  exhausted: { label: 'Épuisé', tone: 'bg-warning-soft text-warning' },
  revoked: { label: 'Révoqué', tone: 'bg-danger-soft text-danger' },
}
export const STATE_ORDER = Object.keys(STATE_META) as ShareState[]

export const TARGET_LABELS: Record<ShareTarget, string> = {
  version: 'Une version précise',
  asset: 'Le fichier (dernière version)',
  playlist: 'Une sélection de fichiers',
}

export const EVENT_LABELS: Record<ShareEvent, string> = {
  view: 'Ouverture',
  play: 'Écoute',
  download: 'Téléchargement',
  password_failed: 'Mot de passe refusé',
}

/** "3 / 10 vues", "12 vues", "—" when nothing happened and no quota. */
export function quotaText(count: number, max: number | null, unit: string): string {
  const plural = (n: number) => (n > 1 ? `${unit}s` : unit)
  if (max !== null) return `${count} / ${max} ${plural(max)}`
  return count ? `${count} ${plural(count)}` : `0 ${unit}`
}

/** "expire dans 3 j", "expire demain", "expire dans 2 h", "expiré", or "". */
export function expiryText(expiresAt: string | null, now = new Date()): string {
  if (!expiresAt) return ''
  const diff = new Date(expiresAt).getTime() - now.getTime()
  if (diff <= 0) return 'expiré'
  const hours = Math.floor(diff / 3_600_000)
  if (hours < 1) return 'expire dans moins d’une heure'
  if (hours < 24) return `expire dans ${hours} h`
  const days = Math.floor(hours / 24)
  return days === 1 ? 'expire demain' : `expire dans ${days} j`
}

/** Local datetime-input value (YYYY-MM-DDTHH:MM) for a stored ISO instant. */
export function toLocalInput(iso: string | null): string {
  if (!iso) return ''
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** The reverse: a datetime-local value to an ISO instant (null when empty). */
export function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null
}

/** What the table shows as the "who" column. */
export function recipientText(link: Pick<ShareLink, 'recipient_label' | 'title'>): string {
  return link.recipient_label || '—'
}

/** Sort: active first, then by creation date (newest first). */
export function sortLinks(links: ShareLink[]): ShareLink[] {
  const rank = (state: ShareState) => (state === 'active' ? 0 : 1)
  return [...links].sort(
    (a, b) => rank(a.state) - rank(b.state) || b.created_at.localeCompare(a.created_at),
  )
}
