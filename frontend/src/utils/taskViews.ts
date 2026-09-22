/**
 * Pure helpers behind the task views (kanban, calendar, Gantt): everything
 * that converts a Task to what a view needs, and a drag back to task dates.
 * Kept out of the components so that it can be unit-tested.
 *
 * Date convention (utils/tasks.ts): an all-day date sits at midnight UTC and
 * only its date part counts; a timed date is an instant shown in local time.
 */
import type { Task, TaskStatus } from '@/api/tasks'

import { CLOSED_STATUSES, dateKey, localDateKey, TASK_STATUS_ORDER } from './tasks'

// --- Dates ---------------------------------------------------------------------

/** YYYY-MM-DD shifted by `days` (calendar arithmetic, no timezone involved). */
export function shiftDateKey(key: string, days: number): string {
  const [year, month, day] = key.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10)
}

/** Whole days from `from` to `to` (both YYYY-MM-DD). */
export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000)
}

function allDayIso(key: string): string {
  return `${key}T00:00:00Z`
}

/** A timed instant moved by whole days, keeping its local time of day (DST-safe). */
function shiftInstant(iso: string, days: number): string {
  const moment = new Date(iso)
  moment.setDate(moment.getDate() + days)
  return moment.toISOString()
}

export interface TaskDates {
  all_day: boolean
  start_at: string | null
  due_at: string | null
}

// --- Kanban ----------------------------------------------------------------------

export type KanbanColumns = Record<TaskStatus, Task[]>

/** One column per status, each in its saved order. */
export function kanbanColumns(tasks: Task[]): KanbanColumns {
  const columns = Object.fromEntries(
    TASK_STATUS_ORDER.map((status) => [status, [] as Task[]]),
  ) as KanbanColumns
  for (const task of tasks) columns[task.status].push(task)
  for (const column of Object.values(columns)) {
    column.sort((a, b) => a.position - b.position || a.id - b.id)
  }
  return columns
}

/**
 * Position to send to the server for the card now at `index` of `column`.
 * The server orders each column PER PROJECT, while a board that includes the
 * sub-projects mixes several projects: only the cards of the same project
 * that sit above the dropped one count.
 */
export function dropPosition(column: Task[], index: number): number {
  const moved = column[index]
  return column.slice(0, index).filter((task) => task.project === moved.project).length
}

// --- Calendar (FullCalendar) ----------------------------------------------------------

export interface CalendarEvent {
  id: string
  title: string
  start: string
  end?: string
  allDay: boolean
  backgroundColor: string
  borderColor: string
  textColor: string
  editable: boolean
  classNames: string[]
  extendedProps: { task: Task }
}

/** Tasks with at least one date, as FullCalendar events. `canMove` decides
 * which ones may be dragged (editors only: an assignee cannot change dates). */
export function calendarEvents(tasks: Task[], canMove: (task: Task) => boolean): CalendarEvent[] {
  const events: CalendarEvent[] = []
  for (const task of tasks) {
    const first = task.start_at ?? task.due_at
    const last = task.due_at ?? task.start_at
    if (!first || !last) continue
    const closed = CLOSED_STATUSES.includes(task.status)
    events.push({
      id: String(task.id),
      title: task.title,
      // All-day: FullCalendar wants an EXCLUSIVE end date.
      start: task.all_day ? dateKey(first, true) : first,
      end: task.all_day
        ? shiftDateKey(dateKey(last, true), 1)
        : task.start_at && task.due_at
          ? task.due_at
          : undefined,
      allDay: task.all_day,
      backgroundColor: task.project_color,
      borderColor: task.is_overdue ? 'var(--c-danger)' : task.project_color,
      textColor: '#1c1917', // project colours are pastels: dark text in both themes
      editable: canMove(task),
      classNames: [
        'task-event',
        ...(task.is_overdue ? ['task-event-overdue'] : []),
        ...(closed ? ['task-event-closed'] : []),
      ],
      extendedProps: { task },
    })
  }
  return events
}

/**
 * New dates of a task after its calendar event was dropped or resized.
 * `start` / `end` are what FullCalendar reports (local Dates, end EXCLUSIVE
 * for all-day events, null when the event has no duration).
 * A task that only had a due date keeps only a due date, unless it was
 * stretched over several days.
 */
