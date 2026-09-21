/**
 * Task helpers: labels, priority colours, date conversion, "Mes tâches"
 * grouping and recurrence rules.
 *
 * Date convention (same as the backend): an all-day date is stored at
 * midnight UTC and only its date part matters; a timed date is a real instant,
 * shown in the browser's timezone.
 */
import type { Task, TaskStatus } from '@/api/tasks'

import { formatDate } from './projects'

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  todo: 'À faire',
  in_progress: 'En cours',
  to_validate: 'À valider',
  done: 'Terminé',
  cancelled: 'Annulé',
}
export const TASK_STATUS_ORDER = Object.keys(TASK_STATUS_LABELS) as TaskStatus[]
export const CLOSED_STATUSES: TaskStatus[] = ['done', 'cancelled']

/** 5 = highest. One pastel colour per level (SPEC §7), defined only here. */
export const PRIORITIES: Record<number, { label: string; color: string }> = {
  1: { label: 'Très basse', color: '#E7E5E4' },
  2: { label: 'Basse', color: '#BAE6FD' },
  3: { label: 'Normale', color: '#BBF7D0' },
  4: { label: 'Haute', color: '#FED7AA' },
  5: { label: 'Très haute', color: '#FECACA' },
}

// --- Dates -------------------------------------------------------------------

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

