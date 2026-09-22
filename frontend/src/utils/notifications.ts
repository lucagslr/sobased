/** Labels of the bell: one sentence per notification kind. Pure, tested. */
import type { Notification, NotificationKind } from '@/api/notifications'

export const KIND_LABELS: Record<NotificationKind, string> = {
  assignment: 'Tâche assignée',
  mention: 'Mention',
  asset_status: 'Statut de fichier',
  invitation: 'Ajout à un projet',
  share_opened: 'Lien partagé ouvert',
}

const STATUS_LABELS: Record<string, string> = {
  draft: 'brouillon',
  to_validate: 'à valider',
  approved: 'validé',
  rejected: 'refusé',
}

function payloadOf(notification: Pick<Notification, 'payload'>): Record<string, string> {
  return (notification.payload ?? {}) as Record<string, string>
}

/** "Sam t'a assigné « Brief »", "Le lien « Écoute privée » a été ouvert (Radio X)"… */
export function sentence(notification: Pick<Notification, 'kind' | 'payload' | 'actor'>): string {
  const payload = payloadOf(notification)
  const actor = notification.actor?.display_name ?? payload.actor_name ?? 'Quelqu’un'
  switch (notification.kind) {
    case 'assignment':
      return `${actor} t’a assigné « ${payload.title ?? ''} »`
    case 'mention':
      return `${actor} t’a mentionné dans « ${payload.title ?? ''} »`
    case 'asset_status':
      return `${actor} a passé « ${payload.title ?? ''} » en ${STATUS_LABELS[payload.to_status ?? ''] ?? payload.to_status ?? ''}`
    case 'invitation':
      return `${actor} t’a ajouté à « ${payload.scope_name ?? ''} » (${payload.role ?? ''})`
    case 'share_opened':
      return `Le lien « ${payload.title ?? ''} » a été ouvert${payload.recipient_label ? ` (${payload.recipient_label})` : ''}`
    default:
      return KIND_LABELS[notification.kind] ?? ''
  }
}

/** The secondary line: the excerpt of a mention, the note of a status change. */
export function detail(notification: Pick<Notification, 'kind' | 'payload'>): string {
  const payload = payloadOf(notification)
  if (notification.kind === 'mention') return payload.excerpt ?? ''
  if (notification.kind === 'asset_status') return payload.note ?? ''
  if (notification.kind === 'assignment') return payload.project_name ?? ''
  return ''
}

/** "à l’instant", "il y a 5 min", "il y a 3 h", "hier", "22.09.2026". */
export function relativeTime(iso: string, now = new Date()): string {
  const diff = now.getTime() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'à l’instant'
  if (minutes < 60) return `il y a ${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `il y a ${hours} h`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'hier'
  if (days < 7) return `il y a ${days} j`
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()}`
}
