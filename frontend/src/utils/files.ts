/**
 * Files helpers (SPEC §9): labels, sizes, durations, anchors of the comments
 * and the threads they form. Pure functions, tested in files.test.ts.
 */
import type { AssetComment, AssetKind, AssetStatus } from '@/api/files'

export const KIND_LABELS: Record<AssetKind, string> = {
  audio: 'Audio',
  image: 'Image',
  video: 'Vidéo',
  document: 'PDF / document',
  other: 'Autre',
}
export const KIND_ORDER = Object.keys(KIND_LABELS) as AssetKind[]

export const STATUS_META: Record<AssetStatus, { label: string; tone: string }> = {
  draft: { label: 'Brouillon', tone: 'bg-surface-2 text-muted' },
  to_validate: { label: 'À valider', tone: 'bg-warning-soft text-warning' },
  approved: { label: 'Validé', tone: 'bg-success-soft text-success' },
  rejected: { label: 'Refusé', tone: 'bg-danger-soft text-danger' },
}
export const STATUS_ORDER = Object.keys(STATUS_META) as AssetStatus[]

/** "12 Ko", "3,4 Mo", "1,2 Go" (French units, one decimal above kilobytes). */
export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`
  const units = ['Ko', 'Mo', 'Go', 'To']
  let value = bytes / 1024
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  const text = index === 0 ? String(Math.round(value)) : value.toFixed(1).replace('.', ',')
  return `${text.replace(/,0$/, '')} ${units[index]}`
}

/** "1:05", "12:03", "1:02:03" from milliseconds (floor). */
export function formatTimestamp(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return hours ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${minutes}:${pad(seconds)}`
}

/** "v3 · master" or just "v3". */
export function versionLabel(number: number, label: string): string {
  return label ? `v${number} · ${label}` : `v${number}`
}

/** What the kind of the asset lets a comment be anchored on. */
export type AnchorKind = 'time' | 'rect' | 'page' | 'none'

export function anchorKind(kind: AssetKind): AnchorKind {
  if (kind === 'audio' || kind === 'video') return 'time'
  if (kind === 'image') return 'rect'
  if (kind === 'document') return 'page'
  return 'none'
}

export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

/** The rectangle of a comment, in percent, or null when it has none. */
export function commentRect(
  comment: Pick<AssetComment, 'rect_x' | 'rect_y' | 'rect_w' | 'rect_h'>,
): Rect | null {
  if (comment.rect_x == null || comment.rect_y == null) return null
  if (comment.rect_w == null || comment.rect_h == null) return null
  return {
    x: Number(comment.rect_x),
    y: Number(comment.rect_y),
    w: Number(comment.rect_w),
    h: Number(comment.rect_h),
  }
}

/**
 * A rectangle drawn from two points of a box of `width` × `height` pixels,
 * as percentages clamped to the image, with 3 decimals (the API precision).
 */
export function rectFromDrag(
  start: { x: number; y: number },
  end: { x: number; y: number },
  width: number,
  height: number,
): Rect | null {
  if (width <= 0 || height <= 0) return null
  const clamp = (value: number) => Math.min(100, Math.max(0, value))
  const round = (value: number) => Math.round(value * 1000) / 1000
  const x1 = clamp((Math.min(start.x, end.x) / width) * 100)
  const y1 = clamp((Math.min(start.y, end.y) / height) * 100)
  const x2 = clamp((Math.max(start.x, end.x) / width) * 100)
  const y2 = clamp((Math.max(start.y, end.y) / height) * 100)
  const rect = { x: round(x1), y: round(y1), w: round(x2 - x1), h: round(y2 - y1) }
  // A click without a drag is not an area.
  return rect.w < 0.5 || rect.h < 0.5 ? null : rect
}

export function rectPayload(rect: Rect): {
  rect_x: string
  rect_y: string
  rect_w: string
  rect_h: string
} {
  const text = (value: number) => value.toFixed(3)
  return { rect_x: text(rect.x), rect_y: text(rect.y), rect_w: text(rect.w), rect_h: text(rect.h) }
}

export interface Thread {
  root: AssetComment
  replies: AssetComment[]
}

/** Root comments with their replies, in creation order; replies flattened. */
export function buildThreads(comments: AssetComment[]): Thread[] {
  const threads = new Map<number, Thread>()
  for (const comment of comments) {
    if (comment.parent === null) threads.set(comment.id, { root: comment, replies: [] })
  }
  for (const comment of comments) {
    if (comment.parent === null) continue
    const thread = threads.get(comment.parent)
    if (thread) thread.replies.push(comment)
  }
  return [...threads.values()]
}

/** Threads sorted by their anchor (time, page, top-left), unanchored last. */
export function sortThreads(threads: Thread[], kind: AnchorKind): Thread[] {
  const key = (thread: Thread): number => {
    const { root } = thread
    if (kind === 'time') return root.timestamp_ms ?? Number.POSITIVE_INFINITY
    if (kind === 'page') return root.page ?? Number.POSITIVE_INFINITY
    if (kind === 'rect') {
      const rect = commentRect(root)
      return rect ? rect.y * 1000 + rect.x : Number.POSITIVE_INFINITY
    }
    return Number.POSITIVE_INFINITY
  }
  return [...threads].sort((a, b) => {
    const diff = key(a) - key(b)
    return diff !== 0 && Number.isFinite(diff) ? diff : a.root.id - b.root.id
  })
}

/** Accepted upload types, as the file picker's `accept` attribute. */
export const ACCEPT =
  'audio/*,video/*,image/*,application/pdf,.mp3,.wav,.flac,.m4a,.aac,.ogg,.mp4,.mov,.webm,.avi,.png,.jpg,.jpeg,.webp,.gif,.tif,.tiff,.pdf,.zip,.txt,.doc,.docx,.xls,.xlsx,.ppt,.pptx'

/** Text after a status change, for the toast. */
export function statusChangedMessage(status: AssetStatus): string {
  return {
    draft: 'Fichier remis en brouillon.',
    to_validate: 'Fichier envoyé en validation.',
    approved: 'Fichier validé.',
    rejected: 'Fichier refusé.',
  }[status]
}
