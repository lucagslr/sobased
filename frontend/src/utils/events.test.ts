import { describe, expect, it } from 'vitest'

import type { Event } from '@/api/events'

import {
  datesAfterCalendarChange,
  eventCalendarEntries,
  externalCalendarEntries,
  groupAgenda,
  isPast,
  monthLabel,
} from './events'

// Wednesday 23.09.2026, noon local time.
const NOW = new Date(2026, 8, 23, 12, 0)

let nextId = 1
function event(fields: Partial<Event> = {}): Event {
  const id = fields.id ?? nextId++
  return {
    id,
    project: 1,
    project_name: 'Clip',
    project_color: '#DDD6FE',
    type: 'meeting',
    title: `RDV ${id}`,
    start: '2026-10-12T00:00:00Z',
    end: '2026-10-12T00:00:00Z',
    all_day: true,
    location: '',
    prep_notes: '',
    report: '',
    decisions: [],
    participants: [],
    contacts: [],
    contact_details: [],
    tags: [],
    tasks: [],
    recurrence: null,
    ...fields,
  } as Event
}

describe('isPast', () => {
  it('compares all-day events by date, timed ones by instant', () => {
    expect(isPast(event({ end: '2026-09-22T00:00:00Z' }), NOW)).toBe(true)
    expect(isPast(event({ end: '2026-09-23T00:00:00Z' }), NOW)).toBe(false) // today: still on
    expect(
      isPast(event({ all_day: false, end: new Date(2026, 8, 23, 11).toISOString() }), NOW),
    ).toBe(true)
    expect(
      isPast(event({ all_day: false, end: new Date(2026, 8, 23, 13).toISOString() }), NOW),
    ).toBe(false)
  })
})

describe('groupAgenda', () => {
  it('groups upcoming events by month and puts past ones last, most recent first', () => {
    const groups = groupAgenda(
      [
        event({ id: 1, start: '2026-09-01T00:00:00Z', end: '2026-09-01T00:00:00Z' }),
        event({ id: 2, start: '2026-09-20T00:00:00Z', end: '2026-09-20T00:00:00Z' }),
        event({ id: 3, start: '2026-10-05T00:00:00Z', end: '2026-10-05T00:00:00Z' }),
        event({ id: 4, start: '2026-09-25T00:00:00Z', end: '2026-09-25T00:00:00Z' }),
        event({ id: 5, start: '2026-11-01T00:00:00Z', end: '2026-11-01T00:00:00Z' }),
      ],
      NOW,
    )

    expect(groups.map((g) => [g.key, g.items.map((e) => e.id)])).toEqual([
      ['2026-09', [4]],
      ['2026-10', [3]],
      ['2026-11', [5]],
      ['past', [2, 1]],
    ])
    expect(monthLabel('2026-10')).toBe('Octobre 2026')
  })
})

describe('calendar entries', () => {
  it('prefixes ids, makes all-day ends exclusive and flags past events', () => {
    const [entry] = eventCalendarEntries(
      [event({ id: 7, start: '2026-09-01T00:00:00Z', end: '2026-09-02T00:00:00Z' })],
      () => false,
    )

    expect(entry.id).toBe('event-7')
    expect(entry).toMatchObject({ start: '2026-09-01', end: '2026-09-03', allDay: true })
    expect(entry.editable).toBe(false)
    expect(entry.classNames).toContain('calendar-meeting')
    expect(entry.extendedProps.event.id).toBe(7)
  })
})

describe('dates after a calendar drag', () => {
  it('turns an exclusive all-day end back into an inclusive one', () => {
    expect(
      datesAfterCalendarChange({
        allDay: true,
        start: new Date(2026, 9, 12),
        end: new Date(2026, 9, 14),
      }),
    ).toEqual({ all_day: true, start: '2026-10-12T00:00:00Z', end: '2026-10-13T00:00:00Z' })
  })

  it('keeps a single day when there is no end', () => {
    expect(
      datesAfterCalendarChange({ allDay: true, start: new Date(2026, 9, 12), end: null }),
    ).toEqual({ all_day: true, start: '2026-10-12T00:00:00Z', end: '2026-10-12T00:00:00Z' })
  })

  it('keeps timed instants', () => {
    const start = new Date(2026, 9, 12, 14)
    const end = new Date(2026, 9, 12, 15, 30)
    expect(datesAfterCalendarChange({ allDay: false, start, end })).toEqual({
      all_day: false,
      start: start.toISOString(),
      end: end.toISOString(),
    })
  })
})

describe('externalCalendarEntries', () => {
  it('builds read-only entries in the calendar colour', () => {
    const [timed, allDay] = externalCalendarEntries([
      {
        id: 1,
        calendar: 3,
        calendar_name: 'Horaire HEG',
        calendar_color: '#c7d2fe',
        provider: 'google',
        title: 'Cours BPMN',
        start: '2026-10-06T08:15:00Z',
        end: '2026-10-06T10:00:00Z',
        all_day: false,
        location: '',
      },
      {
        id: 2,
        calendar: 3,
        calendar_name: 'Horaire HEG',
        calendar_color: '',
        provider: 'google',
        title: '',
        start: '2026-10-20T00:00:00Z',
        end: '2026-10-20T00:00:00Z',
        all_day: true,
        location: '',
      },
    ])
    expect(timed.id).toBe('external-1')
    expect(timed.editable).toBe(false)
    expect(timed.borderColor).toBe('#c7d2fe')
    expect(timed.classNames).toContain('calendar-external')
    expect(allDay.title).toBe('(sans titre)')
    expect(allDay.start).toBe('2026-10-20')
    expect(allDay.end).toBe('2026-10-21') // exclusive end for FullCalendar
    expect(allDay.borderColor).toBe('#a8a29e')
  })
})
