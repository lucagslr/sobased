import { describe, expect, it } from 'vitest'

import type { Task } from '@/api/tasks'

import {
  calendarEvents,
  datesAfterCalendarChange,
  datesAfterGanttChange,
  daysBetween,
  dropPosition,
  escapeHtml,
  ganttRows,
  kanbanColumns,
  shiftDateKey,
} from './taskViews'
import { fromIso } from './tasks'

let nextId = 1
function task(fields: Partial<Task> = {}): Task {
  const id = fields.id ?? nextId++
  return {
    id,
    project: 1,
    project_name: 'Clip',
    project_color: '#BFDBFE',
    title: `Tâche ${id}`,
    description: '',
    status: 'todo',
    priority: 3,
    start_at: null,
    due_at: null,
    all_day: true,
    position: 0,
    assignees: [],
    tags: [],
    checklist: [],
    blockers: [],
    is_overdue: false,
    is_blocked: false,
    recurrence: null,
    comments_count: 0,
    ...fields,
  } as Task
}

const day = (key: string) => `${key}T00:00:00Z`

describe('date keys', () => {
  it('shifts across months and years', () => {
    expect(shiftDateKey('2026-10-31', 1)).toBe('2026-11-01')
    expect(shiftDateKey('2027-01-01', -1)).toBe('2026-12-31')
    expect(shiftDateKey('2028-02-28', 1)).toBe('2028-02-29') // leap year
  })

  it('counts whole days, DST change included', () => {
    expect(daysBetween('2026-10-24', '2026-10-26')).toBe(2) // 25.10: clocks go back
    expect(daysBetween('2026-10-26', '2026-10-24')).toBe(-2)
  })
})

describe('kanban', () => {
  it('has one column per status, each in saved order', () => {
    const columns = kanbanColumns([
      task({ id: 1, status: 'todo', position: 1 }),
      task({ id: 2, status: 'todo', position: 0 }),
      task({ id: 3, status: 'done', position: 0 }),
    ])

    expect(Object.keys(columns)).toEqual([
      'todo',
      'in_progress',
      'to_validate',
      'done',
      'cancelled',
    ])
    expect(columns.todo.map((t) => t.id)).toEqual([2, 1])
    expect(columns.done.map((t) => t.id)).toEqual([3])
    expect(columns.in_progress).toEqual([])
  })

  it('sends a position counted among the cards of the same project', () => {
    const column = [
      task({ id: 1, project: 1 }),
      task({ id: 2, project: 2 }), // a sub-project shown on the same board
      task({ id: 3, project: 1 }),
      task({ id: 4, project: 1 }),
    ]

    expect(dropPosition(column, 0)).toBe(0)
    expect(dropPosition(column, 1)).toBe(0) // first card of project 2
    expect(dropPosition(column, 3)).toBe(2) // two cards of project 1 above it
  })
})

describe('calendar events', () => {
  it('skips undated tasks and gives all-day events an exclusive end', () => {
    const events = calendarEvents(
      [
        task({ id: 1 }),
        task({ id: 2, due_at: day('2026-10-12') }),
        task({ id: 3, start_at: day('2026-10-12'), due_at: day('2026-10-14') }),
      ],
      () => true,
    )

    expect(events.map((e) => e.id)).toEqual(['2', '3'])
    expect(events[0]).toMatchObject({ start: '2026-10-12', end: '2026-10-13', allDay: true })
    expect(events[1]).toMatchObject({ start: '2026-10-12', end: '2026-10-15' })
  })

  it('keeps timed tasks as instants, with an end only when there are two dates', () => {
    const [point, span] = calendarEvents(
      [
        task({ all_day: false, due_at: '2026-10-12T12:30:00Z' }),
        task({ all_day: false, start_at: '2026-10-12T08:00:00Z', due_at: '2026-10-12T10:00:00Z' }),
      ],
      () => true,
    )

    expect(point).toMatchObject({ start: '2026-10-12T12:30:00Z', end: undefined, allDay: false })
    expect(span).toMatchObject({ start: '2026-10-12T08:00:00Z', end: '2026-10-12T10:00:00Z' })
  })

  it('flags overdue and closed tasks, and only lets editors drag', () => {
    const [late, done] = calendarEvents(
      [
        task({ id: 1, due_at: day('2026-09-01'), is_overdue: true }),
        task({ id: 2, due_at: day('2026-09-01'), status: 'done' }),
      ],
      (t) => t.id === 1,
    )

    expect(late.classNames).toContain('task-event-overdue')
    expect(late.editable).toBe(true)
    expect(done.classNames).toContain('task-event-closed')
    expect(done.editable).toBe(false)
  })
})