export function datesAfterCalendarChange(
  task: Pick<Task, 'start_at' | 'due_at'>,
  change: { allDay: boolean; start: Date; end: Date | null },
): TaskDates {
  const onlyDue = !task.start_at && !!task.due_at
  const onlyStart = !!task.start_at && !task.due_at
  if (change.allDay) {
    const first = localDateKey(change.start)
    const last = change.end ? shiftDateKey(localDateKey(change.end), -1) : first
    const single = last <= first
    return {
      all_day: true,
      start_at: onlyDue && single ? null : allDayIso(first),
      due_at: onlyStart && single ? null : allDayIso(single ? first : last),
    }
  }
  const startIso = change.start.toISOString()
  const endIso = change.end ? change.end.toISOString() : null
  if (onlyDue && !endIso) return { all_day: false, start_at: null, due_at: startIso }
  if (onlyStart && !endIso) return { all_day: false, start_at: startIso, due_at: null }
  return { all_day: false, start_at: startIso, due_at: endIso ?? startIso }
}

// --- Gantt (frappe-gantt) -----------------------------------------------------------

/** frappe-gantt writes task names with innerHTML: they MUST be escaped. */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export interface GanttRow {
  id: string
  name: string
  /** YYYY-MM-DD, both inclusive. */
  start: string
  end: string
  progress: number
  /** Comma-separated ids of the blockers that are on the chart too. */
  dependencies: string
  color: string
  /** ONE class name (frappe-gantt passes it to classList.add). */
  custom_class: string
}

/** Dated tasks as Gantt rows (day precision), undated ones listed apart. */
export function ganttRows(tasks: Task[]): { rows: GanttRow[]; undated: Task[] } {
  const dated = tasks.filter((task) => task.start_at || task.due_at)
  const onChart = new Set(dated.map((task) => task.id))
  const rows = dated.map((task) => {
    const first = (task.start_at ?? task.due_at)!
    const last = (task.due_at ?? task.start_at)!
    const done = task.checklist.filter((item) => item.done).length
    return {
      id: String(task.id),
      name: escapeHtml(task.title),
      start: dateKey(first, task.all_day),
      end: dateKey(last, task.all_day),
      progress:
        task.status === 'done'
          ? 100
          : task.checklist.length
            ? Math.round((done / task.checklist.length) * 100)
            : 0,
      dependencies: task.blockers
        .filter((blocker) => onChart.has(blocker.id))
        .map((blocker) => String(blocker.id))
        .join(','),
      color: task.project_color,
      custom_class: task.is_overdue
        ? 'gantt-overdue'
        : CLOSED_STATUSES.includes(task.status)
          ? 'gantt-closed'
          : 'gantt-open',
    }
  })
  rows.sort((a, b) =>
    a.start === b.start ? a.end.localeCompare(b.end) : a.start < b.start ? -1 : 1,
  )
  return { rows, undated: tasks.filter((task) => !task.start_at && !task.due_at) }
}

/**
 * New dates after a bar was moved or resized on the Gantt (day precision).
 * A timed task keeps its times of day: only its days move.
 */
export function datesAfterGanttChange(
  task: Pick<Task, 'start_at' | 'due_at' | 'all_day'>,
  startKey: string,
  endKey: string,
): TaskDates {
  const onlyDue = !task.start_at && !!task.due_at
  const onlyStart = !!task.start_at && !task.due_at
  const single = endKey <= startKey
  if (task.all_day) {
    return {
      all_day: true,
      start_at: onlyDue && single ? null : allDayIso(startKey),
      due_at: onlyStart && single ? null : allDayIso(single ? startKey : endKey),
    }
  }
  const oldStart = dateKey((task.start_at ?? task.due_at)!, false)
  const oldEnd = dateKey((task.due_at ?? task.start_at)!, false)
  const startShift = daysBetween(oldStart, startKey)
  const endShift = daysBetween(oldEnd, endKey)
  if (onlyDue && single) {
    return { all_day: false, start_at: null, due_at: shiftInstant(task.due_at!, endShift) }
  }
  if (onlyStart && single) {
    return { all_day: false, start_at: shiftInstant(task.start_at!, startShift), due_at: null }
  }
  return {
    all_day: false,
    start_at: shiftInstant((task.start_at ?? task.due_at)!, startShift),
    due_at: shiftInstant((task.due_at ?? task.start_at)!, endShift),
  }
}
