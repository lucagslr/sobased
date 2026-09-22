import { describe, expect, it } from 'vitest'

import {
  buildRrule,
  collapseSeries,
  compareTasks,
  dateKey,
  describeRrule,
  fromIso,
  groupTasks,
  parseRrule,
  taskGroup,
  toIso,
} from './tasks'

// Wednesday 23.09.2026, noon local time.
const NOW = new Date(2026, 8, 23, 12, 0)

function allDay(date: string, overdue = false) {
  return { due_at: `${date}T00:00:00Z`, start_at: null, all_day: true, is_overdue: overdue }
}

describe('all-day dates', () => {
  it('round-trips without drifting to the previous or next day', () => {
    expect(toIso('2026-10-12', '', true)).toBe('2026-10-12T00:00:00Z')
    expect(fromIso('2026-10-12T00:00:00Z', true)).toEqual({ date: '2026-10-12', time: '' })
    expect(dateKey('2026-10-12T00:00:00Z', true)).toBe('2026-10-12')
  })

  it('reads the UTC date whatever zone the API wrote midnight UTC in', () => {
    expect(dateKey('2026-10-12T02:00:00+02:00', true)).toBe('2026-10-12')
    expect(dateKey('2026-10-11T19:00:00-05:00', true)).toBe('2026-10-12')
    expect(fromIso('2026-10-11T19:00:00-05:00', true)).toEqual({ date: '2026-10-12', time: '' })
  })

  it('keeps timed dates as real instants', () => {
    const iso = toIso('2026-10-12', '14:30', false)!
    expect(fromIso(iso, false)).toEqual({ date: '2026-10-12', time: '14:30' })
  })

  it('treats an empty date as no date', () => {
    expect(toIso('', '10:00', false)).toBeNull()
    expect(fromIso(null, true)).toEqual({ date: '', time: '' })
  })
})

describe('taskGroup (Mes tâches)', () => {
  it('puts overdue first, whatever the date says', () => {
    expect(taskGroup(allDay('2026-09-20', true), NOW)).toBe('overdue')
  })

  it('sorts by calendar distance', () => {
    expect(taskGroup(allDay('2026-09-23'), NOW)).toBe('today')
    expect(taskGroup(allDay('2026-09-24'), NOW)).toBe('tomorrow')
    expect(taskGroup(allDay('2026-09-27'), NOW)).toBe('week') // Sunday ends the week
    expect(taskGroup(allDay('2026-09-28'), NOW)).toBe('later') // next Monday
  })

  it('uses the start date when there is no due date', () => {
    const task = {
      due_at: null,
      start_at: '2026-09-24T00:00:00Z',
      all_day: true,
      is_overdue: false,
    }
    expect(taskGroup(task, NOW)).toBe('tomorrow')
  })

  it('has a group for undated tasks', () => {
    const task = { due_at: null, start_at: null, all_day: true, is_overdue: false }
    expect(taskGroup(task, NOW)).toBe('undated')
  })

  it('on a Sunday, "this week" is empty and tomorrow is tomorrow', () => {
    const sunday = new Date(2026, 8, 27, 12, 0)
    expect(taskGroup(allDay('2026-09-28'), sunday)).toBe('tomorrow')
    expect(taskGroup(allDay('2026-09-29'), sunday)).toBe('later')
  })

  it('groups a list', () => {
    const groups = groupTasks(
      [allDay('2026-09-23'), allDay('2026-12-01'), allDay('2026-09-23')],
      NOW,
    )
    expect(groups.today).toHaveLength(2)
    expect(groups.later).toHaveLength(1)
    expect(groups.overdue).toEqual([])
  })
})

describe('compareTasks', () => {
  it('orders by due date, undated last, then by priority', () => {
    const tasks = [
      { title: 'c', due_at: null, priority: 5 },
      { title: 'b', due_at: '2026-10-02T00:00:00Z', priority: 1 },
      { title: 'a', due_at: '2026-10-01T00:00:00Z', priority: 1 },
      { title: 'z', due_at: '2026-10-01T00:00:00Z', priority: 5 },
    ]
    expect(tasks.sort(compareTasks).map((t) => t.title)).toEqual(['z', 'a', 'b', 'c'])
  })
})

describe('collapseSeries', () => {
  const occurrence = (id: number, date: string, series: number | null, status = 'todo') => ({
    id,
    due_at: `${date}T00:00:00Z`,
    start_at: null,
    all_day: true,
    status: status as 'todo' | 'done',
    recurrence: series ? { series, rrule: 'FREQ=WEEKLY', is_exception: false } : null,
  })

  it('keeps late and current occurrences, and only the next future one per series', () => {
    const tasks = [
      occurrence(1, '2026-09-16', 7), // late
      occurrence(2, '2026-09-23', 7), // today
      occurrence(3, '2026-10-07', 7), // later
      occurrence(4, '2026-09-30', 7), // the next one
      occurrence(5, '2026-10-01', 8), // another series
      occurrence(6, '2026-12-01', null), // a plain task is never hidden
      occurrence(7, '2026-11-01', 7, 'done'), // closed ones are left alone
    ]

    const ids = collapseSeries(tasks, NOW)
      .map((task) => task.id)
      .sort()

    expect(ids).toEqual([1, 2, 4, 5, 6, 7])
  })
})

describe('recurrence rules', () => {
  it('builds and parses the same rule', () => {
    const choice = { frequency: 'WEEKLY' as const, interval: 2, until: '2026-12-31' }
    const rule = buildRrule(choice)

    expect(rule).toBe('FREQ=WEEKLY;INTERVAL=2;UNTIL=20261231T235959')
    expect(parseRrule(rule)).toEqual(choice)
  })

  it('has no rule when not recurring', () => {
    expect(buildRrule({ frequency: '', interval: 3, until: '' })).toBe('')
    expect(parseRrule(null).frequency).toBe('')
  })

  it('describes rules in French', () => {
    expect(describeRrule('FREQ=DAILY')).toBe('Tous les jours')
    expect(describeRrule('FREQ=WEEKLY;INTERVAL=2')).toBe('Toutes les 2 semaines')
    expect(describeRrule('FREQ=MONTHLY;UNTIL=20261231T235959')).toBe(
      "Tous les mois jusqu'au 31.12.2026",
    )
    expect(describeRrule('')).toBe('')
  })

  it('reads rules written by other tools', () => {
    expect(parseRrule('RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=5').frequency).toBe('WEEKLY')
  })
})
