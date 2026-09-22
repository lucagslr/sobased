/** Labels and helpers for events and meetings (SPEC §8). */
import type { Event, EventType } from '@/api/events'
import type { Task } from '@/api/tasks'

import type { CalendarEvent } from './taskViews'
import { shiftDateKey } from './taskViews'
import { dateKey, localDateKey } from './tasks'

export const EVENT_TYPE_LABELS: Record<EventType, string> = {
  meeting: 'RDV',
  live: 'Date live',
  shooting: 'Tournage',
  release: 'Release',
  release_party: 'Release party',
  class: 'Cours',
  exam: 'Examen',
  other: 'Autre',
}
export const EVENT_TYPE_ORDER = Object.keys(EVENT_TYPE_LABELS) as EventType[]

/** True once the event is over (its end has passed, on the user's clock). */
export function isPast(event: Pick<Event, 'end' | 'all_day'>, now = new Date()): boolean {
  if (event.all_day) return dateKey(event.end, true) < localDateKey(now)
  return new Date(event.end) < now
}

/** Groups an agenda: past events aside, the rest by month (YYYY-MM). */
export function groupAgenda(events: Event[], now = new Date()): { key: string; items: Event[] }[] {
  const groups = new Map<string, Event[]>()
  for (const event of events) {
    const key = isPast(event, now) ? 'past' : dateKey(event.start, event.all_day).slice(0, 7)
    const list = groups.get(key) ?? []
    list.push(event)
    groups.set(key, list)
  }
  const keys = [...groups.keys()].filter((key) => key !== 'past').sort()
  const result = keys.map((key) => ({ key, items: groups.get(key)! }))
  const past = groups.get('past')
  if (past) result.push({ key: 'past', items: [...past].reverse() }) // most recent first
  return result
}

/** "octobre 2026", for an agenda group key. */
export function monthLabel(key: string): string {
  const [year, month] = key.split('-').map(Number)
  const label = new Intl.DateTimeFormat('fr-CH', { month: 'long', year: 'numeric' }).format(
    new Date(year, month - 1, 1),
  )
  return label.charAt(0).toUpperCase() + label.slice(1)
}

/**
 * Events as FullCalendar events, next to the tasks (utils/taskViews.ts).
 * They share the calendar with tasks: their id is prefixed so that the two
 * never collide, and `extendedProps.event` tells them apart.
 */
export interface CalendarEventEntry extends Omit<CalendarEvent, 'extendedProps'> {
  extendedProps: { event: Event; task?: Task }
}

export function eventCalendarEntries(
  events: Event[],
  canMove: (event: Event) => boolean,
): CalendarEventEntry[] {
  return events.map((event) => ({
    id: `event-${event.id}`,
    title: event.title,
    start: event.all_day ? dateKey(event.start, true) : event.start,
    // All-day: FullCalendar wants an EXCLUSIVE end; ours is inclusive.
    end: event.all_day ? shiftDateKey(dateKey(event.end, true), 1) : event.end,
    allDay: event.all_day,
    backgroundColor: event.project_color,
    borderColor: event.project_color,
    textColor: '#1c1917',
    editable: canMove(event),
    classNames: ['task-event', 'calendar-meeting', ...(isPast(event) ? ['task-event-closed'] : [])],
    extendedProps: { event },
  }))
}

export interface EventDates {
  all_day: boolean
  start: string
  end: string
}

/** New dates of an event after its calendar entry was dropped or resized.
 * `end` from FullCalendar is exclusive for all-day entries, null when the
 * entry has no duration. */
export function datesAfterCalendarChange(change: {
  allDay: boolean
  start: Date
  end: Date | null
}): EventDates {
  if (change.allDay) {
    const first = localDateKey(change.start)
    const last = change.end ? shiftDateKey(localDateKey(change.end), -1) : first
    return {
      all_day: true,
      start: `${first}T00:00:00Z`,
      end: `${last < first ? first : last}T00:00:00Z`,
    }
  }
  const start = change.start.toISOString()
  return {
    all_day: false,
    start,
    end: change.end ? change.end.toISOString() : start,
  }
}