/** Local calendar date of a Date object, as YYYY-MM-DD. */
export function localDateKey(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** YYYY-MM-DD of a task date: the UTC date if all-day, the local date otherwise. */
export function dateKey(iso: string, allDay: boolean): string {
  return allDay ? iso.slice(0, 10) : localDateKey(new Date(iso))
}

/** Form values -> ISO string for the API ("" means no date). */
export function toIso(date: string, time: string, allDay: boolean): string | null {
  if (!date) return null
  if (allDay) return `${date}T00:00:00Z`
  return new Date(`${date}T${time || '09:00'}`).toISOString()
}

/** ISO string from the API -> form values. */
export function fromIso(iso: string | null, allDay: boolean): { date: string; time: string } {
  if (!iso) return { date: '', time: '' }
  if (allDay) return { date: iso.slice(0, 10), time: '' }
  const local = new Date(iso)
  return { date: localDateKey(local), time: `${pad(local.getHours())}:${pad(local.getMinutes())}` }
}

/** "12.10.2026" or "12.10.2026 14:30". */
export function formatTaskDate(iso: string | null, allDay: boolean): string {
  if (!iso) return ''
  const { date, time } = fromIso(iso, allDay)
  return allDay ? formatDate(date) : `${formatDate(date)} ${time}`
}

// --- "Mes tâches" groups (SPEC §15) ---------------------------------------------

export type TaskGroupKey = 'overdue' | 'today' | 'tomorrow' | 'week' | 'later' | 'undated'

export const TASK_GROUP_LABELS: Record<TaskGroupKey, string> = {
  overdue: 'En retard',
  today: "Aujourd'hui",
  tomorrow: 'Demain',
  week: 'Cette semaine',
  later: 'Plus tard',
  undated: 'Sans date',
}
export const TASK_GROUP_ORDER = Object.keys(TASK_GROUP_LABELS) as TaskGroupKey[]

function addDays(date: Date, days: number): Date {
  const copy = new Date(date)
  copy.setDate(copy.getDate() + days)
  return copy
}

/** The Sunday that ends the week of `date` (weeks start on Monday). */
function endOfWeek(date: Date): Date {
  const daysUntilSunday = (7 - date.getDay()) % 7
  return addDays(date, daysUntilSunday)
}

/** Which group a task falls in. `is_overdue` comes from the server (it knows
 * the user's timezone and the all-day rule); the rest is calendar arithmetic. */
export function taskGroup(
  task: Pick<Task, 'due_at' | 'start_at' | 'all_day' | 'is_overdue'>,
  now = new Date(),
): TaskGroupKey {
  if (task.is_overdue) return 'overdue'
  const iso = task.due_at ?? task.start_at
  if (!iso) return 'undated'
  const key = dateKey(iso, task.all_day)
  const today = localDateKey(now)
  if (key <= today) return 'today' // a start date already reached counts as today
  if (key === localDateKey(addDays(now, 1))) return 'tomorrow'
  if (key <= localDateKey(endOfWeek(now))) return 'week'
  return 'later'
}

export function groupTasks<T extends Parameters<typeof taskGroup>[0]>(
  tasks: T[],
  now = new Date(),
): Record<TaskGroupKey, T[]> {
  const groups = Object.fromEntries(TASK_GROUP_ORDER.map((key) => [key, [] as T[]])) as Record<
    TaskGroupKey,
    T[]
  >
  for (const task of tasks) groups[taskGroup(task, now)].push(task)
  return groups
}

/** Open tasks first by due date (undated last), then by priority (high first). */
export function compareTasks(
  a: Pick<Task, 'due_at' | 'priority' | 'title'>,
  b: Pick<Task, 'due_at' | 'priority' | 'title'>,
): number {
  if (a.due_at !== b.due_at) {
    if (!a.due_at) return 1
    if (!b.due_at) return -1
    return a.due_at < b.due_at ? -1 : 1
  }
  return b.priority - a.priority || a.title.localeCompare(b.title, 'fr')
}

/**
 * Lists only: a weekly task exists 13 times ahead (90-day window). Showing them
 * all buries everything else, so each series keeps its occurrences that are
 * due (today or late) plus the NEXT one. Calendars show every occurrence.
 */
export function collapseSeries<
  T extends Pick<Task, 'recurrence' | 'due_at' | 'start_at' | 'all_day' | 'status'>,
>(tasks: T[], now = new Date()): T[] {
  const today = localDateKey(now)
  const nextBySeries = new Map<number, T>()
  const kept: T[] = []
  for (const task of tasks) {
    const iso = task.due_at ?? task.start_at
    const future = !!iso && dateKey(iso, task.all_day) > today
    if (!task.recurrence || !future || CLOSED_STATUSES.includes(task.status)) {
      kept.push(task)
      continue
    }
    const current = nextBySeries.get(task.recurrence.series)
    const currentIso = current ? (current.due_at ?? current.start_at)! : null
    if (!currentIso || iso! < currentIso) nextBySeries.set(task.recurrence.series, task)
  }
  return [...kept, ...nextBySeries.values()]
}

// --- Recurrence (RRULE) ----------------------------------------------------------

export type RecurrenceFrequency = 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'YEARLY'

export interface RecurrenceChoice {
  frequency: RecurrenceFrequency | ''
  interval: number
  /** YYYY-MM-DD, or "" for no end. */
  until: string
}

export const NO_RECURRENCE: RecurrenceChoice = { frequency: '', interval: 1, until: '' }

export function buildRrule(choice: RecurrenceChoice): string {
  if (!choice.frequency) return ''
  const parts = [`FREQ=${choice.frequency}`]
  if (choice.interval > 1) parts.push(`INTERVAL=${Math.floor(choice.interval)}`)
  if (choice.until) parts.push(`UNTIL=${choice.until.replace(/-/g, '')}T235959`)
  return parts.join(';')
}

export function parseRrule(rule: string | null | undefined): RecurrenceChoice {
  if (!rule) return { ...NO_RECURRENCE }
  const fields = Object.fromEntries(
    rule
      .replace(/^RRULE:/i, '')
      .split(';')
      .map((part) => part.split('=') as [string, string]),
  )
  const until = /^(\d{4})(\d{2})(\d{2})/.exec(fields.UNTIL ?? '')
  return {
    frequency: (fields.FREQ as RecurrenceFrequency) ?? '',
    interval: Number(fields.INTERVAL ?? 1) || 1,
    until: until ? `${until[1]}-${until[2]}-${until[3]}` : '',
  }
}

const UNIT: Record<RecurrenceFrequency, [string, string, string]> = {
  // [every one, plural unit, "chaque" form]
  DAILY: ['Tous les jours', 'jours', 'Tous les'],
  WEEKLY: ['Toutes les semaines', 'semaines', 'Toutes les'],
  MONTHLY: ['Tous les mois', 'mois', 'Tous les'],
  YEARLY: ['Tous les ans', 'ans', 'Tous les'],
}

/** "Toutes les 2 semaines jusqu'au 31.12.2026". "" when not recurring. */
export function describeRrule(rule: string | null | undefined): string {
  const choice = parseRrule(rule)
  if (!choice.frequency || !UNIT[choice.frequency]) return ''
  const [single, unit, every] = UNIT[choice.frequency]
  const base = choice.interval > 1 ? `${every} ${choice.interval} ${unit}` : single
  return choice.until ? `${base} jusqu'au ${formatDate(choice.until)}` : base
}