describe('dates after a calendar drag', () => {
  // FullCalendar reports local Dates; all-day ends are exclusive.
  const local = (y: number, m: number, d: number, h = 0, min = 0) => new Date(y, m - 1, d, h, min)

  it('moves a due-only all-day task without inventing a start date', () => {
    const moved = datesAfterCalendarChange(
      { start_at: null, due_at: day('2026-10-12') },
      { allDay: true, start: local(2026, 10, 15), end: local(2026, 10, 16) },
    )

    expect(moved).toEqual({ all_day: true, start_at: null, due_at: day('2026-10-15') })
  })

  it('moves a multi-day task as a block', () => {
    const moved = datesAfterCalendarChange(
      { start_at: day('2026-10-12'), due_at: day('2026-10-14') },
      { allDay: true, start: local(2026, 10, 19), end: local(2026, 10, 22) },
    )

    expect(moved).toEqual({
      all_day: true,
      start_at: day('2026-10-19'),
      due_at: day('2026-10-21'),
    })
  })

  it('gives a start date to a due-only task stretched over several days', () => {
    const moved = datesAfterCalendarChange(
      { start_at: null, due_at: day('2026-10-12') },
      { allDay: true, start: local(2026, 10, 12), end: local(2026, 10, 15) },
    )

    expect(moved).toEqual({
      all_day: true,
      start_at: day('2026-10-12'),
      due_at: day('2026-10-14'),
    })
  })

  it('turns an all-day task into a timed one when dropped on an hour', () => {
    const moved = datesAfterCalendarChange(
      { start_at: null, due_at: day('2026-10-12') },
      { allDay: false, start: local(2026, 10, 12, 14, 30), end: null },
    )

    expect(moved.all_day).toBe(false)
    expect(moved.start_at).toBeNull()
    expect(fromIso(moved.due_at, false)).toEqual({ date: '2026-10-12', time: '14:30' })
  })

  it('keeps both ends of a timed task', () => {
    const moved = datesAfterCalendarChange(
      { start_at: '2026-10-12T08:00:00Z', due_at: '2026-10-12T10:00:00Z' },
      { allDay: false, start: local(2026, 10, 13, 9), end: local(2026, 10, 13, 11) },
    )

    expect(fromIso(moved.start_at, false)).toEqual({ date: '2026-10-13', time: '09:00' })
    expect(fromIso(moved.due_at, false)).toEqual({ date: '2026-10-13', time: '11:00' })
  })
})

describe('gantt rows', () => {
  it('escapes names: frappe-gantt writes them with innerHTML', () => {
    expect(escapeHtml(`<img src=x onerror="alert('x')">&`)).toBe(
      '&lt;img src=x onerror=&quot;alert(&#39;x&#39;)&quot;&gt;&amp;',
    )
    const { rows } = ganttRows([task({ title: '<b>Mix</b>', due_at: day('2026-10-12') })])
    expect(rows[0].name).toBe('&lt;b&gt;Mix&lt;/b&gt;')
  })

  it('separates undated tasks and sorts rows by start', () => {
    const { rows, undated } = ganttRows([
      task({ id: 1, due_at: day('2026-10-20') }),
      task({ id: 2 }),
      task({ id: 3, start_at: day('2026-10-05'), due_at: day('2026-10-09') }),
    ])

    expect(rows.map((row) => row.id)).toEqual(['3', '1'])
    expect(rows[0]).toMatchObject({ start: '2026-10-05', end: '2026-10-09' })
    expect(rows[1]).toMatchObject({ start: '2026-10-20', end: '2026-10-20' })
    expect(undated.map((t) => t.id)).toEqual([2])
  })

  it('only draws arrows between tasks that are both on the chart', () => {
    const blocker: Task['blockers'][number] = {
      id: 1,
      visible: true,
      title: 'a',
      status: 'todo',
      project_name: 'Clip',
      is_open: true,
    }
    const elsewhere = { ...blocker, id: 99 } // in another project: not on this chart
    const { rows } = ganttRows([
      task({ id: 1, due_at: day('2026-10-01') }),
      task({ id: 2, due_at: day('2026-10-05'), blockers: [blocker, elsewhere] }),
    ])

    expect(rows.find((row) => row.id === '2')!.dependencies).toBe('1')
  })

  it('computes progress from the checklist, 100 when done', () => {
    const item = (done: boolean) => ({ id: nextId++, title: 'x', done, pinned: false, position: 0 })
    const { rows } = ganttRows([
      task({
        id: 1,
        due_at: day('2026-10-01'),
        checklist: [item(true), item(false)] as Task['checklist'],
      }),
      task({ id: 2, due_at: day('2026-10-02'), status: 'done' }),
      task({ id: 3, due_at: day('2026-10-03'), is_overdue: true }),
    ])

    expect(rows.map((row) => row.progress)).toEqual([50, 100, 0])
    expect(rows.map((row) => row.custom_class)).toEqual([
      'gantt-open',
      'gantt-closed',
      'gantt-overdue',
    ])
    // classList.add() throws on a space: one class only.
    expect(rows.every((row) => !row.custom_class.includes(' '))).toBe(true)
  })
})

describe('dates after a gantt drag', () => {
  it('moves a due-only task without inventing a start date', () => {
    expect(
      datesAfterGanttChange(
        { start_at: null, due_at: day('2026-10-12'), all_day: true },
        '2026-10-14',
        '2026-10-14',
      ),
    ).toEqual({ all_day: true, start_at: null, due_at: day('2026-10-14') })
  })

  it('stretches an all-day task', () => {
    expect(
      datesAfterGanttChange(
        { start_at: day('2026-10-12'), due_at: day('2026-10-13'), all_day: true },
        '2026-10-12',
        '2026-10-16',
      ),
    ).toEqual({ all_day: true, start_at: day('2026-10-12'), due_at: day('2026-10-16') })
  })

  it('keeps the time of day of a timed task, across the DST change too', () => {
    const before = {
      start_at: null,
      due_at: new Date(2026, 9, 23, 14, 30).toISOString(),
      all_day: false,
    }

    const moved = datesAfterGanttChange(before, '2026-10-27', '2026-10-27')

    expect(moved.start_at).toBeNull()
    expect(fromIso(moved.due_at, false)).toEqual({ date: '2026-10-27', time: '14:30' })
  })
})
